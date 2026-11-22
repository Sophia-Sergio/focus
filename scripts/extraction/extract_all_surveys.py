#!/usr/bin/env python3
"""
Survey PDF Extraction Script
Processes PDF survey files and extracts responses to JSON format.

Usage examples:
    # Batches API (50% cheaper; results arrive asynchronously, usually < 1 hour)
    python3 extract_all_surveys.py /path/to/pdfs --batch --wait     # submit and wait
    python3 extract_all_surveys.py /path/to/pdfs --batch            # submit only
    python3 extract_all_surveys.py /path/to/pdfs --collect          # fetch finished results

    # Process all pending PDFs in the default directory (./digitalizadas)
    python3 extract_all_surveys.py

    # Process all pending PDFs in a specific directory
    python3 extract_all_surveys.py /path/to/digitalizadas

    # Process a single PDF file
    python3 extract_all_surveys.py /path/to/survey.pdf

    # Test run — process only 3 files
    python3 extract_all_surveys.py --test

    # Reprocess files that already have JSON output
    python3 extract_all_surveys.py --force

    # Limit to first N files
    python3 extract_all_surveys.py --max-files 10

    # Set delay between API requests (default: 1.0s)
    python3 extract_all_surveys.py --delay 2.0

    # Pass API key explicitly (overrides .env)
    python3 extract_all_surveys.py --api-key sk-ant-...

API key is loaded automatically from scripts/.env (ANTHROPIC_API_KEY=...).
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

try:
    from dotenv import load_dotenv
except ImportError:
    os.system("pip3 install python-dotenv")
    from dotenv import load_dotenv

# Load .env from scripts/ directory (one level up from this file)
load_dotenv(Path(__file__).parent.parent / ".env")


MODEL_ID = "claude-sonnet-4-5-20250929"

# USD per million tokens (Claude Sonnet 4.5), standard (synchronous) API. Update if the model changes.
# Batch API = 50% off all of these. Prompt-cache writes cost 1.25x input (5-min TTL) or 2x (1-hour TTL);
# cache reads cost 0.1x input.
PRICING_PER_MTOK = {
    "input": 3.00,
    "output": 15.00,
    "cache_write_5m": 3.75,
    "cache_write_1h": 6.00,
    "cache_read": 0.30,
}
BATCH_DISCOUNT = 0.5


def build_usage(usage, model: str = MODEL_ID, batch: bool = False) -> Dict:
    """Turn an Anthropic `usage` object into a token/cost summary (batch pricing if batch=True)."""
    input_tokens = getattr(usage, "input_tokens", 0) or 0
    output_tokens = getattr(usage, "output_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cc = getattr(usage, "cache_creation", None)
    w5 = getattr(cc, "ephemeral_5m_input_tokens", None) if cc else None
    w1 = getattr(cc, "ephemeral_1h_input_tokens", None) if cc else None
    if w5 is None and w1 is None:          # no TTL breakdown: assume the 5-minute rate
        w5, w1 = cache_write, 0
    cost = (
        input_tokens * PRICING_PER_MTOK["input"]
        + output_tokens * PRICING_PER_MTOK["output"]
        + (w5 or 0) * PRICING_PER_MTOK["cache_write_5m"]
        + (w1 or 0) * PRICING_PER_MTOK["cache_write_1h"]
        + cache_read * PRICING_PER_MTOK["cache_read"]
    ) / 1_000_000
    if batch:
        cost *= BATCH_DISCOUNT
    return {
        "model": model,
        "batch": batch,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_creation_input_tokens": cache_write,
        "cache_read_input_tokens": cache_read,
        "total_tokens": input_tokens + output_tokens + cache_write + cache_read,
        "cost_usd": round(cost, 6),
    }


def validate_rut(rut: str) -> bool:
    """Validate a Chilean RUT using the official modulo-11 algorithm."""
    if not rut:
        return False
    clean = rut.replace(".", "").replace("-", "").upper().strip()
    if len(clean) < 2:
        return False
    body, dv = clean[:-1], clean[-1]
    if not body.isdigit():
        return False
    suma = 0
    multiplo = 2
    for digit in reversed(body):
        suma += int(digit) * multiplo
        multiplo = multiplo + 1 if multiplo < 7 else 2
    remainder = suma % 11
    result = 11 - remainder
    expected = "0" if result == 11 else ("K" if result == 10 else str(result))
    return dv == expected


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

    def prepare_request(self, pdf_path: str, cache_ttl: Optional[str] = None) -> Optional[Tuple[Dict, Dict]]:
        """Build the Messages API params for one PDF -> (params, ctx), or None if unreadable.

        The (identical for every survey) extraction rules go in a cached system block placed before
        the images; only the page images and the small task context vary per survey.
        cache_ttl: None/"5m" (default) or "1h" (recommended for batches).
        """
        images = self.pdf_to_base64_images(pdf_path)
        if not images:
            print(f"Failed to convert PDF to images: {pdf_path}")
            return None

        filename_without_ext = Path(pdf_path).stem

        # Folder name is the single source of truth for grade/section
        folder_name = Path(pdf_path).parent.name
        folder_match = re.match(r'^(\d)([A-Z])$', folder_name)
        grade_folder = (folder_match.group(1) + "°") if folder_match else None

        if grade_folder in ("6°", "7°"):
            grade_range, total_questions, scale_1_end, scale_2_start = "6° - 7°", 68, 49, 50
        else:
            grade_range, total_questions, scale_1_end, scale_2_start = "4° - 5°", 50, 31, 32

        rules_path = Path(__file__).parent.parent.parent / ".claude" / "extraction_rules.md"
        extraction_rules = rules_path.read_text(encoding="utf-8")

        # NOTE: the survey_id/filename is deliberately NOT given to the model (Python injects it). When it was,
        # the model copied it into `folio` for scans that have no folio printed.
        context = f"""## Task Context
