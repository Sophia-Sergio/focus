import json
import os

def fix_high_difference_surveys():
    """Fix surveys with more than 5 differences by updating original JSON with _2d_attemp values"""

    # Find all comparison files
    comparison_files = []
    for root, dirs, files in os.walk("digitalizadas"):
        for file in files:
            if file.endswith("_comparison.json"):
                comparison_files.append(os.path.join(root, file))

    print("Checking {} comparison files for surveys with >5 differences...".format(len(comparison_files)))

    surveys_to_fix = []

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
                surveys_to_fix.append({
                    'survey_id': survey_id,
                    'comparison_file': file_path,
                    'differences': diff_count,
                    'differing_questions': [r['question'] for r in differences]
                })

        except Exception as e:
            print("Error reading {}: {}".format(file_path, e))
            continue

    print("Found {} surveys with more than 5 differences".format(len(surveys_to_fix)))

    # Sort by number of differences (most problematic first)
    surveys_to_fix.sort(key=lambda x: x['differences'], reverse=True)

    fixed_count = 0

    for survey in surveys_to_fix:
        survey_id = survey['survey_id']
        differing_questions = set(survey['differing_questions'])

        print("Fixing survey {} with {} differences...".format(survey_id, survey['differences']))

        try:
            # Find the regular JSON file
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

            # Read both files with error handling
            try:
                with open(regular_file, 'r') as f:
                    regular_data = json.load(f)
            except ValueError as e:
                print("  Skipping {}: Regular JSON file is malformed ({})".format(survey_id, e))
                continue

            try:
                with open(attemp_file, 'r') as f:
                    attemp_data = json.load(f)
            except ValueError as e:
                print("  Skipping {}: _2d_attemp JSON file is malformed ({})".format(survey_id, e))
                continue

            # Create mapping of question -> answer from _2d_attemp file
            attemp_answers = {resp["question"]: resp["answer"] for resp in attemp_data.get("responses", [])}

            # Update regular JSON responses where there are differences
            updated_responses = []
            for resp in regular_data.get("responses", []):
                question = resp["question"]
                if question in differing_questions and question in attemp_answers:
                    # Replace with _2d_attemp answer
                    resp["answer"] = attemp_answers[question]
                    print("  Updated question {}: {} -> {}".format(question, resp["answer"], attemp_answers[question]))

                updated_responses.append(resp)

            regular_data["responses"] = updated_responses

            # Save the updated regular JSON file
            with open(regular_file, 'w') as f:
                json.dump(regular_data, f, indent=2)

            # Also update the comparison file to reflect the fix
            with open(survey['comparison_file'], 'r') as f:
                comp_data = json.load(f)

            for resp in comp_data.get("responses", []):
                if resp["question"] in differing_questions:
                    resp["answer_json"] = resp["answer_2d_json"]
                    resp["difference"] = 0

            with open(survey['comparison_file'], 'w') as f:
                json.dump(comp_data, f, indent=2)

            fixed_count += 1
            print("  Fixed survey {} ({} differences corrected)".format(survey_id, len(differing_questions)))

        except Exception as e:
            print("  Error fixing survey {}: {}".format(survey_id, e))
            continue

    print("\n=== SUMMARY ===")
    print("Successfully fixed {} surveys with >5 differences".format(fixed_count))
    print("Total surveys that needed fixing: {}".format(len(surveys_to_fix)))

if __name__ == "__main__":
    fix_high_difference_surveys()
