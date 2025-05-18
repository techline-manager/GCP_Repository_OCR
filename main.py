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
GDRIVE_FOLDER_ID = "1xpiH4-kIVTjgSb0PT1-UwsclzMYtHoPH"  # Replace with your real folder ID

credentials = None  # Using Application Default Credentials

#endregion

@app.route("/process-invoice", methods=["POST"])
def process_invoice():
    try:
        # Log raw request data for debugging
        app.logger.info(f"Raw request data: {request.data}")

        # Try parsing the JSON payload
        data = request.get_json(force=True)
        if not data:
            raise ValueError("No JSON payload received.")

        bucket_name = data.get("bucket_name")
        file_name = data.get("file_name")

        if not bucket_name or not file_name:
            raise ValueError("Missing 'bucket_name' or 'file_name' in payload.")

        app.logger.info(f"Received bucket: {bucket_name}, file: {file_name}")

        # ─── Download PDF from GCS ───────────────────────────
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)
        pdf_content = blob.download_as_bytes()

        # ─── Send to Document AI ────────────────────────────
        client = documentai.DocumentProcessorServiceClient()
        processor_path = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

        raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
        request_ai = documentai.ProcessRequest(name=processor_path, raw_document=raw_document)
        result = client.process_document(request=request_ai)
        document_json = json.loads(result.document.to_json())

    except Exception as e:
        app.logger.exception("Document AI processing failed")
        return jsonify({
            "status": "error",
            "stage": "document-ai",
            "detail": str(e)
        }), 500
    
    try:
        # ─── Upload result JSON to GCS ────────────────────
        processed_file_name = f"{file_name}_OCRed.json"
        result_blob = bucket.blob(processed_file_name)
        result_blob.upload_from_string(
            data=json.dumps(document_json),
            content_type="application/json"
        )

    except Exception as e:
        app.logger.exception("GCS upload failed")
        return jsonify({
            "status": "error",
            "stage": "gcs-upload",
            "detail": str(e)
        }), 500

    return jsonify({
        "status": "success",
        "message": f"Processed {file_name} and saved JSON to Drive."
    }), 200
