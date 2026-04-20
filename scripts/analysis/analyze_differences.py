import json
import os
from collections import Counter


def analyze_differences():
    comparison_files = []
    for root, _, files in os.walk("digitalizadas"):
        for file in files:
            if file.endswith("_comparison.json"):
                comparison_files.append(os.path.join(root, file))

    print("Analyzing {} comparison files...".format(len(comparison_files)))

    total_responses = 0
    total_differences = 0
    difference_counts = []
    surveys_by_difference_count = Counter()

    for file_path in comparison_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            responses = data.get("responses", [])
            survey_differences = sum(1 for r in responses if r.get("difference") == 1)

            total_responses += len(responses)
            total_differences += survey_differences
            difference_counts.append(survey_differences)
            surveys_by_difference_count[survey_differences] += 1

        except Exception as e:
            print("Error reading {}: {}".format(file_path, e))

    surveys_total = len(difference_counts)
    surveys_with_differences = len([d for d in difference_counts if d > 0])

    print("\n=== SUMMARY ===")
    print("Total survey pairs analyzed: {}".format(surveys_total))
    print("Surveys with identical responses: {}".format(surveys_total - surveys_with_differences))
    print("Surveys with at least one difference: {}".format(surveys_with_differences))
    if surveys_total > 0:
        print("Surveys with differences: {:.2f}%".format(float(surveys_with_differences) / surveys_total * 100))
    print("Total responses compared: {}".format(total_responses))
    print("Total differences found: {}".format(total_differences))
    if total_responses > 0:
        print("Overall difference rate: {:.2f}%".format(float(total_differences) / total_responses * 100))

    print("\n=== DISTRIBUTION ===")
    for diff_count, survey_count in sorted(surveys_by_difference_count.items()):
        pct = float(survey_count) / surveys_total * 100 if surveys_total > 0 else 0
        label = "identical" if diff_count == 0 else "{} difference{}".format(diff_count, "s" if diff_count != 1 else "")
        print("  {} surveys ({:.1f}%) — {}".format(survey_count, pct, label))

    if difference_counts:
        print("\n=== STATISTICS ===")
        sorted_counts = sorted(difference_counts)
        print("  Average: {:.2f}".format(sum(difference_counts) / len(difference_counts)))
        print("  Median:  {:.0f}".format(sorted_counts[len(sorted_counts) // 2]))
        print("  Max:     {}".format(max(difference_counts)))


if __name__ == "__main__":
    analyze_differences()
