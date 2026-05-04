"""
llm_extractor.py
────────────────
Uses the Anthropic Claude API to extract structured financial entities
from raw, unstructured text (news articles, reports, announcements).

Extracted fields
────────────────
  company_name    – name of the company that received funding
  funding_amount  – amount in USD (float); converts ₹ crore → USD automatically
  round           – funding round (Seed / Series A / Series B / …)
  investor        – lead investor name (or comma-separated list)
  date            – ISO 8601 date string (YYYY-MM-DD) or None
  currency_note   – original currency/amount string for auditability
  confidence      – LLM self-rated confidence 0.0–1.0

Usage (standalone)
──────────────────
  python llm_extractor.py
"""

import json
import re
import os
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger("extractor")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
MODEL         = "claude-sonnet-4-20250514"
MAX_TOKENS    = 512
INR_TO_USD    = 0.012          # approximate conversion rate
CRORE         = 10_000_000     # 1 crore INR in INR units


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are a financial data extraction specialist.
Given a piece of financial news text, extract the following fields and return
ONLY a valid JSON object — no markdown, no explanation, no extra text.

Fields to extract:
  company_name    (string)  - Company that received funding. Null if unclear.
  funding_amount  (number)  - Amount in USD. Convert ₹ crore → USD using 1 crore = 10,000,000 INR and 1 USD = 83 INR.
                              Convert "forty million" → 40000000. Null if not stated.
  round           (string)  - e.g. "Seed", "Pre-Series A", "Series A", "Series B", "Series C", "Series D",
                              "Bridge", "Growth". Null if not stated.
  investor        (string)  - Lead investor(s). If multiple, comma-separated. Null if not stated.
  date            (string)  - ISO 8601 (YYYY-MM-DD). Infer year from context if only month given.
                              Null if no date available.
  currency_note   (string)  - Original amount as written in the text (e.g. "₹150 crore", "$12M").
  confidence      (number)  - Your extraction confidence between 0.0 and 1.0.

Return exactly this JSON structure, no other text:
{
  "company_name": ...,
  "funding_amount": ...,
  "round": ...,
  "investor": ...,
  "date": ...,
  "currency_note": ...,
  "confidence": ...
}"""


# ---------------------------------------------------------------------------
# LLM Extractor
# ---------------------------------------------------------------------------

class LLMExtractor:
    """
    Wraps the Anthropic Claude API to extract structured financial data
    from unstructured text.
    """

    def __init__(self, api_key: Optional[str] = None):
        import anthropic as _anthropic
        key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = _anthropic.Anthropic(api_key=key)

    # ── Public method ──────────────────────────────────────────────────────

    def extract(self, text: str, source: str = "unknown") -> dict:
        """
        Send text to Claude, parse the JSON response, validate, and return
        a clean record dict.

        Returns a dict with an additional `_meta` key containing pipeline info.
        """
        log.debug(f"Extracting from source='{source}'  text_len={len(text)}")

        raw_json = self._call_llm(text)
        parsed   = self._parse_json(raw_json)
        validated = self._validate(parsed)
        validated["_meta"] = {
            "source"       : source,
            "extracted_at" : datetime.now().isoformat(),
            "model"        : MODEL,
            "text_preview" : text[:120] + ("…" if len(text) > 120 else ""),
        }
        return validated

    def extract_batch(self, records: list[dict]) -> list[dict]:
        """
        Extract from a list of {'id', 'source', 'text'} dicts.
        Returns extraction results; failures include an 'error' key.
        """
        results = []
        for rec in records:
            try:
                result = self.extract(rec["text"], source=rec.get("source", "unknown"))
                result["input_id"] = rec.get("id")
                results.append(result)
                log.info(
                    f"  [{rec.get('id'):>2}] {result.get('company_name','?'):<22} "
                    f"| {result.get('round','?'):<14} "
                    f"| ${result.get('funding_amount') or 0:>13,.0f} "
                    f"| conf={result.get('confidence', 0):.2f}"
                )
            except Exception as exc:
                log.warning(f"  [{rec.get('id')}] FAILED — {exc}")
                results.append({
                    "input_id": rec.get("id"),
                    "error"   : str(exc),
                    "_meta"   : {"source": rec.get("source"), "model": MODEL},
                })
        return results

    # ── Private helpers ────────────────────────────────────────────────────

    def _call_llm(self, text: str) -> str:
        """Call Claude and return the raw text response."""
        response = self.client.messages.create(
            model      = MODEL,
            max_tokens = MAX_TOKENS,
            system     = SYSTEM_PROMPT,
            messages   = [{"role": "user", "content": text}],
        )
        return response.content[0].text.strip()

    def _parse_json(self, raw: str) -> dict:
        """
        Parse JSON from LLM response.
        Strips accidental markdown fences if present.
        """
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        cleaned = re.sub(r"\n?```$",          "", cleaned).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned invalid JSON: {exc}\nRaw: {raw[:300]}")

    def _validate(self, data: dict) -> dict:
        """
        Validate and normalise extracted fields.
        - Coerces types
        - Clips confidence to [0, 1]
        - Normalises funding_amount to float or None
        - Strips whitespace from strings
        """
        out = {}

        # company_name
        out["company_name"] = (
            str(data["company_name"]).strip()
            if data.get("company_name") else None
        )

        # funding_amount — must be positive float
        raw_amt = data.get("funding_amount")
        if raw_amt is not None:
            try:
                amt = float(raw_amt)
                out["funding_amount"] = round(amt, 2) if amt > 0 else None
            except (TypeError, ValueError):
                out["funding_amount"] = None
        else:
            out["funding_amount"] = None

        # round
        out["round"] = (
            str(data["round"]).strip().title()
            if data.get("round") else None
        )

        # investor
        out["investor"] = (
            str(data["investor"]).strip()
            if data.get("investor") else None
        )

        # date — accept ISO string or None
        raw_date = data.get("date")
        if raw_date and str(raw_date).lower() not in ("null", "none", ""):
            try:
                parsed_date = datetime.strptime(str(raw_date)[:10], "%Y-%m-%d")
                out["date"] = parsed_date.strftime("%Y-%m-%d")
            except ValueError:
                out["date"] = None
        else:
            out["date"] = None

        # currency_note
        out["currency_note"] = (
            str(data["currency_note"]).strip()
            if data.get("currency_note") else None
        )

        # confidence
        try:
            conf = float(data.get("confidence", 0.5))
            out["confidence"] = max(0.0, min(1.0, conf))
        except (TypeError, ValueError):
            out["confidence"] = 0.5

        return out


# ---------------------------------------------------------------------------
# Standalone demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")

    sample = (
        'Bengaluru-based fintech startup PaySwift has raised $12 million '
        'in a Series A funding round led by Sequoia Capital India on January 15, 2024.'
    )

    extractor = LLMExtractor()
    result    = extractor.extract(sample, source="demo")

    print("\n── Extraction result ───────────────────────────────────")
    print(json.dumps(result, indent=2))
