from flask import Flask, request, jsonify, abort
from flask_cors import CORS
import os
from pymongo import MongoClient
from bson.objectid import ObjectId
import jwt
from datetime import datetime, timedelta, timezone
from functools import wraps

app = Flask(__name__)
CORS(app)

# --- Config & MongoDB Setup ---
MONGODB_URI = os.environ.get('MONGODB_URI')
SECRET_KEY = os.environ.get('SECRET_KEY')
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

if not MONGODB_URI or not SECRET_KEY or not ADMIN_PASSWORD:
    raise RuntimeError("Missing one or more environment variables: MONGODB_URI, SECRET_KEY, ADMIN_PASSWORD")

try:
    client = MongoClient(MONGODB_URI)
    db = client.get_database("hackathonDB")
    submissions_collection = db.get_collection("submissions")
    # NEW: Collection to store the release state
    app_state_collection = db.get_collection("app_state")
    client.server_info()
    print("Successfully connected to MongoDB.")
except Exception as e:
    print(f"ERROR: Could not connect to MongoDB: {e}")
    client = None
    submissions_collection = None
    app_state_collection = None
# --- End of Setup ---


# --- Token Authentication Wrapper (Unchanged) ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({"message": "Malformed 'Authorization' header."}), 401
        if not token:
            return jsonify({"message": "Token is missing!"}), 401
        try:
            jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        except jwt.ExpiredSignatureError:
            return jsonify({"message": "Token has expired!"}), 401
        except jwt.InvalidTokenError:
            return jsonify({"message": "Token is invalid!"}), 401
        return f(*args, **kwargs)
    return decorated


# --- Admin Login Endpoint (Unchanged) ---
@app.route('/api/admin-login', methods=['POST'])
def admin_login():
    if not request.is_json:
        abort(400, description="Request must be JSON")
    password = request.get_json().get('password')
    if not password:
        abort(400, description="Password is required.")
    
    if password == ADMIN_PASSWORD:
        token = jwt.encode({
            'admin': True,
            'exp': datetime.now(timezone.utc) + timedelta(hours=8)
        }, SECRET_KEY, algorithm="HS256")
        return jsonify({"status": "success", "message": "Login successful.", "token": token}), 200
    else:
        return jsonify({"message": "Invalid credentials."}), 401


# --- Public Submission Endpoint (Unchanged) ---
@app.route('/api/submit-judging', methods=['POST'])
def submit_judging():
    if not request.is_json:
        abort(400, description="Request must be JSON")
    if submissions_collection is None:
         abort(500, description="Database connection is not available.")
    
    new_submission = request.get_json()
    # ... (validation code omitted for brevity) ...
    try:
        result = submissions_collection.insert_one(new_submission)
        return jsonify({"status": "success", "message": "Judgment submitted successfully!", "id": str(result.inserted_id)}), 201
    except Exception as e:
        abort(500, description="An internal server error occurred.")


# --- MODIFIED: Public Results Endpoint ---
@app.route('/api/get-results', methods=['GET'])
def get_results():
    """
    Publicly returns results ONLY IF they have been released by an admin.
    """
    if submissions_collection is None or app_state_collection is None:
         abort(500, description="Database connection is not available.")

    # 1. Check the release status from the database
    status_doc = app_state_collection.find_one({"_id": "release_config"})
    
    # 2. If doc doesn't exist OR results_released is False, block the request
    if not status_doc or not status_doc.get("results_released", False):
        abort(403, description="Results have not been released by the admin yet.")

    # 3. If released, proceed to get results
    try:
        all_results_cursor = submissions_collection.find()
        results_list = list(all_results_cursor)
        for result in results_list:
            result['_id'] = str(result['_id'])
        return jsonify(results_list), 200
    except Exception as e:
        print(f"Unexpected error retrieving results: {e}")
        abort(500, description="An internal server error occurred retrieving results.")


# --- NEW: Admin-Only Endpoints ---

@app.route('/api/results-status', methods=['GET'])
@token_required
def get_results_status():
    """Admin-only: Checks if results are currently released."""
    if app_state_collection is None:
        abort(500, description="Database connection is not available.")
        
    status_doc = app_state_collection.find_one({"_id": "release_config"})
    is_released = status_doc.get("results_released", False) if status_doc else False
    return jsonify({"status": "success", "results_released": is_released}), 200

@app.route('/api/release-results', methods=['POST'])
@token_required
def release_results():
    """Admin-only: Sets the results_released flag to True."""
    if app_state_collection is None:
        abort(500, description="Database connection is not available.")
        
    try:
        # upsert=True creates the document if it doesn't exist
        app_state_collection.update_one(
            {"_id": "release_config"},
            {"$set": {"results_released": True}},
            upsert=True
        )
        return jsonify({"status": "success", "message": "Results have been publicly released."}), 200
    except Exception as e:
        abort(500, description=f"Could not release results: {str(e)}")

@app.route('/api/retract-results', methods=['POST'])
@token_required
def retract_results():
    """Admin-only: Sets the results_released flag to False."""
    if app_state_collection is None:
        abort(500, description="Database connection is not available.")
        
    try:
        app_state_collection.update_one(
            {"_id": "release_config"},
            {"$set": {"results_released": False}},
            upsert=True
        )
        return jsonify({"status": "success", "message": "Results have been retracted and are now private."}), 200
    except Exception as e:
        abort(500, description=f"Could not retract results: {str(e)}")


# --- Admin-Only Clear Endpoint (Unchanged) ---
@app.route('/api/clear-results', methods=['POST'])
@token_required
def clear_results():
    """Admin-only: Clears all submissions."""
    if submissions_collection is None:
         abort(500, description="Database connection is not available.")
    try:
        delete_result = submissions_collection.delete_many({})
        return jsonify({"status": "success", "message": f"Results cleared. {delete_result.deleted_count} submissions deleted."}), 200
    except Exception as e:
        abort(500, description=f"Could not clear results: {str(e)}")


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