- grade_range: "{grade_range}" — use this exact value, do NOT read it from the PDF
- total_questions: {total_questions}
- Scale 1 (Certainty) applies to questions 1–{scale_1_end}
- Scale 2 (Frequency) applies to questions {scale_2_start}–{total_questions}
- extraction_date: "{datetime.now().strftime('%Y-%m-%d')}"

The extraction rules are in the system prompt. Extract the survey shown in the images above."""

        cache_control = {"type": "ephemeral"}
        if cache_ttl and cache_ttl != "5m":
            cache_control["ttl"] = cache_ttl
        params = {
            "model": MODEL_ID,
            "max_tokens": 16000,
            "temperature": 0,
            "system": [{"type": "text", "text": extraction_rules, "cache_control": cache_control}],
            "messages": [{"role": "user", "content": images + [{"type": "text", "text": context}]}],
        }
        ctx = {"pdf_path": str(pdf_path), "survey_id": filename_without_ext, "grade_range": grade_range,
               "total_questions": total_questions}
        return params, ctx

    @staticmethod
    def context_for(pdf_path: str) -> Dict:
        """The per-survey context (same rules as prepare_request) without rendering images."""
        grade = re.match(r'^(\d)([A-Z])$', Path(pdf_path).parent.name)
        wide = bool(grade) and grade.group(1) in ("6", "7")
        return {"pdf_path": str(pdf_path), "survey_id": Path(pdf_path).stem,
                "grade_range": "6° - 7°" if wide else "4° - 5°", "total_questions": 68 if wide else 50}

    @staticmethod
    def build_survey_data(response_text: str, ctx: Dict, usage, batch: bool = False) -> Optional[Dict]:
        """Parse the model's JSON and inject everything Python already knows."""
        pdf_path = ctx["pdf_path"]
        filename_without_ext = ctx["survey_id"]
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if not json_match:
            print(f"No JSON found in response for {pdf_path}")
            print(f"Response: {response_text[:500]}")
            return None
        survey_data = json.loads(json_match.group(0))
        meta = survey_data.get("metadata", {})
        meta["survey_id"] = filename_without_ext
        meta["grade_range"] = ctx["grade_range"]
        meta["extraction_date"] = datetime.now().strftime("%Y-%m-%d")
        meta["total_questions"] = ctx["total_questions"]
        meta["school_name"] = Path(pdf_path).parent.parent.name
        meta["grade_folder"] = Path(pdf_path).parent.name
        # Folio check: the model only transcribes it; Python derives the flags
        folio = meta.get("folio")
        folio = re.sub(r"\s+", "", str(folio)).upper() if folio else None
        meta["folio"] = folio
        meta["folio_printed"] = folio is not None
        meta["folio_matches_survey_id"] = (folio == filename_without_ext.upper()) if folio else None
        # Inject valid_rut right after student_run
        if "student_run" in meta:
            new_meta = {}
            for k, v in meta.items():
                new_meta[k] = v
                if k == "student_run":
                    new_meta["valid_rut"] = validate_rut(str(v))
            survey_data["metadata"] = new_meta
        else:
            survey_data["metadata"] = meta
        survey_data["extraction_usage"] = build_usage(usage, batch=batch)
        return survey_data

    def extract_survey_data(self, pdf_path: str, max_retries: int = 3) -> Optional[Dict]:
        """Extract survey data from a PDF file (synchronous API) with retry logic."""
        try:
            print(f"Processing: {pdf_path}")
            prepared = self.prepare_request(pdf_path)
            if not prepared:
                return None
            params, ctx = prepared
            print(f"  Folder: {Path(pdf_path).parent.name} → {ctx['total_questions']} questions")

            for attempt in range(max_retries):
                try:
                    message = self.client.messages.create(**params)
                    return self.build_survey_data(message.content[0].text, ctx, message.usage)
                except anthropic.RateLimitError:
                    wait_time = (2 ** attempt) * 5  # Exponential backoff: 5s, 10s, 20s
                    print(f"⚠️  Rate limit hit. Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                    time.sleep(wait_time)
                    if attempt == max_retries - 1:
                        print(f"❌ Rate limit exceeded after {max_retries} attempts")
                        raise
                except anthropic.APIStatusError as e:
                    if e.status_code == 429:
                        wait_time = (2 ** attempt) * 5
                        print(f"⚠️  Rate limit (429). Waiting {wait_time}s before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        if attempt == max_retries - 1:
                            raise
                    else:
                        raise

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


# Real surveys are named like 46654A1 (digits + section letter + digits); after
# rename_by_folio.py they carry their folio, which may also be purely numeric.
# Everything else in a course folder (Lista-de-curso, Nomina-de-estudiantes,
# Reporte-por-curso, Planilla, "...-Una-hoja-extra", ...) is not a survey.
SURVEY_FILENAME_RE = re.compile(r"^(\d+[A-Z]\d+|\d{5,})$")  # 46654A7, or a numeric folio


def is_survey_pdf(pdf_path) -> bool:
    return bool(SURVEY_FILENAME_RE.match(Path(pdf_path).stem))


def find_pending_pdfs(base_dir: str, force: bool = False) -> List[Tuple[str, str]]:
    """Find all PDFs that don't have a corresponding .json (unless force=True)."""
    base_path = Path(base_dir)
    pending = []

    for pdf_file in base_path.rglob("*.pdf"):
        if not is_survey_pdf(pdf_file):
            continue
        json_file = pdf_file.parent / f"{pdf_file.stem}.json"
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
    total_tokens = 0
    total_cost = 0.0

    for i, (pdf_path, json_path) in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] Processing: {Path(pdf_path).name}")

        survey_data = extractor.extract_survey_data(pdf_path)

        if survey_data:
            if extractor.save_survey_json(survey_data, json_path):
                u = survey_data.get("extraction_usage", {})
                total_tokens += u.get("total_tokens", 0)
                total_cost += u.get("cost_usd", 0.0)
                print(f"✓ Saved: {Path(json_path).name}  "
                      f"({u.get('input_tokens', 0)} in / {u.get('output_tokens', 0)} out tokens, "
                      f"${u.get('cost_usd', 0.0):.4f})")
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
    print(f"Total tokens: {total_tokens:,}  |  Total cost: ${total_cost:.4f}")


# ---------------------------------------------------------------------------
# Message Batches API mode: 50% cheaper, asynchronous (usually done within an hour).
#   --batch    submit pending PDFs (split into batches under the 256 MB request limit)
#   --collect  fetch finished batches and write the JSONs
#   --wait     with --batch: keep collecting until everything is done
# Submitted batches are recorded in <dir>/.extract_batches.json so runs can be resumed.
# ---------------------------------------------------------------------------
BATCH_STATE = ".extract_batches.json"
BATCH_MAX_BYTES = 180 * 1024 * 1024      # API limit is 256 MB per batch; keep headroom
BATCH_MAX_REQUESTS = 5000


def _state_path(base_dir: str) -> Path:
    base = Path(base_dir)
    return (base if base.is_dir() else base.parent) / BATCH_STATE


def _load_state(base_dir: str) -> Dict:
    path = _state_path(base_dir)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"next_id": 1, "batches": []}


