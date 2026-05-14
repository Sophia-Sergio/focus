# Project Context: Focus — Survey PDF Extraction Pipeline

> **Generated on:** 2026-05-02
> **Purpose:** Provides a high-level summary of scripts, conventions, and architecture so any agent can get up to speed quickly.

## Overview
This is a **Chilean student survey data extraction pipeline**. It downloads survey PDFs from Google Drive, uses AI vision models (Claude API and optionally local LM Studio) to extract hand-marked responses, and converts the results into consolidated CSVs for analysis.

## Project Structure

```
/Users/sergiotorres/code/personal/focus/
├── scripts/
│   ├── download/
│   │   └── download_drive_folder.py    # Google Drive batch downloader
│   ├── extraction/
│   │   ├── extract_all_surveys.py      # Main batch extractor (Claude Vision)
│   │   └── ab_test.py                  # A/B test: Claude vs local Qwen2.5-VL
│   ├── output/
│   │   ├── move_jsons.py               # Move JSONs preserving folder structure
│   │   └── json_to_csv.py              # Consolidate JSONs into grade-range CSVs
│   └── analysis/
│       └── analyze_differences.py      # Analyze comparison/difference JSON files
├── .claude/
│   ├── extraction_rules.md             # Shared prompt rules for AI extraction
│   ├── settings.local.json             # Claude permissions config
│   └── agents/
│       └── pdf-survey-extractor.md     # Claude agent definition
└── CONTEXT.md                          # This file
```

## Key Concepts & Conventions

| Concept | Details |
|---|---|
| **Grade Ranges** | **4°–5°** (50 questions) and **6°–7°** (68 questions) |
| **Scale 1 (Certainty)** | `No es cierto`→1, `Poco cierto`→2, `Bastante cierto`→3, `Muy cierto`→4 |
| **Scale 2 (Frequency)** | `Nunca`→1, `Rara vez`→2, `A veces`→3, `Siempre`→4 |
| **Folder Naming** | `SCHOOL NAME G°SECTION` (e.g. `COLEGIO EJEMPLO 5°A`) |
| **Output JSON Naming** | `{survey_id}_2d_attemp.json` per PDF |
| **Consolidated CSVs** | `4-5_consolidated_2d_attemp.csv` and `6-7_consolidated_2d_attemp.csv` |

---

## Scripts Reference

### 1. `scripts/download/download_drive_folder.py`
**Purpose:** Download all files from a shared Google Drive folder (recursively optional).

