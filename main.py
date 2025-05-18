from flask import Flask, request, jsonify
import io
import json

# Google Cloud clients
from google.cloud import storage, documentai_v1 as documentai
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

app = Flask(__name__)

#region CONFIGURATION

PROJECT_ID = "neon-net-459709-s0"
LOCATION = "eu"
PROCESSOR_ID = "f3503305350e4b03"

# This is the ID of the folder in Google Drive where the processed files will be stored
GDRIVE_FOLDER_ID = "1xpiH4-kIVTjgSb0PT1-UwsclzMYtHoPH"  # Replace with your real folder ID

credentials = None  # Using Application Default Credentials

#endregion


#region FUNCTION DEFINITIONS

@app.route("/process-invoice", methods=["POST"])
def process_invoice():
    """
    Tests receiving bucket_name and file_name from a POST request
    and returns a simplified default response.
    """
    # Original implementation
    """
    try:
        data = request.get_json()
        if not data:
            app.logger.error("No JSON payload received.")
            return jsonify({"status": "error", "message": "No JSON payload received."}), 400

        bucket_name = data.get("bucket_name")
        file_name = data.get("file_name")

        if not bucket_name or not file_name:
            app.logger.error("Missing 'bucket_name' or 'file_name' in payload.")
            return jsonify({
                "status": "error",
                "message": "Missing 'bucket_name' or 'file_name' in payload."
            }), 400

        app.logger.info(f"Received bucket_name: {bucket_name}")
        app.logger.info(f"Received file_name: {file_name}")

        return jsonify({
            "status": "success",
            "message": "Parameters received successfully.",
            "received_bucket": bucket_name,
            "received_file": file_name
        }), 200

    except Exception as e:
        app.logger.exception("Error processing /process-invoice request")
        return jsonify({"status": "error", "message": str(e)}), 500
    """
    
    # New simplified implementation
    try:
        data = request.get_json()
        bucket_name = data.get("bucket_name")
        file_name = data.get("file_name")
        
        return jsonify({
            "status": "success",
            "message": "Request received successfully",
            "received_data": {
                "bucket_name": bucket_name,
                "file_name": file_name
            }
        }), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
#endregion

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)