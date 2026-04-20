#!/usr/bin/env python3
"""
Check consistency of ALL questions by comparing 4 extraction attempts
"""
import json
from pathlib import Path

def main():
    import sys

    # Get PDF basename from command line or use default
    pdf_basename = sys.argv[1] if len(sys.argv) > 1 else "311019"

    # Load all 4 JSON files
    attempts = []
    for i in range(1, 5):
        json_path = f"/Users/sergiotorres/code/focus/tmp/{pdf_basename}_{i}.json"
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                attempts.append(data)
        except Exception as e:
            print(f"Error loading {json_path}: {e}")
            return

    print("=" * 70)
    print("Full Survey Consistency Analysis - All 50 Questions")
    print("=" * 70)
    print()

    # Track inconsistencies
    inconsistent_questions = []
    total_questions = 50

    # Check each question
    for q_num in range(1, 51):
        answers = []
        notes_list = []

        for attempt in attempts:
            response = next((r for r in attempt['responses'] if r['question'] == str(q_num)), None)
            if response:
                answers.append(response.get('answer'))
                notes_list.append(response.get('notes', ''))

        # Check if all answers are the same
        unique_answers = set(answers)

        if len(unique_answers) > 1:
            inconsistent_questions.append({
                'question': q_num,
                'answers': answers,
                'notes': notes_list,
                'unique_answers': unique_answers
            })

    # Summary
    consistent_count = total_questions - len(inconsistent_questions)
    print(f"Total Questions: {total_questions}")
    print(f"Consistent: {consistent_count} ({consistent_count/total_questions*100:.1f}%)")
    print(f"Inconsistent: {len(inconsistent_questions)} ({len(inconsistent_questions)/total_questions*100:.1f}%)")
    print()

    if inconsistent_questions:
        print("=" * 70)
        print("INCONSISTENT QUESTIONS:")
        print("=" * 70)

        for item in inconsistent_questions:
            q = item['question']
            answers = item['answers']
            notes = item['notes']
            unique = item['unique_answers']

            print(f"\nQuestion {q}:")
            print(f"  Unique answers: {unique}")

            # Count distribution
            answer_counts = {}
            for ans in answers:
                answer_counts[ans] = answer_counts.get(ans, 0) + 1

            print(f"  Distribution:")
            for ans, count in sorted(answer_counts.items(), key=lambda x: x[1], reverse=True):
                print(f"    {ans}: {count}/4 times ({count*25}%)")

            print(f"  Details:")
            for i, (ans, note) in enumerate(zip(answers, notes), 1):
                note_display = f" - '{note}'" if note else ""
                print(f"    Attempt {i}: {ans}{note_display}")
    else:
        print("✓ All 50 questions are CONSISTENT across all 4 attempts!")

    # Additional statistics
    print()
    print("=" * 70)
    print("DETAILED STATISTICS:")
    print("=" * 70)

    # Check null responses across all attempts
    null_counts = {}
    for q_num in range(1, 51):
        null_count = 0
        for attempt in attempts:
            response = next((r for r in attempt['responses'] if r['question'] == str(q_num)), None)
            if response and response.get('answer') is None:
                null_count += 1
        if null_count > 0:
            null_counts[q_num] = null_count

    if null_counts:
        print(f"\nQuestions with null responses (at least once):")
        for q, count in sorted(null_counts.items()):
            print(f"  Q{q}: {count}/4 attempts")

if __name__ == "__main__":
    main()
