#!/usr/bin/env python3
"""
Survey PDF Extraction Script — Gemma 4 26B via Cloudflare Workers AI
Processes PDF survey files and extracts responses to JSON format.
Uses the Cloudflare Workers AI REST API with the OpenAI-compatible messages format.

USAGE:
  python3 scripts/extraction/extract_with_cloudflare_llava.py [TARGET] [OPTIONS]

TARGET (optional):
  - Path to a single PDF file  → processes only that file
  - Path to a folder           → recursively finds all *.pdf files inside it
  - If omitted                 → defaults to ./digitalizadas

OPTIONS:
  --api-key KEY        Override the Cloudflare API key
  --base-url URL       Override the Cloudflare base URL
  --config-path PATH   Credentials JSON (default: ~/.config/opencode/config.json)
  --max-pages N        Max PDF pages to send (default: all).
  --dpi DPI            Resolution for PDF→image conversion (default: 100).
  --simple-prompt      DIAGNOSTIC ONLY. Send a tiny "Describe this image" prompt.
  --compact-prompt     Alias for default mode (uses extraction_rules.md).
  --max-files N        Process at most N PDFs (folder mode)
  --test               Shortcut for --max-files 3 (quick smoke test)
  --delay SECONDS      Seconds to wait between requests (default: 1.0)
  --force              Re-process even if a *_llava.json already exists

OUTPUT:
  For each PDF processed, a JSON file is saved in the SAME folder as the PDF:
    {pdf_name}_llava.json

CREDENTIALS (resolved in this order):
  1. --api-key / --base-url CLI flags
  2. CLOUDFLARE_API_KEY / CLOUDFLARE_BASE_URL environment variables
  3. ~/.config/opencode/config.json  (provider.cloudflare.options.apiKey / baseURL)
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
    import requests
except ImportError:
    print("Error: requests library not found. Installing...")
    os.system("pip3 install requests")
    import requests


DEFAULT_CONFIG_PATH = "/Users/sergiotorres/.config/opencode/config.json"
DEFAULT_BASE_DIR = "/Users/sergiotorres/code/focus/digitalizadas"
MODEL_ID = "@cf/google/gemma-4-26b-a4b-it"
OUTPUT_SUFFIX = "_llava.json"

def _build_split_prompts(rules: str, ctx: dict, mid: int) -> tuple:
    """
    Build two prompts that use extraction_rules.md as the authoritative guide,
    split so each half fits within LLaVA's 1,024-token output cap.

    Part 1 → metadata + responses for questions 1..mid
    Part 2 → responses array for questions mid+1..total_questions
    """
    total = ctx["total_questions"]
    task_context = (
        f"## Task Context\n"
        f'- survey_id: "{ctx["filename_without_ext"]}" — use this exact value\n'
        f'- grade_range: "{ctx["grade_range"]}" — use this exact value\n'
        f'- total_questions: {total}\n'
        f'- Scale 1 (Certainty) applies to questions 1–{ctx["scale_1_end"]}\n'
        f'- Scale 2 (Frequency) applies to questions {ctx["scale_2_start"]}–{total}\n'
        f'- extraction_date: "{ctx["extraction_date"]}"\n'
    )

    part1 = (
        f"{task_context}\n"
        f"{rules}\n\n"
        f"## Output scope for THIS call\n"
        f"Output ONLY valid JSON (no markdown fences) with:\n"
        f'- "metadata": all fields as defined above\n'
        f'- "responses": questions 1 to {mid} only\n'
        f"Stop after question {mid}. Do NOT output questions {mid+1}–{total}."
    )

    part2 = (
        f"{task_context}\n"
        f"{rules}\n\n"
        f"## Output scope for THIS call\n"
        f"Output ONLY a valid JSON array (no markdown fences, no metadata object) "
        f"with responses for questions {mid+1} to {total}.\n"
        f"Format: "
        f'[{{"question":"{mid+1}","answer":3,"notes":""}},'
        f'{{"question":"{mid+2}","answer":null,"notes":"Sin respuesta visible"}},...]\n'
        f"Include every question from {mid+1} to {total}."
    )

    return part1, part2


def _salvage_truncated_json(text: str) -> Optional[Dict]:
    """Attempt to recover a truncated JSON object by closing open brackets."""
    # Count unclosed braces/brackets and append the necessary closing chars
    closers = {"{": "}", "[": "]"}
    stack = []
    in_string = False
    escape_next = False
    for ch in text:
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch in ("{", "["):
            stack.append(closers[ch])
        elif ch in ("}", "]"):
            if stack and stack[-1] == ch:
                stack.pop()
    if not stack:
        return None  # nothing to close — parse would have succeeded already
    repaired = text.rstrip().rstrip(",") + "".join(reversed(stack))
    try:
        return json.loads(repaired)
    except json.JSONDecodeError:
        return None


class CloudflareLlavaExtractor:
    """Extracts survey data from PDFs using Cloudflare Workers AI (Gemma 4)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        config_path: str = DEFAULT_CONFIG_PATH,
    ):
        self.api_key, self.base_url = self._resolve_credentials(api_key, base_url, config_path)
        if not self.api_key:
            raise ValueError(
                "Cloudflare API key not found. "
                "Set CLOUDFLARE_API_KEY env var, pass --api-key, "
                f"or ensure {config_path} has provider.cloudflare.options.apiKey."
            )
        if not self.base_url:
            raise ValueError(
                "Cloudflare base URL not found. "
                "Set CLOUDFLARE_BASE_URL env var, pass --base-url, "
                f"or ensure {config_path} has provider.cloudflare.options.baseURL."
            )
        normalized = self.base_url.rstrip("/")
        if normalized.endswith("/v1"):
            normalized = normalized[:-3].rstrip("/")
        self.endpoint = f"{normalized}/run/{MODEL_ID}"
        print(f"Using endpoint: {self.endpoint}")

    @staticmethod
    def _resolve_credentials(
        api_key: Optional[str],
        base_url: Optional[str],
        config_path: str,
    ) -> Tuple[Optional[str], Optional[str]]:
        if api_key:
            return api_key, base_url

        api_key = os.environ.get("CLOUDFLARE_API_KEY")
        base_url = os.environ.get("CLOUDFLARE_BASE_URL")
        if api_key:
            return api_key, base_url

        cfg = Path(config_path)
        if cfg.exists():
            try:
                data = json.loads(cfg.read_text(encoding="utf-8"))
                opts = data.get("provider", {}).get("cloudflare", {}).get("options", {})
                api_key = opts.get("apiKey")
                base_url = opts.get("baseURL")
                if api_key:
                    return api_key, base_url
            except (json.JSONDecodeError, OSError):
                pass

        return None, None

    def pdf_to_base64_images(self, pdf_path: str, dpi: int = 100) -> List[str]:
        """Convert PDF pages to base64 JPEG strings for Gemini inline_data."""
        import io
        import base64
        try:
            images = pdf2image.convert_from_path(pdf_path, dpi=dpi)
            result = []
            for image in images:
                if image.mode != "RGB":
                    image = image.convert("RGB")
                buf = io.BytesIO()
                image.save(buf, format="JPEG", quality=85)
                result.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
            return result
        except Exception as e:
            print(f"Error converting PDF to images: {e}")
            return []

    def extract_survey_data(
        self,
        pdf_path: str,
        dpi: int = 100,
        max_pages: Optional[int] = 1,
        simple_prompt: bool = False,
        compact_prompt: bool = False,
        max_retries: int = 3,
    ) -> Optional[Dict]:
        """Extract survey data from a PDF using Gemini via Cloudflare AI Gateway."""
        try:
            print(f"Processing: {pdf_path}")

            b64_images = self.pdf_to_base64_images(pdf_path, dpi=dpi)
            if not b64_images:
                print(f"  ❌  Failed to convert PDF to images")
                return None

            total_pages = len(b64_images)
            if max_pages is not None and total_pages > max_pages:
                print(f"  Sending {max_pages}/{total_pages} pages (--max-pages {max_pages})")
                b64_images = b64_images[:max_pages]
            else:
                print(f"  Sending all {total_pages} page(s)")

            filename_without_ext = Path(pdf_path).stem
            folder_name = Path(pdf_path).parent.name
            folder_match = re.match(r"^(\d)([A-Z])$", folder_name)
            if folder_match:
                grade_folder = folder_match.group(1) + "°"
                section_folder = folder_match.group(2)
            else:
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

            ctx = dict(
                filename_without_ext=filename_without_ext,
                grade_range=grade_range,
                total_questions=total_questions,
                scale_1_end=scale_1_end,
                scale_2_start=scale_2_start,
                extraction_date=datetime.now().strftime("%Y-%m-%d"),
            )

            if simple_prompt:
                prompt_text = (
                    "Describe what you see in this image in detail. "
                    "Focus on any text, numbers, checkboxes, marks, and layout."
                )
                print("  🧪  DIAGNOSTIC MODE: simple prompt")
            else:
                # Both --compact-prompt and default use extraction_rules.md.
                # Gemini 2.5 Flash has a large context + output window — no split needed.
                rules_path = (
                    Path(__file__).parent.parent.parent / ".claude" / "extraction_rules.md"
                )
                extraction_rules = rules_path.read_text(encoding="utf-8")
                prompt_text = (
                    f'## Task Context\n'
                    f'- survey_id: "{filename_without_ext}" — use this exact value\n'
                    f'- grade_range: "{grade_range}" — use this exact value\n'
                    f'- total_questions: {total_questions}\n'
                    f'- Scale 1 (Certainty) applies to questions 1–{scale_1_end}\n'
                    f'- Scale 2 (Frequency) applies to questions {scale_2_start}–{total_questions}\n'
                    f'- extraction_date: "{ctx["extraction_date"]}"\n\n'
                    f'{extraction_rules}'
                )
                print("  📄  Using extraction_rules.md")

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }
            raw_text = self._send_one_request(
                headers, b64_images, prompt_text, max_retries
            )
            if raw_text is None:
                return None

            if simple_prompt:
                return {
                    "raw_response": raw_text,
                    "model": MODEL_ID,
                    "prompt_mode": "simple",
                    "pdf_path": pdf_path,
                    "extraction_date": ctx["extraction_date"],
                }

            survey_data = self._parse_json_from_text(raw_text, "gemini", total_questions)
            if survey_data and survey_data.get("metadata") is not None:
                survey_data["metadata"].update({
                    "survey_id": filename_without_ext,
                    "grade_range": grade_range,
                    "extraction_date": ctx["extraction_date"],
                    "total_questions": total_questions,
                    "school_name": Path(pdf_path).parent.parent.name,
                    "grade_folder": Path(pdf_path).parent.name,
                })
            return survey_data

        except Exception as e:
            print(f"Error processing {pdf_path}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _send_one_request(
        self,
        headers: Dict,
        b64_images: List[str],
        prompt_text: str,
        max_retries: int,
    ) -> Optional[str]:
        """Send image(s) + prompt to Cloudflare Workers AI (Gemma). Returns response text."""
        # Gemma uses the OpenAI-compatible messages format.
        # Images are passed as image_url content parts with a base64 data URI.
        image_parts = [
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            }
            for b64 in b64_images
        ]
        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": image_parts + [{"type": "text", "text": prompt_text}],
                }
            ],
            "max_completion_tokens": 8192,
        }

        print(f"  → Sending {len(b64_images)} image(s) to {MODEL_ID} …", end="", flush=True)
        for attempt in range(max_retries):
            try:
                resp = requests.post(
                    self.endpoint, headers=headers, json=payload, timeout=180
                )
                resp.raise_for_status()
                data = resp.json()

                # Workers AI wraps in {"result": {...}, "success": true}
                result = data.get("result", data)

                # OpenAI-compatible shape: choices[0].message.content
                if "choices" in result:
                    try:
                        text = result["choices"][0]["message"]["content"]
                    except (KeyError, IndexError):
                        print(f" ❌  unexpected choices shape: {json.dumps(result)[:400]}")
                        return None
                # Fallback: flat response key (some CF models)
                elif "response" in result:
                    text = result["response"]
                else:
                    print(f" ❌  unexpected shape: {json.dumps(data)[:400]}")
                    return None

                if not text:
                    print(f" ❌  empty text in response")
                    return None

                print(f" ✓  {len(text)} chars")
                return text

            except requests.exceptions.HTTPError as e:
                status = e.response.status_code if e.response else 0
                if status == 429:
                    wait = (2 ** attempt) * 5
                    print(f"\n  ⚠️  429 rate limit — waiting {wait}s (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait)
                    if attempt == max_retries - 1:
                        raise
                else:
                    body = e.response.text[:400] if e.response else str(e)
                    print(f"\n  ❌  HTTP {status}: {body}")
                    raise
            except requests.exceptions.RequestException as e:
                print(f"\n  ⚠️  request error: {e}")
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)
        return None

    def _parse_json_from_text(
        self, cleaned: str, mode_label: str, total_questions: int
    ) -> Optional[Dict]:
        """Extract and parse a JSON object or array from model output text."""
        # Try JSON object first (full survey or part-1)
        obj_match = re.search(r"\{[\s\S]*\}", cleaned)
        if obj_match:
            candidate = obj_match.group(0)
            try:
                data = json.loads(candidate)
                q_count = len(data.get("responses", []))
                if q_count:
                    print(f"  [{mode_label}] ✓  {q_count} responses")
                return data
            except json.JSONDecodeError:
                salvaged = _salvage_truncated_json(candidate)
                if salvaged:
                    q_count = len(salvaged.get("responses", []))
                    print(f"  [{mode_label}] ⚠️  truncated JSON salvaged — {q_count} responses")
                    return salvaged
                print(f"  [{mode_label}] ❌  JSON parse failed. Output preview:")
                print(f"  {cleaned[:600]}")
                return None

        # Try bare array (part-2 prompt returns only a responses array)
        arr_match = re.search(r"\[[\s\S]*\]", cleaned)
        if arr_match:
            candidate = arr_match.group(0)
            try:
                arr = json.loads(candidate)
                print(f"  [{mode_label}] ✓  {len(arr)} responses (array)")
                return arr  # caller handles list vs dict
            except json.JSONDecodeError:
                pass

        print(f"  [{mode_label}] ❌  no JSON found. Output preview:")
        print(f"  {cleaned[:400]}")
        return None

    def save_survey_json(self, survey_data: Dict, output_path: str) -> bool:
        """Save survey data to JSON file."""
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(survey_data, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"Error saving JSON to {output_path}: {e}")
            return False


