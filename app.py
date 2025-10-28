from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from datetime import datetime

# Initialize Flask app
app = Flask(__name__)
# Enable CORS for all routes and origins (adjust in production if needed)
CORS(app)

# Define the path for the JSON file to store results
JSON_FILE_PATH = 'judging_results.json'

@app.route('/api/submit-judging', methods=['POST'])
def submit_judging():
    """
    Receives judging data via POST request, appends it to a JSON file.
    """
    try:
        # Get the JSON data sent from the form
        new_judging_data = request.get_json()

        if not new_judging_data:
            return jsonify({"status": "error", "message": "No data received"}), 400

        # Add a server-side timestamp for record keeping
        new_judging_data['receivedTimestamp'] = datetime.now().isoformat()

        # Load existing data from the file
        if os.path.exists(JSON_FILE_PATH):
            try:
                with open(JSON_FILE_PATH, 'r', encoding='utf-8') as f:
                    all_judging_data = json.load(f)
                    # Ensure it's a list
                    if not isinstance(all_judging_data, list):
                        all_judging_data = [] 
            except json.JSONDecodeError:
                print(f"Warning: {JSON_FILE_PATH} contains invalid JSON. Starting with an empty list.")
                all_judging_data = []
            except Exception as e:
                print(f"Error reading {JSON_FILE_PATH}: {e}")
                return jsonify({"status": "error", "message": "Could not read existing results file"}), 500
        else:
            # If the file doesn't exist, start with an empty list
            all_judging_data = []

        # Append the new data
        all_judging_data.append(new_judging_data)

        # Write the updated data back to the file
        try:
            with open(JSON_FILE_PATH, 'w', encoding='utf-8') as f:
                # Use indent for readability in the JSON file
                json.dump(all_judging_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"Error writing to {JSON_FILE_PATH}: {e}")
            return jsonify({"status": "error", "message": "Could not save results"}), 500

        # Return a success response
        return jsonify({"status": "success", "message": "Judgment submitted successfully"}), 200

    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        return jsonify({"status": "error", "message": "An internal server error occurred"}), 500

# Optional: Add a simple root route for testing if the server is running
@app.route('/', methods=['GET'])
def index():
    return jsonify({"message": "Judging Backend Service is running."})

# Run the Flask app (for local development)
if __name__ == '__main__':
    # You can change the port if needed, e.g., port=5001
    # Use host='0.0.0.0' to make it accessible on your network
    app.run(debug=True, host='0.0.0.0', port=5000) 
