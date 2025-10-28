from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import json
import os
from datetime import datetime

app = Flask(__name__)
# Enable CORS for all domains on all routes
CORS(app)

# Define the path for the JSON file relative to the script location
# Ensures it works correctly regardless of where the script is run from
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_FILE_PATH = os.path.join(BASE_DIR, 'judging_results.json')

def read_results():
    """Reads the current results from the JSON file."""
    if not os.path.exists(RESULTS_FILE_PATH):
        return [] # Return empty list if file doesn't exist
    try:
        with open(RESULTS_FILE_PATH, 'r', encoding='utf-8') as f:
            # Handle empty file case
            content = f.read()
            if not content:
                return []
            return json.loads(content)
    except (json.JSONDecodeError, IOError) as e:
        print(f"Error reading results file: {e}")
        # In case of corruption, maybe return empty or handle differently
        return []

def write_results(data):
    """Writes the updated results back to the JSON file."""
    try:
        with open(RESULTS_FILE_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
    except IOError as e:
        print(f"Error writing results file: {e}")
        # Potentially raise an exception or handle the error
        raise IOError("Could not save results.")


@app.route('/api/submit-judging', methods=['POST'])
def submit_judging():
    """Receives judging data and appends it to the JSON file."""
    if not request.is_json:
        abort(400, description="Request must be JSON")

    new_submission = request.get_json()

    # Basic validation (can be expanded)
    required_fields = ['judgeName', 'teamName', 'hackathonTrack', 'scores', 'submissionTimestamp']
    if not all(field in new_submission for field in required_fields):
        abort(400, description="Missing required fields in submission")

    if not isinstance(new_submission.get('scores'), dict):
         abort(400, description="Scores field must be an object")

    try:
        current_results = read_results()
        current_results.append(new_submission)
        write_results(current_results)
        return jsonify({"status": "success", "message": "Judgment submitted successfully!"}), 201
    except IOError as e:
        abort(500, description=str(e))
    except Exception as e:
        print(f"Unexpected error during submission: {e}")
        abort(500, description="An internal server error occurred.")


@app.route('/api/get-results', methods=['GET'])
def get_results():
    """Reads and returns all submitted judging results."""
    try:
        results = read_results()
        return jsonify(results), 200
    except Exception as e:
        print(f"Unexpected error retrieving results: {e}")
        abort(500, description="An internal server error occurred retrieving results.")

if __name__ == '__main__':
    # Use environment variable for port if available (e.g., for Render deployment), default to 5000
    port = int(os.environ.get('PORT', 5000))
    # Important for Render: host='0.0.0.0' makes it accessible externally
    app.run(host='0.0.0.0', port=port, debug=True) # Turn debug=False for production
