# 🤖 AI-Powered Financial Data Extraction System

An end-to-end pipeline that uses **Claude (claude-sonnet-4-20250514)** to convert unstructured
financial news text into structured, queryable data — stored in SQLite and exported
to CSV.

---

## 🗂️ Project Structure

```
ai_financial_extractor/
├── pipeline.py            # Main orchestrator — run this
├── llm_extractor.py       # Claude API integration & validation
├── db_loader.py           # SQLite loader + analytical queries
├── mock_llm.py            # Demo mode (no API key needed)
├── extract_text.py        # Interactive single-text CLI
├── requirements.txt
├── data/
│   └── sample_texts.json  # 12 realistic financial news snippets
├── output/
│   ├── deals.db           # SQLite database (created at runtime)
│   ├── raw_extractions.json  # Raw LLM JSON responses
│   └── extracted_deals.csv   # Clean CSV export
└── logs/
    └── pipeline.log
```

---

## ⚡ Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2a. Run in DEMO MODE (no API key needed)
python pipeline.py --demo

# 2b. Run with real Claude API
export ANTHROPIC_API_KEY=sk-ant-...
python pipeline.py

# 3. Extract a single text interactively
python extract_text.py --demo
python extract_text.py --text "Startup XYZ raised $5M Series A from Sequoia"
```

---

## 🏗️ System Architecture

```
Raw Text (News / Reports / Announcements)
        │
        ▼
  ┌─────────────┐
  │ LLMExtractor│  ← Claude claude-sonnet-4-20250514 via Anthropic API
  │  (Step 2)   │  Prompt-based extraction → JSON response
  └─────┬───────┘
        │
        ▼
  ┌─────────────┐
  │  Validator  │  Type coercion · Currency normalisation · Date parsing
  │  (Step 2)   │  Confidence clipping · Null handling
  └─────┬───────┘
        │
        ▼
  ┌─────────────┐
  │  DBLoader   │  SQLite: deals table · Indexed for fast queries
  │  (Step 3)   │  Analytical queries: by round, by investor, top deals
  └─────┬───────┘
        │
        ▼
  Output: deals.db + extracted_deals.csv + raw_extractions.json
```

---

## 🧠 LLM Extraction

The system sends each text to Claude with a structured system prompt that asks for:

| Field | Type | Notes |
|---|---|---|
| `company_name` | string | Company receiving funding |
| `funding_amount` | float | Always in USD; ₹ crore → USD auto-converted |
| `round` | string | Seed / Pre-Series A / Series A / B / C / D / Bridge |
| `investor` | string | Lead investor(s), comma-separated |
| `date` | string | ISO 8601 (YYYY-MM-DD) |
| `currency_note` | string | Original amount as written (auditability) |
| `confidence` | float | LLM self-rated 0.0–1.0 |

**Currency conversion:**
- `₹150 crore` → `₹150,00,00,000 / 83` ≈ `$18,072,289`
- `"forty million dollars"` → `40000000`

---

## 🗄️ Database Schema

```sql
CREATE TABLE deals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    input_id        INTEGER,   -- links back to input record
    company_name    TEXT,
    funding_amount  REAL,      -- always USD
    round           TEXT,
    investor        TEXT,
    date            TEXT,
    currency_note   TEXT,      -- original text amount
    confidence      REAL,      -- 0.0 to 1.0
    source          TEXT,      -- publication name
    model           TEXT,      -- LLM model used
    extracted_at    TEXT       -- ISO timestamp
);
```

---

## 📊 Analytical Queries (built-in)

| Query | Description |
|---|---|
| `by_round` | Total & average funding per round type |
| `by_investor` | Top investors by deal count & capital deployed |
| `top_deals` | Largest 10 deals |
| `confidence_distribution` | High / Medium / Low confidence breakdown |
| `all_deals` | Full export |

---

## 📝 Sample Input → Output

**Input (unstructured text):**
```
"Bengaluru-based fintech startup PaySwift has raised $12 million in a Series A
funding round led by Sequoia Capital India, with participation from Accel Partners.
The deal was closed on January 15, 2024."
```

**Output (structured JSON):**
```json
{
  "company_name": "PaySwift",
  "funding_amount": 12000000.0,
  "round": "Series A",
  "investor": "Sequoia Capital India, Accel Partners",
  "date": "2024-01-15",
  "currency_note": "$12 million",
  "confidence": 0.97
}
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| LLM | Anthropic Claude (claude-sonnet-4-20250514) |
| API client | `anthropic` Python SDK |
| Data processing | `pandas`, `numpy` |
| Storage | `sqlite3` (standard library) |
| Export | CSV via pandas |

---

## 🚀 Future Enhancements

- **FastAPI** — expose extraction as a REST API endpoint
- **Batch web scraping** — feed live news articles via BeautifulSoup / Scrapy
- **Confidence thresholds** — auto-flag low-confidence records for human review
- **Full ETL integration** — pipe output into the Financial ETL Pipeline project
- **Airflow DAG** — scheduled extraction from news RSS feeds
- **Dashboard** — Streamlit app showing real-time extraction results
- **Multi-language** — extract from Hindi/Tamil/Telugu financial news

---

## 🔑 API Key Setup

Get your key at [console.anthropic.com](https://console.anthropic.com).

```bash
export ANTHROPIC_API_KEY=sk-ant-...   # macOS / Linux
set ANTHROPIC_API_KEY=sk-ant-...      # Windows CMD
$env:ANTHROPIC_API_KEY="sk-ant-..."   # Windows PowerShell
```

---

## 📌 Real-World Relevance

Financial institutions extract data from thousands of news articles and reports
daily. This project demonstrates how LLMs can automate that workflow — converting
noisy text into a clean, indexed database ready for downstream analytics, replacing
hours of manual parsing with a single pipeline run.
