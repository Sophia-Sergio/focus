#!/usr/bin/env python3
"""
Survey PDF Extraction Script
Processes PDF survey files and extracts responses to JSON format.
"""

import os
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import re
import time

# Try to import required libraries
try:
    import pypdf
except ImportError:
    print("Error: pypdf library not found. Installing...")
    os.system("pip3 install pypdf")
    import pypdf

try:
    from PIL import Image
    import pdf2image
except ImportError:
    print("Error: Pillow and pdf2image not found. Installing...")
    os.system("pip3 install Pillow pdf2image")
    from PIL import Image
    import pdf2image

try:
    import anthropic
except ImportError:
    print("Error: anthropic library not found. Installing...")
    os.system("pip3 install anthropic")
    import anthropic


class SurveyExtractor:
    """Extracts survey data from PDF files using Claude API."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the extractor with Anthropic API key."""
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY not found. "
                "Set it as an environment variable or pass it to the constructor."
            )
        self.client = anthropic.Anthropic(api_key=self.api_key)

    def pdf_to_base64_images(self, pdf_path: str) -> List[Dict]:
        """Convert PDF pages to base64-encoded images."""
        try:
            # Convert PDF to images
            images = pdf2image.convert_from_path(pdf_path, dpi=200)

            image_data = []
            for i, image in enumerate(images):
                # Convert to RGB if necessary
                if image.mode != 'RGB':
                    image = image.convert('RGB')

                # Save to bytes
                import io
                import base64
                buffer = io.BytesIO()
                image.save(buffer, format='PNG')
                img_bytes = buffer.getvalue()
                img_base64 = base64.b64encode(img_bytes).decode('utf-8')

                image_data.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": img_base64
                    }
                })

            return image_data
        except Exception as e:
            print(f"Error converting PDF to images: {e}")
            return []

    def extract_survey_data(self, pdf_path: str, max_retries: int = 3) -> Optional[Dict]:
        """Extract survey data from a PDF file using Claude API with retry logic."""
        try:
            print(f"Processing: {pdf_path}")

            # Convert PDF to images
            images = self.pdf_to_base64_images(pdf_path)
            if not images:
                print(f"Failed to convert PDF to images: {pdf_path}")
                return None

            # Extract filename without extension for survey_id
            from pathlib import Path
            filename_without_ext = Path(pdf_path).stem

            # Parse folder name — folder is the single source of truth for grade/section
            folder_name = Path(pdf_path).parent.name
            folder_match = re.match(r'^(.+?)\s+(\d°)([A-Z])$', folder_name)
            if folder_match:
                school_folder = folder_match.group(1).strip()
                grade_folder = folder_match.group(2)
                section_folder = folder_match.group(3)
            else:
                school_folder = folder_name
                grade_folder = None
                section_folder = None

            if grade_folder in ("6°", "7°"):
                grade_range = "6° - 7°"
                total_questions = 68
                scale_1_end = 49
                scale_2_start = 50
            else:
                grade_range = "4° - 5°"
                total_questions = 50
                scale_1_end = 31
                scale_2_start = 32

            print(f"  Folder: {folder_name} → grade {grade_folder}, {total_questions} questions")

            # Load shared extraction rules
            rules_path = Path(__file__).parent.parent.parent / ".claude" / "extraction_rules.md"
            extraction_rules = rules_path.read_text(encoding="utf-8")

            # Prepare the prompt — task context + shared rules
            prompt = f"""## Task Context
- survey_id: "{filename_without_ext}" — use this exact value, do NOT read it from the PDF
- grade_range: "{grade_range}" — use this exact value, do NOT read it from the PDF
- grade: "{grade_folder}" — use this exact value, do NOT read it from the PDF
- section: "{section_folder}" — use this exact value, do NOT read it from the PDF
- total_questions: {total_questions}
- Scale 1 (Certainty) applies to questions 1–{scale_1_end}
- Scale 2 (Frequency) applies to questions {scale_2_start}–{total_questions}
- school_folder: "{school_folder}"
- grade_folder: "{grade_folder}"
- section_folder: "{section_folder}"
- extraction_date: "{datetime.now().strftime('%Y-%m-%d')}"

{extraction_rules}"""

            # Call Claude API with vision - with retry logic
            for attempt in range(max_retries):
                try:
                    message = self.client.messages.create(
                        model="claude-sonnet-4-5-20250929",
                        max_tokens=16000,
                        temperature=0,
                        messages=[{
                            "role": "user",
                            "content": images + [{"type": "text", "text": prompt}]
                        }]
                    )

                    # Extract JSON from response
                    response_text = message.content[0].text

                    # Try to extract JSON from the response
                    json_match = re.search(r'\{[\s\S]*\}', response_text)
                    if json_match:
                        json_str = json_match.group(0)
                        survey_data = json.loads(json_str)
                        return survey_data
                    else:
                        print(f"No JSON found in response for {pdf_path}")
                        print(f"Response: {response_text[:500]}")
                        return None

                except anthropic.RateLimitError as e:
                    wait_time = (2 ** attempt) * 5  # Exponential backoff: 5s, 10s, 20s
                    print(f"⚠️  Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    if attempt == max_retries - 1:
                        print(f"❌ Rate limit exceeded after {max_retries} attempts")
                        raise
                except anthropic.APIStatusError as e:
                    if e.status_code == 429:  # Another form of rate limiting
                        wait_time = (2 ** attempt) * 5
                        print(f"⚠️  Rate limit (429). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        if attempt == max_retries - 1:
                            raise
                    else:
                        raise  # Re-raise other API errors immediately

        except anthropic.AuthenticationError as e:
            print(f"❌ Authentication error: Invalid API key")
            print(f"   Error: {e}")
            return None
        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def save_survey_json(self, survey_data: Dict, output_path: str) -> bool:
        """Save survey data to JSON file."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(survey_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving JSON to {output_path}: {e}")
            return False


def find_pending_pdfs(base_dir: str, force: bool = False) -> List[Tuple[str, str]]:
    """Find all PDFs that don't have a corresponding _2d_attemp.json (unless force=True)."""
    base_path = Path(base_dir)
    pending = []

    for pdf_file in base_path.rglob("*.pdf"):
        json_file = pdf_file.parent / f"{pdf_file.stem}_2d_attemp.json"
        if force or not json_file.exists():
            pending.append((str(pdf_file), str(json_file)))

    return pending


def _make_extractor(api_key: Optional[str]) -> "SurveyExtractor":
    try:
        return SurveyExtractor(api_key=api_key)
    except ValueError as e:
        print(f"\nError: {e}")
        print("Set ANTHROPIC_API_KEY or pass --api-key.")
        sys.exit(1)


def _run_batch(extractor: "SurveyExtractor", pending: List[Tuple[str, str]], delay: float):
    success_count = 0
    error_count = 0

    for i, (pdf_path, json_path) in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] Processing: {Path(pdf_path).name}")

        survey_data = extractor.extract_survey_data(pdf_path)

        if survey_data:
            if extractor.save_survey_json(survey_data, json_path):
                print(f"✓ Saved: {Path(json_path).name}")
                success_count += 1
            else:
                print(f"✗ Failed to save JSON")
                error_count += 1
        else:
            print(f"✗ Failed to extract data")
            error_count += 1

        if i < len(pending) and delay > 0:
            time.sleep(delay)

        if i % 10 == 0:
            print(f"\n--- Progress: {i}/{len(pending)} ({i/len(pending)*100:.1f}%) ---")
            print(f"    Success: {success_count}, Errors: {error_count}")

    print("\n" + "=" * 70)
    print(f"Total: {len(pending)}  |  Success: {success_count}  |  Errors: {error_count}")
    if pending:
        print(f"Success rate: {success_count/len(pending)*100:.1f}%")


def process_single_survey(pdf_path: str, api_key: Optional[str] = None, force: bool = False):
    """Process a single PDF file."""
    pdf = Path(pdf_path)
    if not pdf.exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    json_path = pdf.parent / f"{pdf.stem}_2d_attemp.json"

    if not force and json_path.exists():
        print(f"Already processed: {json_path.name}  (use --force to reprocess)")
        return

    print("=" * 70)
    print(f"Processing single file: {pdf.name}")
    print("=" * 70)

    extractor = _make_extractor(api_key)
    survey_data = extractor.extract_survey_data(pdf_path)

    if survey_data:
        if extractor.save_survey_json(survey_data, str(json_path)):
            print(f"\n✓ Saved: {json_path.name}")
        else:
            print("\n✗ Failed to save JSON")
    else:
        print("\n✗ Failed to extract data")


def process_all_surveys(base_dir: str, api_key: Optional[str] = None,
                        max_files: Optional[int] = None, delay: float = 1.0,
                        force: bool = False):
    """Process all pending survey PDFs in a directory."""
    print("=" * 70)
    print("Survey PDF Extraction")
    print("=" * 70)

    print("\nScanning for pending PDFs...")
    pending = find_pending_pdfs(base_dir, force=force)

    if not pending:
        print("No pending PDFs found. All surveys have been processed!")
        return

    print(f"Found {len(pending)} PDFs to process")

    if max_files:
        pending = pending[:max_files]
        print(f"Limiting to first {max_files} files")

    extractor = _make_extractor(api_key)

    print("\nStarting processing...")
    print("-" * 70)

    _run_batch(extractor, pending, delay)


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Extract survey data from PDF files to JSON format.\n"
                    "Pass a file to process one, a folder to process all pending, "
                    "or nothing to process all pending in ./digitalizadas.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target",
        nargs="?",
        default="/Users/sergiotorres/code/focus/digitalizadas",
        help="PDF file or directory to process (default: ./digitalizadas)",
    )
    parser.add_argument("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY)")
    parser.add_argument("--max-files", type=int, help="Max files to process (directory mode)")
    parser.add_argument("--test", action="store_true", help="Process only 3 files (directory mode)")
    parser.add_argument("--delay", type=float, default=1.0,
                        help="Seconds between requests (default: 1.0)")
    parser.add_argument("--force", action="store_true",
                        help="Reprocess even if JSON already exists")

    args = parser.parse_args()

    if args.test:
        args.max_files = 3
        print("TEST MODE — processing only 3 files")

    if os.path.isfile(args.target):
        process_single_survey(args.target, api_key=args.api_key, force=args.force)
    elif os.path.isdir(args.target):
        process_all_surveys(
            base_dir=args.target,
            api_key=args.api_key,
            max_files=args.max_files,
            delay=args.delay,
            force=args.force,
        )
    else:
        print(f"Error: Not a valid file or directory: {args.target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