def find_pending_pdfs(base_dir: str, force: bool = False) -> List[Tuple[str, str]]:
    """Find all PDFs that don't have a corresponding _llava.json (unless force=True)."""
    base_path = Path(base_dir)
    pending = []
    for pdf_file in base_path.rglob("*.pdf"):
        json_file = pdf_file.parent / f"{pdf_file.stem}{OUTPUT_SUFFIX}"
        if force or not json_file.exists():
            pending.append((str(pdf_file), str(json_file)))
    return pending


def _make_extractor(api_key: Optional[str], base_url: Optional[str] = None, config_path: str = DEFAULT_CONFIG_PATH) -> CloudflareLlavaExtractor:
    try:
        return CloudflareLlavaExtractor(api_key=api_key, base_url=base_url, config_path=config_path)
    except ValueError as e:
        print(f"\nError: {e}")
        sys.exit(1)


def _run_batch(
    extractor: CloudflareLlavaExtractor,
    pending: List[Tuple[str, str]],
    delay: float,
    max_pages: Optional[int],
    dpi: int,
    simple_prompt: bool,
    compact_prompt: bool,
):
    success_count = 0
    error_count = 0

    for i, (pdf_path, json_path) in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] Processing: {Path(pdf_path).name}")

        survey_data = extractor.extract_survey_data(
            pdf_path,
            dpi=dpi,
            max_pages=max_pages,
            simple_prompt=simple_prompt,
            compact_prompt=compact_prompt,
        )

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


