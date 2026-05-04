"""
pipeline.py
───────────
Orchestrates the full AI-powered financial data extraction pipeline:

  1. Load unstructured text records (JSON)
  2. Send each to Claude via LLMExtractor
  3. Validate & normalise structured output
  4. Load into SQLite via DBLoader
  5. Run analytical queries & print insights
  6. Export clean CSV

Usage
─────
  # Using real Claude API (set ANTHROPIC_API_KEY env var):
  python pipeline.py

  # Demo mode (no API key needed — uses mock LLM responses):
  python pipeline.py --demo

  # Run on your own text file:
  python pipeline.py --input path/to/texts.json
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# ── project modules ────────────────────────────────────────────────────────
from llm_extractor import LLMExtractor
from db_loader     import DBLoader
from mock_llm      import MockLLMExtractor   # demo / CI mode

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
BASE_DIR    = Path(__file__).parent
DATA_DIR    = BASE_DIR / "data"
OUTPUT_DIR  = BASE_DIR / "output"
LOG_DIR     = BASE_DIR / "logs"

for d in (OUTPUT_DIR, LOG_DIR):
    d.mkdir(exist_ok=True)

DB_PATH     = OUTPUT_DIR / "deals.db"
CSV_PATH    = OUTPUT_DIR / "extracted_deals.csv"
LOG_PATH    = LOG_DIR    / "pipeline.log"
SAMPLE_JSON = DATA_DIR   / "sample_texts.json"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level   = logging.INFO,
    format  = "%(asctime)s  %(levelname)-8s  %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("pipeline")


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(input_path: Path, demo: bool = False) -> dict:
    log.info("=" * 65)
    log.info("  AI FINANCIAL DATA EXTRACTION PIPELINE — START")
    log.info("=" * 65)
    start = datetime.now()

    # ── Step 1: Load input ─────────────────────────────────────────────────
    log.info("─" * 65)
    log.info("STEP 1 — LOAD UNSTRUCTURED TEXT RECORDS")
    with open(input_path) as f:
        records = json.load(f)
    log.info(f"  Loaded {len(records)} text records from {input_path.name}")

    # ── Step 2: LLM Extraction ─────────────────────────────────────────────
    log.info("─" * 65)
    log.info("STEP 2 — LLM-BASED ENTITY EXTRACTION")

    if demo:
        log.info("  ⚡ DEMO MODE — using mock LLM (no API key required)")
        extractor = MockLLMExtractor()
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            log.error(
                "ANTHROPIC_API_KEY not set. "
                "Run with --demo flag for demo mode, or export your key."
            )
            sys.exit(1)
        log.info("  Using Claude claude-sonnet-4-20250514 via Anthropic API")
        extractor = LLMExtractor(api_key=api_key)

    extracted = extractor.extract_batch(records)
    ok_count  = sum(1 for r in extracted if "error" not in r)
    err_count = len(extracted) - ok_count
    log.info(f"  Extraction complete: {ok_count} OK / {err_count} errors")

    # ── Step 3: Save raw extraction JSON ──────────────────────────────────
    raw_json_path = OUTPUT_DIR / "raw_extractions.json"
    with open(raw_json_path, "w") as f:
        json.dump(extracted, f, indent=2, default=str)
    log.info(f"  Raw extractions saved → {raw_json_path}")

    # ── Step 4: Load to DB ─────────────────────────────────────────────────
    log.info("─" * 65)
    log.info("STEP 3 — LOAD TO SQLITE")
    db = DBLoader(DB_PATH)
    db.insert_deals(extracted)

    # ── Step 5: Analyse ────────────────────────────────────────────────────
    log.info("─" * 65)
    log.info("STEP 4 — ANALYSIS & INSIGHTS")
    insights = db.run_all_insights()
    db.print_insights(insights)

    # ── Step 6: Export CSV ─────────────────────────────────────────────────
    log.info("─" * 65)
    log.info("STEP 5 — EXPORT")
    db.export_csv(CSV_PATH)

    elapsed = (datetime.now() - start).total_seconds()
    log.info("─" * 65)
    log.info(f"  Pipeline COMPLETE in {elapsed:.2f}s")
    log.info("=" * 65)

    return {
        "status"      : "success",
        "records_in"  : len(records),
        "records_ok"  : ok_count,
        "records_err" : err_count,
        "db_path"     : str(DB_PATH),
        "csv_path"    : str(CSV_PATH),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Financial Data Extraction Pipeline")
    parser.add_argument(
        "--demo", action="store_true",
        help="Run in demo mode using mock LLM (no API key required)"
    )
    parser.add_argument(
        "--input", type=Path, default=SAMPLE_JSON,
        help=f"Path to input JSON (default: {SAMPLE_JSON})"
    )
    args = parser.parse_args()

    result = run_pipeline(args.input, demo=args.demo)
    print(f"\nOutputs:")
    print(f"  Database : {result['db_path']}")
    print(f"  CSV      : {result['csv_path']}")
    print(f"  Log      : {LOG_PATH}")