def _save_state(base_dir: str, state: Dict):
    _state_path(base_dir).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def submit_batches(extractor: "SurveyExtractor", base_dir: str, pending: List[Tuple[str, str]]) -> int:
    """Submit pending PDFs as one or more batches. Returns the number of PDFs submitted."""
    state = _load_state(base_dir)
    in_flight = {path for b in state["batches"] if not b.get("collected") for path in b["items"].values()}
    todo = [(pdf, js) for pdf, js in pending if pdf not in in_flight]
    if len(todo) < len(pending):
        print(f"Skipping {len(pending) - len(todo)} PDFs already in a submitted, uncollected batch")
    if not todo:
        print("Nothing to submit.")
        return 0

    submitted = 0
    chunk: List[Dict] = []
    items: Dict[str, str] = {}
    size = 0

    def flush():
        nonlocal chunk, items, size, submitted
        if not chunk:
            return
        batch = extractor.client.messages.batches.create(requests=chunk)
        state["batches"].append({"id": batch.id, "created": datetime.now().isoformat(timespec="seconds"),
                                 "items": items, "collected": False})
        _save_state(base_dir, state)
        submitted += len(chunk)
        print(f"  submitted batch {batch.id}: {len(chunk)} surveys, {size/1e6:.0f} MB "
              f"({submitted}/{len(todo)} total)", flush=True)
        chunk, items, size = [], {}, 0

    for i, (pdf, _json) in enumerate(todo, 1):
        prepared = extractor.prepare_request(pdf, cache_ttl="1h")
        if not prepared:
            continue
        params, _ctx = prepared
        req_size = sum(len(b["source"]["data"]) for b in params["messages"][0]["content"] if b["type"] == "image")
        if chunk and (size + req_size > BATCH_MAX_BYTES or len(chunk) >= BATCH_MAX_REQUESTS):
            flush()
        cid = f"s{state['next_id']:07d}"
        state["next_id"] += 1
        chunk.append({"custom_id": cid, "params": params})
        items[cid] = pdf
        size += req_size
        if i % 20 == 0:
            print(f"  prepared {i}/{len(todo)}", flush=True)
    flush()
    return submitted


