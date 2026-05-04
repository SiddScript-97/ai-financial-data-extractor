"""
extract_text.py
───────────────
Interactive CLI: paste any financial news text and get structured JSON back.

Usage
─────
  # With real API:
  python extract_text.py

  # Demo mode:
  python extract_text.py --demo

  # Direct text argument:
  python extract_text.py --text "Startup ABC raised $5M Series A from XYZ Capital"
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mock_llm import MockLLMExtractor


def main():
    parser = argparse.ArgumentParser(
        description="Extract structured data from a single financial news text."
    )
    parser.add_argument("--demo",  action="store_true", help="Demo mode, no API key needed")
    parser.add_argument("--text",  type=str, default=None, help="Text to extract from")
    args = parser.parse_args()

    if args.demo:
        extractor = MockLLMExtractor()
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            print("⚠ ANTHROPIC_API_KEY not set — falling back to demo mode.\n")
            extractor = MockLLMExtractor()
        else:
            from llm_extractor import LLMExtractor
            extractor = LLMExtractor(api_key=api_key)

    if args.text:
        text = args.text
    else:
        print("=" * 60)
        print("  AI Financial Data Extractor")
        print("  Paste your financial news text below.")
        print("  Press Enter twice (blank line) when done.")
        print("=" * 60)
        lines = []
        while True:
            line = input()
            if line == "":
                break
            lines.append(line)
        text = " ".join(lines).strip()

    if not text:
        print("No text provided.")
        sys.exit(1)

    print("\n⏳ Extracting structured data…\n")
    result = extractor.extract(text, source="cli")

    meta = result.pop("_meta", {})
    print("─" * 60)
    print("  EXTRACTED FIELDS")
    print("─" * 60)
    for k, v in result.items():
        label = k.replace("_", " ").title()
        if k == "funding_amount" and v:
            print(f"  {label:<20}  ${v:,.2f}")
        elif k == "confidence" and v is not None:
            bar = "█" * int(v * 20)
            print(f"  {label:<20}  {v:.2f}  {bar}")
        else:
            print(f"  {label:<20}  {v}")
    print("─" * 60)
    print(f"  Model: {meta.get('model')}  |  At: {meta.get('extracted_at','')[:19]}")
    print()

    json_out = dict(result)
    print("JSON output:")
    print(json.dumps(json_out, indent=2, default=str))


if __name__ == "__main__":
    main()
