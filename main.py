from flask import Flask, request, jsonify
import io
import json

# Google Cloud clients
from google.cloud import storage, documentai_v1 as documentai
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from ocr_processor import get_gcs_file as get_gcs_file_func


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
    app.logger.info("Received request to process invoice.")
    get_gcs_file_func()
    # Call the function from ocr_processor.py

    
""" @app.route("/process-invoice", methods=["POST"])
def process_invoice():
    bucket_name = None
    file_name = None
    try:
        app.logger.info(f"Raw request data: {request.data}")
        data = request.get_json(force=True)
        if not data:
            raise ValueError("No JSON payload received.")

        bucket_name = data.get("bucket_name")
        file_name = data.get("file_name")

        if not bucket_name or not file_name:
            return jsonify({
                "status": "error",
                "stage": "request-validation",
                "detail": "Missing 'bucket_name' or 'file_name' in payload."
            }), 400

        app.logger.info(f"Received bucket: {bucket_name}, file: {file_name}")

    except Exception as e:
        app.logger.exception("Request parsing/validation failed")
        return jsonify({"status": "error", "stage": "request-parsing", "detail": str(e)}), 400

    pdf_content = None
    document_json = None
    gcs_bucket = None # To store the bucket object for later use

    try:
        # ─── Download PDF from GCS ───────────────────────────
        storage_client = storage.Client()
        gcs_bucket = storage_client.bucket(bucket_name)
        blob = gcs_bucket.blob(file_name)

        if not blob.exists():
            app.logger.error(f"File '{file_name}' not found in bucket '{bucket_name}'.")
            return jsonify({
                "status": "error",
                "stage": "gcs-download",
                "detail": f"File '{file_name}' not found in bucket '{bucket_name}'."
            }), 404

        pdf_content = blob.download_as_bytes()
        app.logger.info(f"Successfully downloaded '{file_name}' from bucket '{bucket_name}'.")

    except Exception as e:
        app.logger.exception(f"GCS download failed for '{file_name}' from bucket '{bucket_name}'.")
        return jsonify({
            "status": "error",
            "stage": "gcs-download",
            "detail": str(e)
        }), 500

    try:
        # ─── Send to Document AI ────────────────────────────
        # Ensure client uses the correct regional endpoint
        client_options = {"api_endpoint": f"{LOCATION}-documentai.googleapis.com"}
        docai_client = documentai.DocumentProcessorServiceClient(client_options=client_options)

        # Construct the processor name using configured IDs.
        # Note: Your original code used a hardcoded project ID '592970298260'.
        # If the processor is in that project, use that ID instead of PROJECT_ID.
        # For this example, I'm assuming the processor is in the project defined by PROJECT_ID.
        # If it's in '592970298260', change PROJECT_ID to "592970298260" below.
        processor_name = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)
        # If using the hardcoded project ID:
        # processor_name = docai_client.processor_path("592970298260", LOCATION, PROCESSOR_ID)

        raw_document = documentai.RawDocument(content=pdf_content, mime_type="application/pdf")
        request_ai = documentai.ProcessRequest(name=processor_name, raw_document=raw_document)
        
        app.logger.info(f"Sending request to Document AI processor: {processor_name}")
        result = docai_client.process_document(request=request_ai)

        # --- Debugging and robust handling for document conversion ---
        if result and result.document:
            app.logger.info(f"Type of result.document: {type(result.document)}")
            try:
                json_string_from_docai = result.document.to_json()
            except Exception as e_to_json:
                app.logger.error(f"Error calling result.document.to_json(): {e_to_json}")
                # Log some basic, hopefully safe-to-access, attributes of result.document
                error_doc_details = "Unable to retrieve further document details during to_json() error."
                try:
                    # These attributes should generally exist on a valid Document object
                    num_pages = len(result.document.pages) if result.document.pages else 0
                    text_len = len(result.document.text) if result.document.text else 0
                    num_entities = len(result.document.entities) if result.document.entities else 0
                    error_doc_details = (
                        f"result.document attributes at time of to_json() error: "
                        f"Number of pages: {num_pages}, Length of text: {text_len}, Number of entities: {num_entities}."
                    )
                except Exception as e_details:
                    error_doc_details = f"Could not retrieve basic attributes from result.document when to_json() failed: {e_details}"
                app.logger.error(error_doc_details)
                raise # Re-raise the original to_json error to ensure the main error handler catches it
            
            # Log a snippet of the JSON string to check its validity
            log_snippet = (json_string_from_docai[:500] + '...') if len(json_string_from_docai) > 500 else json_string_from_docai
            app.logger.info(f"Raw JSON string snippet from Document AI: {log_snippet}")

            if not json_string_from_docai: # Check if the string is empty
                app.logger.error("result.document.to_json() returned an empty string.")
                raise ValueError("Document AI's to_json() method returned an empty string.")

            document_json = json.loads(json_string_from_docai)
        else:
            app.logger.error(f"Document AI result is missing or result.document is None. Result object: {result}")
            raise ValueError("Document AI processing returned no document or an empty document attribute.")
        # --- End Debugging ---

        app.logger.info(f"Successfully processed '{file_name}' with Document AI.")
    except Exception as e:
        app.logger.exception("Document AI processing failed")
        return jsonify({
            "status": "error",
            "stage": "document-ai", # Corrected stage
            "detail": str(e)
        }), 500

    try:
        # ─── Upload result JSON to GCS ────────────────────
        processed_file_name = f"{file_name.rsplit('.', 1)[0]}_OCRed.json" # e.g., mydoc_OCRed.json
        if not gcs_bucket: # Should have been initialized during download
             raise Exception("GCS bucket object not initialized. This should not happen if PDF download succeeded.")
        result_blob = gcs_bucket.blob(processed_file_name)
        result_blob.upload_from_string(
            data=json.dumps(document_json, indent=2), # Save with indentation for readability
            content_type="application/json"
        )
        app.logger.info(f"Successfully uploaded OCR results for '{file_name}' to GCS bucket '{bucket_name}' as '{processed_file_name}'.")
    except Exception as e:
        app.logger.exception(f"GCS upload of OCR JSON failed for '{processed_file_name}'")
        return jsonify({
            "status": "error",
            "stage": "gcs-upload-json",
            "detail": str(e)
        }), 500

    return jsonify({
        "status": "success",
        "message": f"Processed {file_name} and saved JSON to GCS bucket {bucket_name} as {processed_file_name}."
    }), 200
 """