def collect_batches(extractor: "SurveyExtractor", base_dir: str, force: bool = False) -> Tuple[int, bool]:
    """Write JSONs for finished batches. Returns (saved_count, all_done)."""
    state = _load_state(base_dir)
    saved = failed = 0
    tokens, cost = 0, 0.0
    all_done = True
    for b in state["batches"]:
        if b.get("collected"):
            continue
        info = extractor.client.messages.batches.retrieve(b["id"])
        if info.processing_status != "ended":
            c = info.request_counts
            print(f"  {b['id']}: {info.processing_status} (processing={c.processing}, succeeded={c.succeeded}, "
                  f"errored={c.errored})")
            all_done = False
            continue
        for result in extractor.client.messages.batches.results(b["id"]):
            pdf = b["items"].get(result.custom_id)
            if pdf is None:
                continue
            json_path = Path(pdf).with_suffix(".json")
            if result.result.type != "succeeded":
                failed += 1
                print(f"  ✗ {Path(pdf).name}: {result.result.type}")
                continue
            if json_path.exists() and not force:
                continue
            message = result.result.message
            ctx = extractor.context_for(pdf)
            try:
                data = extractor.build_survey_data(message.content[0].text, ctx, message.usage, batch=True)
            except Exception as e:
                failed += 1
                print(f"  ✗ {Path(pdf).name}: {e}")
                continue
            if data and extractor.save_survey_json(data, str(json_path)):
                u = data["extraction_usage"]
                tokens += u["total_tokens"]
                cost += u["cost_usd"]
                saved += 1
            else:
                failed += 1
        b["collected"] = True
        b["failed"] = failed
        _save_state(base_dir, state)
        print(f"  collected {b['id']}")
    print(f"Collected: saved={saved} failed={failed}  tokens={tokens:,}  cost=${cost:.4f} (batch pricing)")
    if failed:
        print("Failed/expired surveys have no JSON; run --batch again to resubmit them.")
    return saved, all_done


def process_single_survey(pdf_path: str, api_key: Optional[str] = None, force: bool = False):
    """Process a single PDF file."""
    pdf = Path(pdf_path)
    if not pdf.exists():
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)

    if not is_survey_pdf(pdf):
        print(f"Skipping {pdf.name}: not a survey file (expected name like 46654A1.pdf)")
        return

    json_path = pdf.parent / f"{pdf.stem}.json"

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
    parser.add_argument("--batch", action="store_true",
                        help="Submit pending PDFs via the Batches API (50%% cheaper, asynchronous)")
    parser.add_argument("--collect", action="store_true",
                        help="Collect finished batches and write their JSONs")
    parser.add_argument("--wait", action="store_true",
                        help="With --batch: poll and collect until all batches finish")

    args = parser.parse_args()

    if args.test:
        args.max_files = 3
        print("TEST MODE — processing only 3 files")

    if args.batch or args.collect:
        extractor = _make_extractor(args.api_key)
        if args.batch:
            if os.path.isfile(args.target):
                pdf = Path(args.target)
                pending = [(str(pdf), str(pdf.with_suffix(".json")))] if is_survey_pdf(pdf) else []
                pending = [x for x in pending if args.force or not Path(x[1]).exists()]
            else:
                pending = find_pending_pdfs(args.target, force=args.force)
            if args.max_files:
                pending = pending[:args.max_files]
            print(f"{len(pending)} surveys to submit via Batches API (~50% cheaper, async)")
            n = submit_batches(extractor, args.target, pending)
            print(f"Submitted {n} surveys. Collect later with: extract_all_surveys.py {args.target} --collect")
        if args.collect or args.wait:
            while True:
                _saved, done = collect_batches(extractor, args.target, force=args.force)
                if done or not args.wait:
                    break
                time.sleep(60)
        return

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
