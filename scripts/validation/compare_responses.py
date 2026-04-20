import json
import os

def compare_survey_responses():
    """Compare responses between regular JSON files and _2d_attemp.json files"""

    digitalizadas_path = "digitalizadas"

    # Read the matching IDs file
    with open("/tmp/matching_ids.txt", "r") as f:
        matching_ids = [line.strip() for line in f if line.strip()]

    print("Processing {} survey pairs...".format(len(matching_ids)))

    processed_count = 0
    differences_found = 0

    for survey_id in matching_ids:
        try:
            # Find the regular JSON file
            regular_file = None
            attemp_file = None

            for root, dirs, files in os.walk(digitalizadas_path):
                for file in files:
                    if file == "{}.json".format(survey_id):
                        regular_file = os.path.join(root, file)
                    elif file == "{}_2d_attemp.json".format(survey_id):
                        attemp_file = os.path.join(root, file)

            if not regular_file or not attemp_file:
                print("Warning: Could not find both files for {}".format(survey_id))
                continue

            # Read both files
            with open(regular_file, 'r') as f:
                regular_data = json.load(f)

            with open(attemp_file, 'r') as f:
                attemp_data = json.load(f)

            # Create comparison structure
            comparison = {
                "survey_id": survey_id,
                "responses": []
            }

            regular_responses = {resp["question"]: resp["answer"] for resp in regular_data.get("responses", [])}
            attemp_responses = {resp["question"]: resp["answer"] for resp in attemp_data.get("responses", [])}

            # Get all unique questions from both files
            all_questions = set(regular_responses.keys()) | set(attemp_responses.keys())
            all_questions = sorted(all_questions, key=lambda x: int(x) if x.isdigit() else 999)

            survey_differences = 0
            for question in all_questions:
                answer_regular = regular_responses.get(question)
                answer_attemp = attemp_responses.get(question)
                difference = 1 if answer_regular != answer_attemp else 0
                if difference == 1:
                    survey_differences += 1

                comparison["responses"].append({
                    "question": question,
                    "answer_json": answer_regular,
                    "answer_2d_json": answer_attemp,
                    "difference": difference
                })

            # Save comparison file in the same folder as the regular JSON file
            output_file = os.path.join(os.path.dirname(regular_file), "{}_comparison.json".format(survey_id))
            with open(output_file, 'w') as f:
                json.dump(comparison, f, indent=2, ensure_ascii=False)

            processed_count += 1
            if survey_differences > 0:
                differences_found += 1
                if processed_count <= 10:  # Only print first 10
                    print("{}: {} differences found".format(survey_id, survey_differences))

        except Exception as e:
            print("Error processing {}: {}".format(survey_id, e))
            continue

    print("Comparison complete!")
    print("Processed {} survey pairs".format(processed_count))
    print("Found differences in {} surveys".format(differences_found))

if __name__ == "__main__":
    compare_survey_responses()
