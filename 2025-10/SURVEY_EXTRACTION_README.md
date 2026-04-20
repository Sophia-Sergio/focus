# Survey PDF Extraction Script

This script automatically extracts survey data from PDF files and saves them as JSON files.

## Features

- Processes all PDF files in the digitalizadas folder and subdirectories
- Skips PDFs that already have corresponding JSON files
- Uses Claude AI (Sonnet 4.5) with vision to accurately extract survey responses
- Handles Spanish names, RUN validation, and gender encoding
- Validates column alignment and detects correction marks
- Provides detailed progress tracking and error reporting

## Prerequisites

1. **Python 3.8+** installed
2. **Anthropic API Key** - Get one at https://console.anthropic.com/
3. **Required Python packages** (script will auto-install if missing):
   - pypdf
   - Pillow
   - pdf2image
   - anthropic

## Setup

### 1. Install poppler (required for pdf2image)

**macOS:**
```bash
brew install poppler
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get install poppler-utils
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install poppler-utils
```

### 2. Set your Anthropic API Key

**Option A: Environment Variable (Recommended)**
```bash
export ANTHROPIC_API_KEY='your-api-key-here'
```

To make it permanent, add to your `~/.zshrc` or `~/.bashrc`:
```bash
echo 'export ANTHROPIC_API_KEY="your-api-key-here"' >> ~/.zshrc
source ~/.zshrc
```

**Option B: Pass directly to script**
```bash
python3 extract_all_surveys.py --api-key your-api-key-here
```

## Usage

### Basic Usage (Process all pending PDFs)
```bash
cd /Users/sergiotorres/code/focus
python3 extract_all_surveys.py
```

### Test Mode (Process only 3 files)
```bash
python3 extract_all_surveys.py --test
```

### Process specific number of files
```bash
python3 extract_all_surveys.py --max-files 50
```

### Process a different directory
```bash
python3 extract_all_surveys.py /path/to/other/folder
```

## What the Script Does

1. **Scans** the digitalizadas folder for all PDF files
2. **Identifies** PDFs that don't have corresponding JSON files
3. **Processes** each PDF:
   - Converts PDF pages to high-resolution images
   - Sends to Claude AI for extraction
   - Extracts student metadata (name, RUN, gender, school, etc.)
   - Extracts all 50 survey responses
   - Validates answers and detects invalid responses
4. **Saves** extracted data as JSON file next to the PDF
5. **Reports** progress and success/error statistics

## Output Format

Each PDF generates a JSON file with this structure:

```json
{
  "metadata": {
    "survey_id": "311019",
    "type": "TRT",
    "subtype": "TEST-A",
    "grade_range": "4° - 5°",
    "student_name": "ACOSTA MEDINA, MARIANA SOFIA",
    "student_run": "27063740-K",
    "student_gender": 2,
    "school_name": "COLEGIO WHIPPLE SCHOOL ORIENTE",
    "grade": "4°",
    "section": "A",
    "date": "20-10-2025",
    "extraction_date": "2025-12-16",
    "total_questions": 50,
    "completion_status": "Complete"
  },
  "responses": [
    {"question": "1", "answer": 2, "notes": ""},
    {"question": "2", "answer": 4, "notes": ""},
    {"question": "3", "answer": null, "notes": "Inválido: Múltiples respuestas detectadas"}
  ]
}
```

## Progress Tracking

The script provides real-time progress updates:
- Shows current file being processed (X/Total)
- Updates every 10 files with success/error counts
- Final summary with total statistics

## Error Handling

- Automatically handles missing dependencies (attempts to install)
- Continues processing even if individual files fail
- Reports which files had errors
- Creates error log for debugging

## Cost Estimation

- Each PDF costs approximately $0.15-0.20 (using Claude Sonnet 4.5)
- For 1,653 PDFs: approximately $250-$330 total
- Processing time: ~30-60 seconds per PDF
- Total time for all files: ~14-28 hours

## Resumable Processing

The script is fully resumable:
- Run it multiple times - it only processes files without JSON
- Safe to interrupt (Ctrl+C) and restart
- No duplicate processing

## Tips

1. **Run overnight** for large batches
2. **Monitor the first 10-20 files** to ensure quality
3. **Check error files** if success rate is low
4. **Use --test mode** before processing everything

## Troubleshooting

### "ANTHROPIC_API_KEY not found"
Set your API key as described in Setup section above.

### "poppler not found" or PDF conversion errors
Install poppler as described in Prerequisites.

### "Permission denied"
Make script executable: `chmod +x extract_all_surveys.py`

### Low success rate
- Check PDF quality (some may be unreadable)
- Verify API key is valid
- Check internet connection

## Current Status

- **Total PDFs**: 2,856
- **Already processed**: 1,218 (42.6%)
- **Remaining**: 1,638

## Support

For issues or questions, check:
- Script logs for detailed error messages
- Generated JSON files for data quality
- API usage at https://console.anthropic.com/

---

**Note**: This script requires an active Anthropic API subscription. Make sure you have sufficient credits before processing large batches.
