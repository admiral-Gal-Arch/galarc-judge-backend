from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import os
from pymongo import MongoClient
from bson.objectid import ObjectId # Needed to handle MongoDB's _id

app = Flask(__name__)
CORS(app)

# --- MongoDB Setup ---
# Get the connection string from the environment variable you set in Render
MONGODB_URI = os.environ.get('MONGODB_URI')
if not MONGODB_URI:
    # If the variable isn't set, the app can't start
    raise RuntimeError("MONGODB_URI environment variable not set")

try:
    # Connect to MongoDB
    client = MongoClient(MONGODB_URI)
    # Get your database (it will be created if it doesn't exist)
    db = client.get_database("hackathonDB") 
    # Get your collection (like a table, will also be created)
    submissions_collection = db.get_collection("submissions") 
    # Test the connection
    client.server_info()
    print("Successfully connected to MongoDB.")
except Exception as e:
    print(f"ERROR: Could not connect to MongoDB: {e}")
    # If connection fails, you might want to exit or handle it
    client = None
    submissions_collection = None
# --- End of MongoDB Setup ---


@app.route('/api/submit-judging', methods=['POST'])
def submit_judging():
    """Receives judging data and inserts it into the MongoDB collection."""
    if not request.is_json:
        abort(400, description="Request must be JSON")

    if submissions_collection is None:
         abort(500, description="Database connection is not available.")

    new_submission = request.get_json()

    # Basic validation
    required_fields = ['judgeName', 'teamName', 'hackathonTrack', 'scores', 'submissionTimestamp']
    if not all(field in new_submission for field in required_fields):
        abort(400, description="Missing required fields in submission")

    if not isinstance(new_submission.get('scores'), dict):
         abort(400, description="Scores field must be an object")

    try:
        # Instead of reading/writing to a file, just insert the new document
        result = submissions_collection.insert_one(new_submission)
        print(f"Inserted new submission with id: {result.inserted_id}")
        return jsonify({"status": "success", "message": "Judgment submitted successfully!", "id": str(result.inserted_id)}), 201
    except Exception as e:
        print(f"Unexpected error during submission: {e}")
        abort(500, description="An internal server error occurred.")


@app.route('/api/get-results', methods=['GET'])
def get_results():
    """Reads and returns all submitted judging results from MongoDB."""
    if submissions_collection is None:
         abort(500, description="Database connection is not available.")
         
    try:
        # Find all documents in the collection
        all_results_cursor = submissions_collection.find()
        results_list = list(all_results_cursor)

        # IMPORTANT: MongoDB's _id is not JSON-serializable
        # We must convert it to a string for each document
        for result in results_list:
            result['_id'] = str(result['_id'])

        return jsonify(results_list), 200
    except Exception as e:
        print(f"Unexpected error retrieving results: {e}")
        abort(500, description="An internal server error occurred retrieving results.")

@app.route('/api/clear-results', methods=['POST'])
def clear_results():
    """
    Clears all results from the MongoDB collection.
    WARNING: This is insecure. Add authentication to protect this.
    """
    if submissions_collection is None:
         abort(500, description="Database connection is not available.")
         
    try:
        # Deletes all documents from the collection
        delete_result = submissions_collection.delete_many({})
        return jsonify({"status": "success", "message": f"Results cleared. {delete_result.deleted_count} submissions deleted."}), 200
    except Exception as e:
        print(f"Error clearing results: {e}")
        abort(500, description=f"Could not clear results: {str(e)}")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True) # Turn debug=False for production
