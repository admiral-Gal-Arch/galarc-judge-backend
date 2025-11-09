from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import os
from pymongo import MongoClient
from bson.objectid import ObjectId
import jwt  # New import
from datetime import datetime, timedelta, timezone  # New imports
from functools import wraps  # New import

app = Flask(__name__)
CORS(app)

# --- Config & MongoDB Setup ---
MONGODB_URI = os.environ.get('MONGODB_URI')
# Get new secret keys from environment
SECRET_KEY = os.environ.get('SECRET_KEY')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

if not MONGODB_URI or not SECRET_KEY or not ADMIN_PASSWORD:
    raise RuntimeError("Missing one or more environment variables: MONGODB_URI, SECRET_KEY, ADMIN_PASSWORD")

try:
    client = MongoClient(MONGODB_URI)
    db = client.get_database("hackathonDB")
    submissions_collection = db.get_collection("submissions")
    client.server_info()
    print("Successfully connected to MongoDB.")
except Exception as e:
    print(f"ERROR: Could not connect to MongoDB: {e}")
    client = None
    submissions_collection = None
# --- End of Setup ---


# --- NEW: Token Authentication Wrapper ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Check if 'Authorization' header is present
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                # Header should be in 'Bearer <token>' format
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({"message": "Malformed 'Authorization' header."}), 401

        if not token:
            return jsonify({"message": "Token is missing!"}), 401

        try:
            # Decode the token using the SECRET_KEY
            data = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired!"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Token is invalid!"}), 401

        return f(*args, **kwargs)
    return decorated
# --- End of Token Wrapper ---


# --- NEW: Admin Login Endpoint ---
@app.route('/api/admin-login', methods=['POST'])
def admin_login():
    """Receives admin password and returns a JWT."""
    if not request.is_json:
        abort(400, description="Request must be JSON")
    
    data = request.get_json()
    password = data.get('password')

    if not password:
        abort(400, description="Password is required.")

    # Check the password against the environment variable
    if password == ADMIN_PASSWORD:
        # Password is correct, create a token
        token = jwt.encode({
            'admin': True,
            # Token expires in 8 hours
            'exp': datetime.now(timezone.utc) + timedelta(hours=8)
        }, SECRET_KEY, algorithm="HS256")
        
        return jsonify({"status": "success", "message": "Login successful.", "token": token}), 200
    else:
        # Invalid credentials
        return jsonify({"message": "Invalid credentials."}), 401
# --- End of Admin Login ---


# --- Unprotected Endpoint ---
@app.route('/api/submit-judging', methods=['POST'])
def submit_judging():
    """Receives judging data and inserts it into MongoDB. This is still public."""
    if not request.is_json:
        abort(400, description="Request must be JSON")
    
    # --- FIX APPLIED ---
    if submissions_collection is None:
         abort(500, description="Database connection is not available.")

    new_submission = request.get_json()
    required_fields = ['judgeName', 'teamName', 'hackathonTrack', 'scores', 'submissionTimestamp']
    if not all(field in new_submission for field in required_fields):
        abort(400, description="Missing required fields in submission")

    if not isinstance(new_submission.get('scores'), dict):
         abort(400, description="Scores field must be an object")

    try:
        result = submissions_collection.insert_one(new_submission)
        return jsonify({"status": "success", "message": "Judgment submitted successfully!", "id": str(result.inserted_id)}), 201
    except Exception as e:
        print(f"Unexpected error during submission: {e}")
        abort(500, description="An internal server error occurred.")


# --- MODIFIED: Protected Endpoint ---
@app.route('/api/get-results', methods=['GET'])
@token_required  # <-- This decorator protects the route
def get_results():
    """Reads and returns all results. Requires a valid admin token."""
    
    # --- FIX APPLIED ---
    if submissions_collection is None:
         abort(500, description="Database connection is not available.")
         
    try:
        all_results_cursor = submissions_collection.find()
        results_list = list(all_results_cursor)
        for result in results_list:
            result['_id'] = str(result['_id'])

        return jsonify(results_list), 200
    except Exception as e:
        print(f"Unexpected error retrieving results: {e}")
        abort(500, description="An internal server error occurred retrieving results.")


# --- MODIFIED: Protected Endpoint ---
@app.route('/api/clear-results', methods=['POST'])
@token_required  # <-- This decorator also protects the clear route
def clear_results():
    """Clears all results. Requires a valid admin token."""
    
    # --- FIX APPLIED ---
    if submissions_collection is None:
         abort(500, description="Database connection is not available.")
         
    try:
        delete_result = submissions_collection.delete_many({})
        return jsonify({"status": "success", "message": f"Results cleared. {delete_result.deleted_count} submissions deleted."}), 200
    except Exception as e:
        print(f"Error clearing results: {e}")
        abort(500, description=f"Could not clear results: {str(e)}")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
