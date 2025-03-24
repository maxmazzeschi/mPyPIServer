import os
from flask import Flask, request, jsonify, send_from_directory, render_template_string
import re


app = Flask(__name__)

# Load environment variables
UPLOAD_FOLDER = "/packages"
LISTEN_PORT = int(os.getenv("LISTEN_PORT", 8082))

os.mkdir(UPLOAD_FOLDER, exist_ok=True)

@app.route("/")
def index():
    return f"Serving packages from {UPLOAD_FOLDER} on port {LISTEN_PORT}"
def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()


@app.route("/simple/<package>/", methods=["GET"])
def serve_package(package):
    
    print("Serving package:", package)
    package = normalize(package)
    # List all files in the upload folder matching the package name
    files = [f for f in os.listdir(UPLOAD_FOLDER) if package in normalize(f)]
    if not files:
        return jsonify({"error": "Package not found"}), 404

    # Generate an HTML response with links to the files
    html_template = """
    <!DOCTYPE html>
    <html>
    <head><title>Simple Index</title></head>
    <body>
        <h1>Links for {{ package }}</h1>
        {% for file in files %}
        <a href="/packages/{{ file }}">{{ file }}</a><br>
        {% endfor %}
    </body>
    </html>
    """
    return render_template_string(html_template, package=package, files=files)

@app.route("/packages/<filename>", methods=["GET"])
def serve_file(filename):
    print("Serving file:", filename)
    # Serve the actual file from the upload folder
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    if not os.path.exists(file_path):
        return jsonify({"error": "File not found"}), 404
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/", methods=["POST"])
def upload_via_twine():
    if "content" not in request.files:  # Check for 'content' instead of 'file'
        print("No file part")   
        return jsonify({"error": "No file part"}), 400
    file = request.files["content"]  # Access the file using 'content'
    if file.filename == "":
        print("No selected file")
        return jsonify({"error": "No selected file"}), 400

    # Optional: Validate username and password if required
    if False:
        username = request.form.get("username")
        password = request.form.get("password")
        if not username or not password:
            print("Missing username or password")
            return jsonify({"error": "Missing username or password"}), 400

    # Save the uploaded file
    file.save(os.path.join(UPLOAD_FOLDER, file.filename))
    return jsonify({"message": "File uploaded successfully via Twine"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=LISTEN_PORT)
