from flask import Flask, request, jsonify
from google.cloud import documentai_v1 as documentai

app = Flask(__name__)

# ─── YOUR CONFIG ───────────────────────────────────────────
PROJECT_ID = "neon-net-459709-s0"
LOCATION = "eu"
PROCESSOR_ID = "f3503305350e4b03"  # Your actual processor ID

@app.route("/process-invoice", methods=["POST"])
def process_invoice():
    try:
        data = request.get_json(force=True)
        bucket_name = data.get("bucket_name")
        file_name = data.get("file_name")

        if not all([bucket_name, file_name]):
            return jsonify({
                "status": "error",
                "message": "Missing 'bucket_name' or 'file_name' in request."
            }), 400

        # ─── Build GCS URI ─────────────────────────────────────
        gcs_uri = f"gs://{bucket_name}/{file_name}"

        # ─── Initialize Document AI Client ─────────────────────
        client = documentai.DocumentProcessorServiceClient()
        processor_path = client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

        # ─── Prepare GCS Document Input ────────────────────────
        gcs_document = documentai.GcsDocument(
            gcs_uri=gcs_uri,
            mime_type="application/pdf"
        )

        document_input_config = documentai.DocumentInputConfig(
            gcs_document=gcs_document
        )

        # ─── Send Request to Document AI ───────────────────────
        request_ai = documentai.ProcessRequest(
            name=processor_path,
            document_input_config=document_input_config
        )

        result = client.process_document(request=request_ai)
        document_json = result.document.to_json()

        return jsonify({
            "status": "success",
            "document_result": document_json
        })

    except Exception as e:
        app.logger.exception("Error processing invoice")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
