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
        data = request.get_json()
        bucket_name = data.get("bucket_name")
        file_name = data.get("file_name")
        file_data_b64 = data.get("file_data")  # Base64 encoded content

        if not all([bucket_name, file_name, file_data_b64]):
            return jsonify({
                "status": "error",
                "message": "Missing 'bucket_name', 'file_name', or 'file_data'."
            }), 400

        # Decode the base64 content
        pdf_content = base64.b64decode(file_data_b64)

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
