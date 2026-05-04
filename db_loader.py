"""
db_loader.py
────────────
Handles all SQLite operations for the AI Financial Extractor:
  - Schema creation
  - Inserting extracted deal records
  - Running analytical queries
  - Exporting results to CSV
"""

import sqlite3
import csv
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

log = logging.getLogger("db_loader")

DDL = """
CREATE TABLE IF NOT EXISTS deals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    input_id        INTEGER,
    company_name    TEXT,
    funding_amount  REAL,
    round           TEXT,
    investor        TEXT,
    date            TEXT,
    currency_note   TEXT,
    confidence      REAL,
    source          TEXT,
    model           TEXT,
    extracted_at    TEXT
);

CREATE TABLE IF NOT EXISTS extraction_runs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at      TEXT,
    records_in  INTEGER,
    records_ok  INTEGER,
    records_err INTEGER
);

CREATE INDEX IF NOT EXISTS idx_deals_round      ON deals(round);
CREATE INDEX IF NOT EXISTS idx_deals_investor   ON deals(investor);
CREATE INDEX IF NOT EXISTS idx_deals_confidence ON deals(confidence);
"""

INSIGHT_QUERIES = {
    "by_round": """
        SELECT round,
               COUNT(*)                               AS deals,
               ROUND(SUM(funding_amount),    2)       AS total_usd,
               ROUND(AVG(funding_amount),    2)       AS avg_usd
        FROM   deals
        WHERE  funding_amount IS NOT NULL
        GROUP  BY round
        ORDER  BY total_usd DESC;
    """,
    "by_investor": """
        SELECT investor,
               COUNT(*)                               AS deals,
               ROUND(SUM(funding_amount), 2)          AS total_deployed
        FROM   deals
        WHERE  investor IS NOT NULL
          AND  funding_amount IS NOT NULL
        GROUP  BY investor
        ORDER  BY deals DESC
        LIMIT  10;
    """,
    "top_deals": """
        SELECT company_name, round, investor,
               ROUND(funding_amount, 2)               AS funding_usd,
               date, confidence, currency_note
        FROM   deals
        WHERE  funding_amount IS NOT NULL
        ORDER  BY funding_amount DESC
        LIMIT  10;
    """,
    "confidence_distribution": """
        SELECT CASE
                 WHEN confidence >= 0.9 THEN 'High   (≥0.90)'
                 WHEN confidence >= 0.7 THEN 'Medium (0.70–0.89)'
                 ELSE                        'Low    (<0.70)'
               END AS band,
               COUNT(*) AS records
        FROM   deals
        GROUP  BY band
        ORDER  BY records DESC;
    """,
    "all_deals": """
        SELECT id, company_name, funding_amount, round, investor,
               date, currency_note, confidence, source
        FROM   deals
        ORDER  BY id;
    """,
}


class DBLoader:

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_schema()

    def _init_schema(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(DDL)

    # ── Insert ─────────────────────────────────────────────────────────────

    def insert_deals(self, records: list[dict]) -> tuple[int, int]:
        """
        Insert extracted records. Returns (ok_count, err_count).
        Records with an 'error' key are skipped and counted as errors.
        """
        ok, err = 0, 0
        with sqlite3.connect(self.db_path) as conn:
            for rec in records:
                if "error" in rec:
                    err += 1
                    continue
                meta = rec.get("_meta", {})
                try:
                    conn.execute(
                        """
                        INSERT INTO deals
                          (input_id, company_name, funding_amount, round,
                           investor, date, currency_note, confidence,
                           source, model, extracted_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?)
                        """,
                        (
                            rec.get("input_id"),
                            rec.get("company_name"),
                            rec.get("funding_amount"),
                            rec.get("round"),
                            rec.get("investor"),
                            rec.get("date"),
                            rec.get("currency_note"),
                            rec.get("confidence"),
                            meta.get("source"),
                            meta.get("model"),
                            meta.get("extracted_at"),
                        ),
                    )
                    ok += 1
                except Exception as exc:
                    log.warning(f"Insert failed for input_id={rec.get('input_id')}: {exc}")
                    err += 1

            conn.execute(
                "INSERT INTO extraction_runs VALUES (?,?,?,?,?)",
                (None, datetime.now().isoformat(), len(records), ok, err),
            )
        log.info(f"  Inserted {ok} rows; {err} errors")
        return ok, err

    # ── Query ──────────────────────────────────────────────────────────────

    def query(self, name: str) -> pd.DataFrame:
        sql = INSIGHT_QUERIES.get(name)
        if not sql:
            raise ValueError(f"Unknown query: {name}")
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(sql, conn)

    def run_all_insights(self) -> dict[str, pd.DataFrame]:
        return {name: self.query(name) for name in INSIGHT_QUERIES}

    # ── Export ─────────────────────────────────────────────────────────────

    def export_csv(self, out_path: Path) -> None:
        df = self.query("all_deals")
        df.to_csv(out_path, index=False)
        log.info(f"  Exported {len(df)} rows → {out_path}")

    # ── Print insights ─────────────────────────────────────────────────────

    def print_insights(self, insights: dict[str, pd.DataFrame]) -> None:
        div = "=" * 65

        print(f"\n{div}")
        print("  TOP DEALS BY FUNDING AMOUNT")
        print(div)
        for _, r in insights["top_deals"].iterrows():
            amt = f"${r['funding_usd']:>12,.0f}"
            print(f"  {r['company_name']:<22} {r['round']:<14} {amt}  "
                  f"[{r['currency_note']}]  conf={r['confidence']:.2f}")

        print(f"\n{div}")
        print("  FUNDING BY ROUND")
        print(div)
        for _, r in insights["by_round"].iterrows():
            print(f"  {r['round']:<16} {int(r['deals']):>3} deals  "
                  f"total ${r['total_usd']:>13,.0f}  avg ${r['avg_usd']:>12,.0f}")

        print(f"\n{div}")
        print("  TOP INVESTORS BY DEAL COUNT")
        print(div)
        for _, r in insights["by_investor"].iterrows():
            print(f"  {r['investor']:<35} {int(r['deals']):>2} deals  "
                  f"${r['total_deployed']:>13,.0f} deployed")

        print(f"\n{div}")
        print("  EXTRACTION CONFIDENCE DISTRIBUTION")
        print(div)
        for _, r in insights["confidence_distribution"].iterrows():
            print(f"  {r['band']}   →  {int(r['records'])} records")

        print()
