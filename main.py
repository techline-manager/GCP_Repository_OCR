from flask import Flask, request, jsonify

import io
import json

# Google Cloud clients
from google.cloud import storage, documentai_v1 as documentai
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

app = Flask(__name__)

#region my code

# ─── YOUR CONFIG ───────────────────────────────────────────
PROJECT_ID       = "neon-net-459709-s0"
LOCATION         = "eu"
PROCESSOR_ID     = "f3503305350e4b03"
GDRIVE_FOLDER_ID = "1xpiH4-kIVTjgSb0PT1-UwsclzMYtHoPH"  # your real folder ID

# Use Application Default Credentials on Cloud Run
# (no keyfile path needed unless you explicitly mount one)
credentials = None

@app.route("/process-invoice", methods=["POST"])
def process_invoice():
    try:
        data        = request.get_json(force=True)
        bucket_name = data.get("bucket_name", "ai-test-bucket-ocr")
        file_name   = data.get("file_name",   "Invoice.pdf")

        # ─── Download PDF from GCS ───────────────────────────
        storage_client = storage.Client()                  # ADC
        bucket         = storage_client.bucket(bucket_name)
        blob           = bucket.blob(file_name)
        pdf_content    = blob.download_as_bytes()

        # ─── Send to Document AI ────────────────────────────
        client         = documentai.DocumentProcessorServiceClient()
        processor_path = "https://eu-documentai.googleapis.com/v1/projects/592970298260/locations/eu/processors/f3503305350e4b03"

        raw_document = documentai.RawDocument(
            content  = pdf_content,
            mime_type= "application/pdf"
        )
        request_ai = documentai.ProcessRequest(
            name        = processor_path,
            raw_document= raw_document
        )
        result        = client.process_document(request=request_ai)
        document_json = json.loads(result.document.to_json())

    except Exception as e:
        app.logger.exception("Document AI failed")
        return jsonify({
            "status": "error",
            "stage":  "document-ai",
            "detail": str(e)
        }), 500

    try:
        # ─── Upload result JSON to Drive ────────────────────
        drive_service = build("drive", "v3")              # ADC
        file_metadata = {
            "name":    f"{file_name}.json",
            "parents": [GDRIVE_FOLDER_ID]
        }
        media = MediaIoBaseUpload(
            io.BytesIO(json.dumps(document_json).encode()),
            mimetype="application/json"
        )
        drive_service.files().create(
            body       = file_metadata,
            media_body = media,
            fields     = "id"
        ).execute()

    except Exception as e:
        app.logger.exception("Drive upload failed")
        return jsonify({
            "status": "error",
            "stage":  "drive-upload",
            "detail": str(e)
        }), 500

    return jsonify({
        "status":  "success",
        "message": f"Processed {file_name} and saved JSON to Drive."
    })


#endregion