**Key Behaviors:**
- Extracts `folder_id` from full URLs or uses raw ID
- OAuth2 authentication with Google Drive API
- Supports credentials via `credentials.json` or `scripts/.env` (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_DESKTOP`)
- Caches token in `~/.credentials/drive_downloader.json`
- Exports Google Docs → `.docx`, Sheets → `.xlsx`, Slides → `.pptx`
- Skips existing files

**CLI:**
```bash
python scripts/download/download_drive_folder.py <folder_id_or_url> [destination] --recursive --credentials
```

---

### 2. `scripts/extraction/extract_all_surveys.py`
**Purpose:** Main batch extractor. Converts PDFs to images and sends them to Claude Vision API.

**Key Behaviors:**
- Auto-installs missing deps: `pypdf`, `Pillow`, `pdf2image`, `anthropic`
- Converts PDF pages → base64 PNGs at 200 DPI
- Derives task context from folder name (school, grade, section)
- Loads shared rules from `.claude/extraction_rules.md`
- Calls Claude model `claude-sonnet-4-5-20250929`
- **Retry logic:** 3 attempts with exponential backoff on rate limits (5s, 10s, 20s)
- Skips already-processed PDFs (checks for `_2d_attemp.json`)
- Supports single-file or batch mode
- Default target: `/Users/sergiotorres/code/focus/digitalizadas`

**CLI:**
```bash
python scripts/extraction/extract_all_surveys.py [file_or_folder] --api-key --max-files --test --delay --force
```

---

### 3. `scripts/extraction/ab_test.py`
**Purpose:** Compare Claude API vs a local vision model (e.g. Qwen2.5-VL in LM Studio) on a single survey.

**Key Behaviors:**
- Same PDF→image conversion and task-context building as the main extractor
- Runs both extractors on the same PDF
- Compares metadata fields and every question answer
- Prints mismatch report with statistics (% agreement, missing fields, per-question diffs)
- Optional `--save` to write `_claude.json` and `_local.json`

**CLI:**
```bash
python scripts/extraction/ab_test.py <survey.pdf> --lm-url http://localhost:1234/v1 --model qwen2.5-vl-7b-instruct --save --skip-claude --skip-local
```

---

### 4. `scripts/output/move_jsons.py`
**Purpose:** Move all `_2d_attemp.json` files from `digitalizadas/` to `jsons/` preserving folder hierarchy.

**Hardcoded Paths:**
- Source: `/Users/sergiotorres/code/focus/digitalizadas`
- Destination: `/Users/sergiotorres/code/focus/jsons`

---

### 5. `scripts/output/json_to_csv.py`
**Purpose:** Consolidate all `_2d_attemp.json` files into two grade-range CSVs.

**Key Behaviors:**
- Recursively finds `*_2d_attemp.json` in `digitalizadas/`
- Groups by `grade_range`: `4°-5°` (50 Qs) and `6°-7°` (68 Qs)
- CSV columns: 16 metadata fields + `q1`…`q50`/`q68`
- Null answers written as empty strings
- Outputs:
  - `digitalizadas/4-5_consolidated_2d_attemp.csv`
  - `digitalizadas/6-7_consolidated_2d_attemp.csv`

---

### 6. `scripts/analysis/analyze_differences.py`
**Purpose:** Analyze `_comparison.json` files across `digitalizadas/` to compute extraction quality stats.

**Metrics Produced:**
- Total survey pairs, surveys with differences, difference rate
- Distribution of difference counts (histogram)
- Average, median, max differences per survey

---

## Shared Resources

### `.claude/extraction_rules.md`
Master prompt/rules injected into every AI extraction call. Covers:
- Metadata extraction rules (RUN formatting, gender mapping, date formatting)
- Two answer scales (Certainty & Frequency)
- **Mandatory 5-step mark-counting procedure:**
  1. Count marks in all 4 columns
  2. Check mark count
  3. Handle multiple marks (large X = correction; else invalid)
  4. Exactly 1 mark → record column number
  5. No marks → `null`, "Sin respuesta visible"
- Faint/blurry mark handling
- Strict JSON output schema

### `.claude/agents/pdf-survey-extractor.md`
Claude Code agent definition (`pdf-survey-extractor`) that delegates survey extraction tasks. References `extraction_rules.md` and enforces skipping already-processed files.

---

## Environment & Dependencies

- **Python 3**
- **Required packages:** `anthropic`, `openai`, `pdf2image`, `Pillow`, `pypdf`, `google-api-python-client`, `google-auth-httplib2`, `google-auth-oauthlib`
- **External binary:** `poppler` (required by `pdf2image` for PDF→image conversion)
- **API keys:**
  - `ANTHROPIC_API_KEY` (required for extraction)
  - Google OAuth credentials (for Drive downloads; optional file or env vars)
- **Optional local model:** LM Studio running Qwen2.5-VL-7B-Instruct (OpenAI-compatible API at `http://localhost:1234/v1`)

---

## Workflow Summary

1. **Download** surveys from Google Drive using `download_drive_folder.py`
2. **Extract** responses using `extract_all_surveys.py` (Claude Vision)
3. **(Optional)** Validate with `ab_test.py` against a local model
4. **Move** results with `move_jsons.py` if needed
5. **Consolidate** into CSVs with `json_to_csv.py`
6. **Analyze** quality with `analyze_differences.py`
