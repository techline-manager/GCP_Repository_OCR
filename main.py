from flask import Flask, request, jsonify
from google.cloud import storage, documentai_v1 as documentai
from google.protobuf.json_format import MessageToDict
import io
import json

app = Flask(__name__)

# ─── CONFIGURATION ────────────────────────────────────────────────
PROJECT_ID = "neon-net-459709-s0"
LOCATION = "eu"  # Region where your processor is located.
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
        client = documentai.DocumentProcessorServiceClient(
            client_options={"api_endpoint": "eu-documentai.googleapis.com"}
        )
        processor_path = f"projects/{PROJECT_ID}/locations/{LOCATION}/processors/{PROCESSOR_ID}"

        raw_document = documentai.RawDocument(
            content=pdf_content,
            mime_type="application/pdf"
        )

        request_ai = documentai.ProcessRequest(
            name=processor_path,
            raw_document=raw_document
        )

        result = client.process_document(request=request_ai)

          # ─── Convert Protobuf to Dictionary ─────────────────────────
        document_dict = MessageToDict(result.document)
        document_json = json.dumps(document_dict)

 # ─── Upload JSON Result Back to GCS ─────────────────────────
        output_file_name = f"{file_name.rsplit('.', 1)[0]}_ocr_completed.json"
        output_blob = bucket.blob(output_file_name)
        output_blob.upload_from_string(document_json, content_type="application/json")


        return jsonify({
            "status": "success",
            "message": f"Processed '{file_name}' and uploaded result as '{output_file_name}'."
        })
    
    except Exception as e:
        app.logger.exception("Processing failed")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