def process_single_survey(
    pdf_path: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    config_path: str = DEFAULT_CONFIG_PATH,
    dpi: int = 100,
    max_pages: Optional[int] = None,
    simple_prompt: bool = False,
    compact_prompt: bool = False,
    force: bool = False,
):
    """Process a single PDF file."""
    pdf = Path(pdf_path)
    if not pdf.exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    json_path = pdf.parent / f"{pdf.stem}{OUTPUT_SUFFIX}"

    if not force and json_path.exists():
        print(f"Already processed: {json_path.name}  (use --force to reprocess)")
        return

    print("=" * 70)
    print(f"Processing single file: {pdf.name}")
    print("=" * 70)

    extractor = _make_extractor(api_key, base_url, config_path)
    survey_data = extractor.extract_survey_data(
        pdf_path,
        dpi=dpi,
        max_pages=max_pages,
        simple_prompt=simple_prompt,
        compact_prompt=compact_prompt,
    )

    if survey_data:
        if extractor.save_survey_json(survey_data, str(json_path)):
            print(f"\n✓ Saved: {json_path.name}")
        else:
            print("\n✗ Failed to save JSON")
    else:
        print("\n✗ Failed to extract data")


def process_all_surveys(
    base_dir: str,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
    config_path: str = DEFAULT_CONFIG_PATH,
    max_files: Optional[int] = None,
    dpi: int = 100,
    max_pages: Optional[int] = None,
    simple_prompt: bool = False,
    compact_prompt: bool = False,
    delay: float = 1.0,
    force: bool = False,
):
    """Process all pending survey PDFs in a directory."""
    print("=" * 70)
    print(f"Survey PDF Extraction — {MODEL_ID} via Cloudflare AI Gateway")
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

    extractor = _make_extractor(api_key, base_url, config_path)

    print("\nStarting processing...")
    print("-" * 70)

    _run_batch(
        extractor,
        pending,
        delay,
        max_pages,
        dpi,
        simple_prompt,
        compact_prompt,
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description=(
            f"Extract survey data from PDF files to JSON using {MODEL_ID} "
            "on Cloudflare Workers AI.\n"
            "Credentials read from ~/.config/opencode/config.json by default."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=DEFAULT_BASE_DIR,
        help="PDF file or directory to process (default: ./digitalizadas)",
    )
    parser.add_argument("--api-key", help="Cloudflare API key (or set CLOUDFLARE_API_KEY)")
    parser.add_argument("--base-url", help="Cloudflare base URL (or set CLOUDFLARE_BASE_URL)")
    parser.add_argument("--config-path", default=DEFAULT_CONFIG_PATH,
                        help="Path to opencode config JSON with Cloudflare credentials")
    parser.add_argument("--max-files", type=int, help="Max files to process (directory mode)")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Max PDF pages to send (default: all). Gemini supports multiple images per request.",
    )
    parser.add_argument(
        "--dpi",
        type=int,
        default=100,
        help="DPI for PDF-to-image conversion (default: 100)",
    )
    parser.add_argument(
        "--simple-prompt",
        action="store_true",
        help="Diagnostic mode: send a tiny describe-image prompt to verify the pipeline.",
    )
    parser.add_argument(
        "--compact-prompt",
        action="store_true",
        help="Alias for default mode — uses extraction_rules.md (kept for backward compat).",
    )
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
        process_single_survey(
            args.target,
            api_key=args.api_key,
            base_url=args.base_url,
            config_path=args.config_path,
            dpi=args.dpi,
            max_pages=args.max_pages,
            simple_prompt=args.simple_prompt,
            compact_prompt=args.compact_prompt,
            force=args.force,
        )
    elif os.path.isdir(args.target):
        process_all_surveys(
            base_dir=args.target,
            api_key=args.api_key,
            base_url=args.base_url,
            config_path=args.config_path,
            max_files=args.max_files,
            dpi=args.dpi,
            max_pages=args.max_pages,
            simple_prompt=args.simple_prompt,
            compact_prompt=args.compact_prompt,
            delay=args.delay,
            force=args.force,
        )
    else:
        print(f"Error: Not a valid file or directory: {args.target}")
        sys.exit(1)


if __name__ == "__main__":
    main()
