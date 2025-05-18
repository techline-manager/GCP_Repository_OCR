from flask import Flask, request, jsonify
from google.cloud import storage, documentai_v1 as documentai
import io
import json

app = Flask(__name__)

# ─── CONFIGURATION ────────────────────────────────────────────────
PROJECT_ID = "neon-net-459709-s0"
LOCATION = "eu"  # Updated based on the error you had earlier.
PROCESSOR_ID = "f3503305350e4b03"

@app.route("/process-invoice", methods=["POST"])
def process_invoice():
    try:
        data = request.get_json(force=True)
        bucket_name = data.get("bucket_name")
        file_name = data.get("file_name")

        if not all([bucket_name, file_name]):
            return jsonify({
                "status": "error",
                "message": "Missing 'bucket_name' or 'file_name'."
            }), 400

        # ─── Download the file from Google Cloud Storage ───────────────
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)

        if not blob.exists():
            return jsonify({
                "status": "error",
                "message": f"File '{file_name}' not found in bucket '{bucket_name}'."
            }), 404

        pdf_content = blob.download_as_bytes()

        # ─── Send to Document AI ──────────────────────────────────────
        client = documentai.DocumentProcessorServiceClient()
        processor_path = f"projects/592970298260/locations/eu/processors/f3503305350e4b03"


        raw_document = documentai.RawDocument(
            content=pdf_content,
            mime_type="application/pdf"
        )

        request_ai = documentai.ProcessRequest(
            name=processor_path,
            raw_document=raw_document
        )

        result = client.process_document(request=request_ai)
        document_json = json.loads(result.document.to_json())

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
    app.run(host="0.0.0.0", port=8080)
