from flask import Flask, request, jsonify
import io
import json
import base64
import os


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
    try:
        # ─── Get the file data from the request ────────────────────────────
        data = request.args  # If sent as query parameters or headers, adjust accordingly
        bucket_name = data.get("bucket_name")
        file_name = data.get("file_name")
        file_data_raw_binary = request.data

        if not all([bucket_name, file_name, file_data_raw_binary]):
            return jsonify({
                "status": "error",
                "message": "Missing 'bucket_name', 'file_name', or 'file_data'."
            }), 400

        # If Document AI expects Base64, encode it
        file_data_b64 = base64.b64encode(file_data_raw_binary).decode("utf-8")

        # Otherwise, use raw binary directly
        pdf_content = file_data_b64  

        # ─── Send to Document AI ────────────────────────────
        client = documentai.DocumentProcessorServiceClient()
        processor_path = client.processor_path("592970298260", "eu", "f3503305350e4b03")

        raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
        request_ai = documentai.ProcessRequest(name=processor_path, raw_document=raw_document)
        result = client.process_document(request=request_ai)
        document_json = result.document.to_json()

        return jsonify({
            "status": "success",
            "document_result": document_json
        })

    except Exception as e:
        app.logger.exception("Processing failed")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
