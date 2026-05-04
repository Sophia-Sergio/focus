#!/usr/bin/env python3
"""
Convert survey JSON files to consolidated CSV files.
Creates 2 consolidated files: 4-5_consolidated.csv and 6-7_consolidated.csv

Usage:
    python3 scripts/output/json_to_csv.py <path_to_folder>

Examples:
    python3 scripts/output/json_to_csv.py digitalizadas
    python3 scripts/output/json_to_csv.py "2026-03/pdfs/Avance Regiones"

If no path is provided, defaults to 'digitalizadas'.
Output CSVs are written into the same folder as the input.
"""

import json
import csv
from pathlib import Path

def load_survey_json(json_path):
    """Load a survey JSON file and return its data"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_survey_row(survey_data, max_questions):
    """Extract a single row of data from a survey JSON"""
    metadata = survey_data['metadata']
    responses = survey_data['responses']

    # Build the row with metadata
    row = {
        'survey_id': metadata.get('survey_id', ''),
        'type': metadata.get('type', ''),
        'subtype': metadata.get('subtype', ''),
        'grade_range': metadata.get('grade_range', ''),
        'student_name': metadata.get('student_name', ''),
        'student_run': metadata.get('student_run', ''),
        'student_gender': metadata.get('student_gender', ''),
        'school_name': metadata.get('school_name', ''),
        'grade': metadata.get('grade', ''),
        'section': metadata.get('section', ''),
        'date': metadata.get('date', ''),
        'total_questions': metadata.get('total_questions', ''),
        'completion_status': metadata.get('completion_status', ''),
        'school_folder': metadata.get('school_folder', ''),
        'grade_folder': metadata.get('grade_folder', ''),
        'section_folder': metadata.get('section_folder', '')
    }

    # Add answer columns (q1, q2, q3, ...)
    # Create a mapping of question number to answer
    answers_dict = {}
    for response in responses:
        q_num = response.get('question', '')
        answer = response.get('answer', '')
        # Convert None/null to empty string for CSV
        if answer is None:
            answer = ''
        answers_dict[str(q_num)] = answer

    # Add all question columns in order
    for i in range(1, max_questions + 1):
        q_key = str(i)
        row[f'q{i}'] = answers_dict.get(q_key, '')

    return row

def process_all_surveys(digitalizadas_path='digitalizadas'):
    """Process all JSON files in digitalizadas folder and create consolidated CSVs"""
    base_folder = Path(digitalizadas_path)

    if not base_folder.exists():
        print(f"Error: Folder '{digitalizadas_path}' does not exist")
        return

    json_files = sorted(base_folder.rglob('*.json'))

    if not json_files:
        print(f"No JSON files found in '{digitalizadas_path}'")
        return

    print(f"Found {len(json_files)} JSON files across all subdirectories")

    # Show which folders contain JSON files
    folders_with_json = set()
    for json_file in json_files:
        folders_with_json.add(json_file.parent.name)

    print(f"\nProcessing surveys from {len(folders_with_json)} folders:")
    for folder in sorted(folders_with_json):
        count = sum(1 for jf in json_files if jf.parent.name == folder)
        print(f"  - {folder}: {count} files")

    # Group surveys by grade range
    surveys_4_5 = []
    surveys_6_7 = []
    skipped = []

    for json_file in json_files:
        try:
            survey_data = load_survey_json(json_file)
            grade_range = survey_data['metadata'].get('grade_range', 'unknown')

            # Normalize grade_range by removing spaces for comparison
            grade_range_normalized = grade_range.replace(' ', '')

            if '4°-5°' in grade_range_normalized or '4-5' in grade_range_normalized:
                surveys_4_5.append(survey_data)
            elif '6°-7°' in grade_range_normalized or '6-7' in grade_range_normalized:
                surveys_6_7.append(survey_data)
            else:
                skipped.append((json_file, grade_range))
        except Exception as e:
            print(f"Error processing {json_file}: {e}")
            skipped.append((json_file, f"Error: {e}"))

    print(f"\n4°-5° grade range: {len(surveys_4_5)} surveys")
    print(f"6°-7° grade range: {len(surveys_6_7)} surveys")
    if skipped:
        print(f"Skipped: {len(skipped)} files")
        for file, reason in skipped:
            print(f"  - {file.name}: {reason}")

    # Define CSV headers
    metadata_headers = [
        'survey_id', 'type', 'subtype', 'grade_range', 'student_name',
        'student_run', 'student_gender', 'school_name', 'grade', 'section',
        'date', 'total_questions', 'completion_status', 'school_folder',
        'grade_folder', 'section_folder'
    ]

    # Create 4-5 consolidated CSV
    if surveys_4_5:
        output_file = base_folder / '4-5_consolidated.csv'
        max_questions = 50
        question_headers = [f'q{i}' for i in range(1, max_questions + 1)]
        all_headers = metadata_headers + question_headers

        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_headers)
            writer.writeheader()

            for survey in surveys_4_5:
                row = extract_survey_row(survey, max_questions)
                writer.writerow(row)

        print(f"\n✓ Created: {output_file}")
        print(f"  - {len(surveys_4_5)} surveys")
        print(f"  - {len(all_headers)} columns (16 metadata + 50 questions)")

    # Create 6-7 consolidated CSV
    if surveys_6_7:
        output_file = base_folder / '6-7_consolidated.csv'
        max_questions = 68
        question_headers = [f'q{i}' for i in range(1, max_questions + 1)]
        all_headers = metadata_headers + question_headers

        with open(output_file, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=all_headers)
            writer.writeheader()

            for survey in surveys_6_7:
                row = extract_survey_row(survey, max_questions)
                writer.writerow(row)

        print(f"\n✓ Created: {output_file}")
        print(f"  - {len(surveys_6_7)} surveys")
        print(f"  - {len(all_headers)} columns (16 metadata + 68 questions)")

def main():
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'digitalizadas'
    print(f"Consolidating survey JSON files into CSV format...\n")
    process_all_surveys(path)

if __name__ == '__main__':
    main()
