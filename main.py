from flask import Flask, request, jsonify
from google.api_core.client_options import ClientOptions
from google.cloud import storage, documentai_v1 as documentai
from google.protobuf.json_format import MessageToDict # Keep MessageToDict
import io
import json

app = Flask(__name__)

# ─── CONFIGURATION ────────────────────────────────────────────────
PROJECT_ID = "neon-net-459709-s0"
LOCATION = "eu"  # Region where your processor is located.
PROCESSOR_ID = "f3503305350e4b03"

# FILE_PATH is now used in __main__ block, not globally read
# MIME_TYPE is defined where used

docai_client = documentai.DocumentProcessorServiceClient(client_options=ClientOptions(api_endpoint=f"{LOCATION}-documentai.googleapis.com"))
RESOURCE_NAME = docai_client.processor_path(PROJECT_ID, LOCATION, PROCESSOR_ID)

# Remove the global file read - it's not used in the Flask route and won't be used in the new function
# with open(FILE_PATH, "rb") as image:
#     image_content = image.read()

def process_gcs_document(bucket_name: str, file_name: str):
    """
    Downloads a document from GCS, processes it with Document AI,
    and uploads the result JSON back to GCS.
    """
    app.logger.info(f"Processing GCS file: gs://{bucket_name}/{file_name}")

    try:
        # ─── Download the file from Google Cloud Storage ───────────────
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(file_name)

        if not blob.exists():
            raise FileNotFoundError(f"File '{file_name}' not found in bucket '{bucket_name}'.")

        pdf_content = blob.download_as_bytes()
        app.logger.info(f"Downloaded {file_name} ({len(pdf_content)} bytes)")

        # ─── Process with Document AI ──────────────────────────────────
        raw_document = documentai.RawDocument(
            content=pdf_content,
            mime_type="application/pdf" # Assuming PDF based on original code and variable names
        )

        request_ai = documentai.ProcessRequest(
            name=RESOURCE_NAME,
            raw_document=raw_document
        )

        app.logger.info("Sending document to Document AI...")
        result = docai_client.process_document(request=request_ai)
        app.logger.info("Document processing completed.")

        # --- Debugging: Inspect result.document ---
        app.logger.info(f"Type of result.document: {type(result.document)}")
        if hasattr(result.document, 'DESCRIPTOR') and result.document.DESCRIPTOR:
            app.logger.info(f"result.document.DESCRIPTOR.full_name: {result.document.DESCRIPTOR.full_name}")
        else:
            app.logger.warning("result.document does not have a valid DESCRIPTOR attribute.")
        # --- End Debugging ---

        # ─── Save the result to a JSON file ─────────────────────────
        try:
            # If MessageToDict(result.document) was causing the "DESCRIPTOR" error,
            # and you only need the text for now, you can remove or comment out this line:
            # document_dict = MessageToDict(result.document)

            # Extract only the text and save it in a simple dictionary
            text_only_dict = {"extracted_text": result.document.text}
            document_json = json.dumps(text_only_dict, indent=2)
        except Exception as e_serialize:
            app.logger.error(f"Error during JSON serialization of extracted text: {e_serialize}")
            raise  # Re-raise the exception to be caught by the main try-except block

        # ─── Upload JSON Result Back to GCS ─────────────────────────
        output_file_name = f"{file_name.rsplit('.', 1)[0]}_ocr_completed.json"
        output_blob = bucket.blob(output_file_name)
        output_blob.upload_from_string(document_json, content_type="application/json")
        app.logger.info(f"Uploaded result to gs://{bucket_name}/{output_file_name}")

        return {
            "status": "success",
            "message": f"Processed '{file_name}' and uploaded result as '{output_file_name}'.",
            "output_gcs_uri": f"gs://{bucket_name}/{output_file_name}"
        }

    except FileNotFoundError as e:
        app.logger.error(str(e))
        return {
            "status": "error",
            "message": str(e)
        }
    except Exception as e:
        app.logger.exception("Processing failed")
        return {
            "status": "error",
            "message": str(e)
        }


@app.route("/process-invoice", methods=["POST"])
def process_invoice():
    try:
        data = request.get_json(force=True)
        bucket_name = data.get("bucket_name")
        file_name = data.get("file_name")

        if not all([bucket_name, file_name]):
            return jsonify({
                "status": "ERROR - MISSING ",
                "message": "Missing 'bucket_name' or 'file_name'."
            }), 400

        # Call the refactored processing function
        result = process_gcs_document(bucket_name, file_name)

        # Map the result structure to Flask response
        if result.get("status") == "success":
            return jsonify(result), 200
        elif result.get("status") == "error" and "not found" in result.get("message", "").lower():
            return jsonify({
                "status": "ERROR - NOT FOUND",
                "message": f"File '{file_name}' not found in bucket '{bucket_name}'."
            }), 404
        else:
            return jsonify(result), 500

    except Exception as e:
        # This catch is for errors *before* calling process_gcs_document (e.g., JSON parsing)
        app.logger.exception("Flask route processing failed")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

if __name__ == "__main__":
    # Define the GCS file path you want to process when running the script directly
    # You can change this to any gs:// path you need for direct processing
    FILE_PATH_FOR_DIRECT_RUN = "gs://neon-net-459709-s0/ocr_test.pdf"

    # Instead of running the Flask app, call the processing function directly
    if FILE_PATH_FOR_DIRECT_RUN.startswith("gs://"):
        # Parse bucket and file name from the gs:// path
        parts = FILE_PATH_FOR_DIRECT_RUN[5:].split('/', 1) # Split "gs://bucket/path/to/file" into ["bucket", "path/to/file"]
        if len(parts) == 2:
            main_bucket_name = parts[0]
            main_file_name = parts[1]
            print(f"Running direct processing for {FILE_PATH_FOR_DIRECT_RUN}")
            processing_result = process_gcs_document(main_bucket_name, main_file_name)
            print("\n--- Processing Result ---")
            print(json.dumps(processing_result, indent=2))
            print("-------------------------")
        else:
            print(f"Error: Invalid GCS path format in FILE_PATH_FOR_DIRECT_RUN: {FILE_PATH_FOR_DIRECT_RUN}")
    else:
        print(f"Error: FILE_PATH_FOR_DIRECT_RUN is not a GCS path: {FILE_PATH_FOR_DIRECT_RUN}")

    # If you still want to run the Flask app alongside, you could add logic here
    # like checking a command-line argument or environment variable.
    # For this request, we've replaced the Flask run with the direct processing call.
    # app.run(host="0.0.0.0", port=8080) # Commented out to run direct processing
