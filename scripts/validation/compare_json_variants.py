#!/usr/bin/env python3
"""Compare Mina vs Tinta JSON survey files grouped by resolution number."""

import json
import re
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple


def parse_resolution_and_type(json_file: Path) -> Optional[Tuple[str, str]]:
    """Extract (resolution, type) from filenames like 'Res 75 a Mina_2d_attemp.json'."""
    stem = json_file.stem  # e.g. "Res 75 a Mina_2d_attemp"
    match = re.match(r'Res\s+(\d+)\s+a\s+(Mina|Tinta)', stem, re.IGNORECASE)
    if match:
        return match.group(1), match.group(2).capitalize()
    return None


def find_by_ink_type(base_dir: str) -> Dict[str, Dict[str, Path]]:
    """Group JSON files by ink type (Mina/Tinta), keyed by resolution."""
    base_path = Path(base_dir)
    groups: Dict[str, Dict[str, Path]] = defaultdict(dict)

    for json_file in sorted(base_path.rglob("*.json")):
        parsed = parse_resolution_and_type(json_file)
        if parsed:
            resolution, ink_type = parsed
            groups[ink_type][resolution] = json_file

    return dict(groups)


def compare_metadata(data1: dict, data2: dict) -> List[Tuple[str, any, any]]:
    """Return list of (key, val1, val2) for differing metadata fields."""
    meta1 = data1.get('metadata', {})
    meta2 = data2.get('metadata', {})
    all_keys = sorted(set(meta1.keys()) | set(meta2.keys()))
    return [(k, meta1.get(k), meta2.get(k)) for k in all_keys if meta1.get(k) != meta2.get(k)]


def compare_responses(mina_data: dict, tinta_data: dict) -> List[Tuple[str, any, any, str, str]]:
    """Return list of (question, mina_answer, tinta_answer, mina_notes, tinta_notes) for diffs."""
    diffs = []
    mina_resp = {r['question']: r for r in mina_data.get('responses', [])}
    tinta_resp = {r['question']: r for r in tinta_data.get('responses', [])}

    all_questions = sorted(
        set(mina_resp.keys()) | set(tinta_resp.keys()),
        key=lambda x: int(x) if x.isdigit() else x
    )

    for q in all_questions:
        r_mina = mina_resp.get(q, {})
        r_tinta = tinta_resp.get(q, {})
        if r_mina.get('answer') != r_tinta.get('answer') or r_mina.get('notes') != r_tinta.get('notes'):
            diffs.append((
                q,
                r_mina.get('answer'),
                r_tinta.get('answer'),
                r_mina.get('notes', ''),
                r_tinta.get('notes', '')
            ))

    return diffs


def compare_ink_group(ink_type: str, resolutions: Dict[str, Path]) -> List[Tuple[str, str, int]]:
    """Compare all resolution pairs within an ink type. Returns list of (res1, res2, n_diffs)."""
    print(f"\n{'='*80}")
    print(f"  {ink_type.upper()} — comparando todas las resoluciones entre sí")
    print(f"{'='*80}")

    sorted_res = sorted(resolutions.keys(), key=int)

    # Load all files
    data: Dict[str, dict] = {}
    for res in sorted_res:
        f = resolutions[res]
        try:
            with open(f, encoding='utf-8') as fh:
                data[res] = json.load(fh)
            print(f"  ✓ {res} DPI — {f.name}")
        except Exception as e:
            print(f"  ✗ {res} DPI — Error: {e}")

    results = []
    for i, res1 in enumerate(sorted_res):
        for res2 in sorted_res[i+1:]:
            if res1 not in data or res2 not in data:
                continue

            meta_diffs = compare_metadata(data[res1], data[res2])
            resp_diffs = compare_responses(data[res1], data[res2])
            results.append((res1, res2, len(resp_diffs)))

            print(f"\n  {res1} DPI vs {res2} DPI:")

            if meta_diffs:
                print(f"    Metadata — {len(meta_diffs)} diferencias:")
                for key, v1, v2 in meta_diffs:
                    print(f"      {key}: {v1!r} vs {v2!r}")
            else:
                print(f"    Metadata: ✓ idéntica")

            if not resp_diffs:
                print(f"    Respuestas: ✓ idénticas (0 diferencias)")
            else:
                print(f"    Respuestas: ✗ {len(resp_diffs)} preguntas diferentes\n")
                print(f"    {'Q':>4}  {res1+' DPI':>8}  {res2+' DPI':>8}  Notas")
                print(f"    {'-'*60}")
                for q, ans1, ans2, notes1, notes2 in resp_diffs:
                    s1 = str(ans1) if ans1 is not None else 'null'
                    s2 = str(ans2) if ans2 is not None else 'null'
                    notes_str = ''
                    if notes1:
                        notes_str += f"{res1}: {notes1}"
                    if notes2:
                        notes_str += (' | ' if notes_str else '') + f"{res2}: {notes2}"
                    print(f"    Q{q:>3}  {s1:>8}  {s2:>8}  {notes_str}")

    return results


def main():
    base_dir = sys.argv[1] if len(sys.argv) > 1 else "digitalizadas/TEST"

    print(f"Comparando consistencia por tipo de lápiz en: {base_dir}")
    print(f"{'='*80}")

    groups = find_by_ink_type(base_dir)

    if not groups:
        print("No se encontraron archivos Mina/Tinta.")
        return

    all_results: Dict[str, List[Tuple[str, str, int]]] = {}

    for ink_type in sorted(groups.keys()):
        resolutions = groups[ink_type]
        print(f"\n  {ink_type}: resoluciones {sorted(resolutions.keys(), key=int)} DPI")
        all_results[ink_type] = compare_ink_group(ink_type, resolutions)

    # Summary
    print(f"\n{'='*80}")
    print(f"RESUMEN GENERAL")
    print(f"{'='*80}")
    for ink_type, results in all_results.items():
        print(f"\n  {ink_type.upper()}")
        print(f"  {'Par':>16}  {'Diferencias':>12}")
        print(f"  {'-'*32}")
        for res1, res2, n_diffs in results:
            status = '✓ Identicas' if n_diffs == 0 else f'✗ {n_diffs} preguntas'
            print(f"  {res1:>4} vs {res2:>4} DPI  {status}")
    print(f"\n{'='*80}")


if __name__ == "__main__":
    main()
