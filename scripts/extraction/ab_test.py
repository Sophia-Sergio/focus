#!/usr/bin/env python3
"""
A/B test: Claude API vs local qwen2.5-vl (LM Studio) on a single survey PDF.

Usage:
    python ab_test.py <path/to/survey.pdf>
    python ab_test.py <path/to/survey.pdf> --lm-url http://localhost:1234/v1
    python ab_test.py <path/to/survey.pdf> --model qwen2.5-vl-7b-instruct
"""

import io
import os
import re
import sys
import json
import base64
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

try:
    import pdf2image
except ImportError:
    os.system("pip3 install pdf2image Pillow")
    import pdf2image

try:
    import anthropic
except ImportError:
    os.system("pip3 install anthropic")
    import anthropic

try:
    from openai import OpenAI
except ImportError:
    os.system("pip3 install openai")
    from openai import OpenAI


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def pdf_to_base64_pages(pdf_path: str, dpi: int = 200) -> List[str]:
    """Return a list of base64-encoded PNG strings, one per PDF page."""
    images = pdf2image.convert_from_path(pdf_path, dpi=dpi)
    pages = []
    for img in images:
        if img.mode != "RGB":
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        pages.append(base64.b64encode(buf.getvalue()).decode("utf-8"))
    return pages


def build_task_context(pdf_path: str) -> tuple[str, dict]:
    """
    Derive task-context fields from the file path.
    Returns (prompt_text, meta_dict).
    """
    p = Path(pdf_path)
    survey_id = p.stem
    folder_name = p.parent.name

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
        scale_1_end, scale_2_start = 49, 50
    else:
        grade_range = "4° - 5°"
        total_questions = 50
        scale_1_end, scale_2_start = 31, 32

    rules_path = Path(__file__).parent.parent.parent / ".claude" / "extraction_rules.md"
    extraction_rules = rules_path.read_text(encoding="utf-8")

    prompt = f"""## Task Context
- survey_id: "{survey_id}" — use this exact value, do NOT read it from the PDF
- grade_range: "{grade_range}" — use this exact value, do NOT read it from the PDF
- total_questions: {total_questions}
- Scale 1 (Certainty) applies to questions 1–{scale_1_end}
- Scale 2 (Frequency) applies to questions {scale_2_start}–{total_questions}
- extraction_date: "{datetime.now().strftime('%Y-%m-%d')}"

{extraction_rules}"""

    meta = {
        "survey_id": survey_id,
        "grade_range": grade_range,
        "total_questions": total_questions,
        "school_name": p.parent.parent.name,
        "grade_folder": p.parent.name,
        "extraction_date": datetime.now().strftime("%Y-%m-%d"),
    }
    return prompt, meta


def parse_json_from_response(text: str) -> Optional[Dict]:
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


# ---------------------------------------------------------------------------
# Claude extractor
# ---------------------------------------------------------------------------

def extract_with_claude(pages_b64: List[str], prompt: str, api_key: Optional[str] = None) -> Optional[Dict]:
    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("  ANTHROPIC_API_KEY not set — skipping Claude.")
        return None

    client = anthropic.Anthropic(api_key=key)

    content = [
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}}
        for b64 in pages_b64
    ]
    content.append({"type": "text", "text": prompt})

    message = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=16000,
        temperature=0,
        messages=[{"role": "user", "content": content}],
    )
    return parse_json_from_response(message.content[0].text)


# ---------------------------------------------------------------------------
# Local model extractor (LM Studio — OpenAI-compatible API)
# ---------------------------------------------------------------------------

def extract_with_local(
    pages_b64: List[str],
    prompt: str,
    base_url: str = "http://localhost:1234/v1",
    model: str = "qwen2.5-vl-7b-instruct",
) -> Optional[Dict]:
    client = OpenAI(api_key="lm-studio", base_url=base_url)

    # Split: extraction rules → system, task context → user
    # The full prompt already contains both; we put everything in user for simplicity
    # (system role support varies by LM Studio version).
    image_blocks = [
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{b64}"},
        }
        for b64 in pages_b64
    ]
    image_blocks.append({"type": "text", "text": prompt})

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        max_tokens=16000,
        messages=[{"role": "user", "content": image_blocks}],
    )
    return parse_json_from_response(response.choices[0].message.content)


# ---------------------------------------------------------------------------
# Comparison report
# ---------------------------------------------------------------------------

