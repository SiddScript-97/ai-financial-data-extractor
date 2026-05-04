"""
mock_llm.py
───────────
A drop-in replacement for LLMExtractor that returns pre-baked realistic
responses without making any API calls. Used for demo / CI / offline runs.

  python pipeline.py --demo
"""

import logging
from datetime import datetime

log = logging.getLogger("mock_llm")

# Pre-baked extraction results aligned with sample_texts.json
_MOCK_RESULTS = [
    {"company_name": "PaySwift",        "funding_amount": 12_000_000,   "round": "Series A",     "investor": "Sequoia Capital India, Accel Partners",       "date": "2024-01-15", "currency_note": "$12 million",   "confidence": 0.97},
    {"company_name": "HealthAI",        "funding_amount": 21_686_747,   "round": "Series B",     "investor": "SoftBank Vision Fund",                         "date": "2024-03-03", "currency_note": "₹150 crore",    "confidence": 0.93},
    {"company_name": "SkillUp",         "funding_amount":    800_000,   "round": "Seed",         "investor": "Blume Ventures, Kalaari Capital",              "date": "2024-02-01", "currency_note": "$800,000",      "confidence": 0.88},
    {"company_name": "AgriTech India",  "funding_amount": 45_000_000,   "round": "Series C",     "investor": "Tiger Global, Lightspeed Venture Partners",    "date": "2024-04-10", "currency_note": "$45 million",   "confidence": 0.96},
    {"company_name": "TrackIt",         "funding_amount": 220_000_000,  "round": "Series D",     "investor": "SoftBank, Tata Capital",                       "date": "2024-05-22", "currency_note": "$220 million",  "confidence": 0.98},
    {"company_name": "GreenLeaf Energy","funding_amount": 30_000_000,   "round": "Bridge",       "investor": "HDFC Capital",                                 "date": None,         "currency_note": "$30M",          "confidence": 0.90},
    {"company_name": "DataGuard",       "funding_amount":  3_500_000,   "round": "Pre-Series A", "investor": "Matrix Partners India",                        "date": None,         "currency_note": "$3.5 million",  "confidence": 0.94},
    {"company_name": "NanoMed",         "funding_amount":  9_638_554,   "round": "Series A",     "investor": "Nexus Venture Partners",                       "date": "2023-07-07", "currency_note": "Rs 80 crore",   "confidence": 0.91},
    {"company_name": "WealthBot",       "funding_amount": 18_000_000,   "round": "Series B",     "investor": "Peak XV Partners",                             "date": "2023-08-30", "currency_note": "$18 million",   "confidence": 0.95},
    {"company_name": "FreightX",        "funding_amount": 55_000_000,   "round": "Series B",     "investor": "Accel, Tiger Global",                          "date": "2023-09-01", "currency_note": "$55 million",   "confidence": 0.92},
    {"company_name": "EduSpark",        "funding_amount":  6_000_000,   "round": "Pre-Series A", "investor": "Blume Ventures",                               "date": None,         "currency_note": "$6 million",    "confidence": 0.89},
    {"company_name": "RetailBot",       "funding_amount": 40_000_000,   "round": "Series C",     "investor": "SoftBank Vision Fund, Lightspeed",             "date": None,         "currency_note": "forty million dollars","confidence": 0.87},
]


class MockLLMExtractor:
    """Returns pre-built extraction results without calling any API."""

    def __init__(self):
        self._index = 0

    def extract(self, text: str, source: str = "unknown") -> dict:
        result = dict(_MOCK_RESULTS[self._index % len(_MOCK_RESULTS)])
        result["_meta"] = {
            "source"       : source,
            "extracted_at" : datetime.now().isoformat(),
            "model"        : "mock-llm (demo mode)",
            "text_preview" : text[:120],
        }
        self._index += 1
        return result

    def extract_batch(self, records: list[dict]) -> list[dict]:
        results = []
        for rec in records:
            result = self.extract(rec["text"], source=rec.get("source", "unknown"))
            result["input_id"] = rec.get("id")
            results.append(result)
            log.info(
                f"  [{rec.get('id'):>2}] {result.get('company_name','?'):<22} "
                f"| {result.get('round','?'):<14} "
                f"| ${result.get('funding_amount') or 0:>13,.0f} "
                f"| conf={result.get('confidence', 0):.2f}"
            )
        return results
