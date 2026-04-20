import json
import os
import shutil

def replace_malformed_surveys():
    """Replace malformed regular JSON files with _2d_attemp versions for surveys with >5 differences"""

    # Find all comparison files
    comparison_files = []
    for root, dirs, files in os.walk("digitalizadas"):
        for file in files:
            if file.endswith("_comparison.json"):
                comparison_files.append(os.path.join(root, file))

    print("Checking {} comparison files for surveys with >5 differences...".format(len(comparison_files)))

    surveys_to_replace = []

    # Identify surveys with more than 5 differences
    for file_path in comparison_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

            survey_id = data.get("survey_id", "unknown")
            responses = data.get("responses", [])

            differences = [r for r in responses if r.get("difference") == 1]
            diff_count = len(differences)

            if diff_count > 5:
                surveys_to_replace.append({
                    'survey_id': survey_id,
                    'comparison_file': file_path,
                    'differences': diff_count,
                    'differing_questions': [r['question'] for r in differences]
                })

        except Exception as e:
            print("Error reading {}: {}".format(file_path, e))
            continue

    print("Found {} surveys with more than 5 differences to potentially replace".format(len(surveys_to_replace)))

    # Sort by number of differences (most problematic first)
    surveys_to_replace.sort(key=lambda x: x['differences'], reverse=True)

    replaced_count = 0

    for survey in surveys_to_replace:
        survey_id = survey['survey_id']

        print("Processing survey {} with {} differences...".format(survey_id, survey['differences']))

        try:
            # Find the regular JSON file and _2d_attemp file
            regular_file = None
            attemp_file = None

            for root, dirs, files in os.walk("digitalizadas"):
                for file in files:
                    if file == "{}.json".format(survey_id):
                        regular_file = os.path.join(root, file)
                    elif file == "{}_2d_attemp.json".format(survey_id):
                        attemp_file = os.path.join(root, file)

            if not regular_file or not attemp_file:
                print("  Warning: Could not find both files for {}".format(survey_id))
                continue

            # Try to read the _2d_attemp file (should be valid)
            try:
                with open(attemp_file, 'r') as f:
                    attemp_data = json.load(f)
            except ValueError as e:
                print("  Skipping {}: _2d_attemp JSON file is also malformed ({})".format(survey_id, e))
                continue

            # Backup the original file
            backup_file = regular_file + ".backup"
            if os.path.exists(regular_file):
                shutil.copy2(regular_file, backup_file)
                print("  Created backup: {}".format(backup_file))

            # Replace the regular JSON with the _2d_attemp version
            shutil.copy2(attemp_file, regular_file)
            print("  Replaced {} with _2d_attemp version".format(regular_file))

            # Update the comparison file to show no differences
            with open(survey['comparison_file'], 'r') as f:
                comp_data = json.load(f)

            for resp in comp_data.get("responses", []):
                resp["answer_json"] = resp["answer_2d_json"]
                resp["difference"] = 0

            with open(survey['comparison_file'], 'w') as f:
                json.dump(comp_data, f, indent=2)

            replaced_count += 1
            print("  Successfully replaced survey {} ({} differences resolved)".format(survey_id, survey['differences']))

        except Exception as e:
            print("  Error replacing survey {}: {}".format(survey_id, e))
            continue

    print("\n=== SUMMARY ===")
    print("Successfully replaced {} surveys with >5 differences".format(replaced_count))
    print("Total surveys that needed replacement: {}".format(len(surveys_to_replace)))

if __name__ == "__main__":
    replace_malformed_surveys()