def compare(claude_data: Optional[Dict], local_data: Optional[Dict], total_q: int) -> None:
    print("\n" + "=" * 72)
    print("A/B COMPARISON REPORT")
    print("=" * 72)

    if not claude_data and not local_data:
        print("Both extractors failed — nothing to compare.")
        return

    # --- Metadata ---
    print("\n### METADATA\n")
    meta_fields = ["student_name", "student_run", "student_gender", "school_name", "date"]
    header = f"{'Field':<22}  {'Claude':^28}  {'Local':^28}  Match"
    print(header)
    print("-" * len(header))
    for field in meta_fields:
        c_val = (claude_data or {}).get("metadata", {}).get(field, "—")
        l_val = (local_data or {}).get("metadata", {}).get(field, "—")
        match = "✓" if c_val == l_val else "✗"
        print(f"  {field:<20}  {str(c_val):<28}  {str(l_val):<28}  {match}")

    # --- Responses ---
    print("\n### ANSWERS\n")
    c_responses = {r["question"]: r for r in (claude_data or {}).get("responses", [])}
    l_responses = {r["question"]: r for r in (local_data or {}).get("responses", [])}

    mismatches = []
    matches = 0
    both_null = 0
    only_in_claude = 0
    only_in_local = 0

    for q in range(1, total_q + 1):
        key = str(q)
        c = c_responses.get(key)
        l = l_responses.get(key)
        c_ans = c["answer"] if c else "MISSING"
        l_ans = l["answer"] if l else "MISSING"

        if c_ans == l_ans:
            if c_ans is None:
                both_null += 1
            else:
                matches += 1
        else:
            if c_ans == "MISSING":
                only_in_local += 1
            elif l_ans == "MISSING":
                only_in_claude += 1
            mismatches.append((q, c_ans, l_ans,
                                (c or {}).get("notes", ""), (l or {}).get("notes", "")))

    # Summary numbers
    total_present = total_q
    agree = matches + both_null
    print(f"  Total questions : {total_present}")
    print(f"  Full agreement  : {agree}  ({agree/total_present*100:.1f}%)")
    print(f"  Disagreements   : {len(mismatches)}")
    if only_in_claude:
        print(f"  Missing in local: {only_in_claude}")
    if only_in_local:
        print(f"  Missing in Claude: {only_in_local}")

    if mismatches:
        print(f"\n  {'Q':>4}  {'Claude':>8}  {'Local':>8}  Notes")
        print("  " + "-" * 60)
        for q, c_ans, l_ans, c_note, l_note in mismatches:
            c_str = str(c_ans) if c_ans is not None else "null"
            l_str = str(l_ans) if l_ans is not None else "null"
            note = c_note or l_note
            note_preview = (note[:35] + "…") if len(note) > 35 else note
            print(f"  {q:>4}  {c_str:>8}  {l_str:>8}  {note_preview}")

    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="A/B test Claude vs local VL model on a survey PDF.")
    parser.add_argument("pdf", help="Path to the survey PDF")
    parser.add_argument("--api-key", help="Anthropic API key (or set ANTHROPIC_API_KEY)")
    parser.add_argument("--lm-url", default="http://localhost:1234/v1",
                        help="LM Studio base URL (default: http://localhost:1234/v1)")
    parser.add_argument("--model", default="qwen2.5-vl-7b-instruct",
                        help="Model name as shown in LM Studio (default: qwen2.5-vl-7b-instruct)")
    parser.add_argument("--save", action="store_true",
                        help="Save outputs as <stem>_claude.json and <stem>_local.json")
    parser.add_argument("--skip-claude", action="store_true", help="Only run local model")
    parser.add_argument("--skip-local", action="store_true", help="Only run Claude")
    args = parser.parse_args()

    pdf_path = args.pdf
    if not Path(pdf_path).exists():
        print(f"Error: file not found: {pdf_path}")
        sys.exit(1)

    print(f"PDF: {pdf_path}")
    print("Converting pages to images…")
    pages = pdf_to_base64_pages(pdf_path)
    print(f"  {len(pages)} page(s) converted")

    prompt, meta = build_task_context(pdf_path)
    total_q = meta["total_questions"]

    claude_data = None
    local_data = None

    if not args.skip_claude:
        print("\n[1/2] Running Claude (claude-sonnet-4-5-20250929)…")
        try:
            claude_data = extract_with_claude(pages, prompt, api_key=args.api_key)
            if claude_data and claude_data.get("metadata") is not None:
                claude_data["metadata"].update({k: meta[k] for k in ("survey_id", "grade_range", "extraction_date", "total_questions", "school_name", "grade_folder")})
            print("  Done." if claude_data else "  Failed to parse JSON from response.")
        except Exception as e:
            print(f"  Error: {e}")

    if not args.skip_local:
        print(f"\n[2/2] Running local model ({args.model} @ {args.lm_url})…")
        try:
            local_data = extract_with_local(pages, prompt, base_url=args.lm_url, model=args.model)
            if local_data and local_data.get("metadata") is not None:
                local_data["metadata"].update({k: meta[k] for k in ("survey_id", "grade_range", "extraction_date", "total_questions", "school_name")})
            print("  Done." if local_data else "  Failed to parse JSON from response.")
        except Exception as e:
            print(f"  Error: {e}")
            print("  Is LM Studio running with the model loaded?")

    compare(claude_data, local_data, total_q)

    if args.save:
        stem = Path(pdf_path).parent / Path(pdf_path).stem
        if claude_data:
            out = str(stem) + "_claude.json"
            Path(out).write_text(json.dumps(claude_data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved: {out}")
        if local_data:
            out = str(stem) + "_local.json"
            Path(out).write_text(json.dumps(local_data, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Saved: {out}")


if __name__ == "__main__":
    main()
