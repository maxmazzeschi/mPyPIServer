import os
import argparse
import json
from http.server import SimpleHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
from mimetypes import guess_type
import re


class PackageHandler:
    def __init__(self, directory):
        self.directory = directory
        self.generate_index()

    def generate_index(self):
        """Generate an HTML and JSON index of available packages."""
        print(f"looking into {self.directory}")
        files = [f for f in os.listdir(self.directory) if f.endswith(('.whl', '.tar.gz'))]
        self.index = {}
        print(f"files {files}")
        # Group files by package name (using the base name without version suffix)
        for file in files:
            # Extract the package name, version, and environment from the filename
            match = re.match(r'([a-zA-Z0-9_\-]+)-([0-9\.]+)-([a-zA-Z0-9\-]+)(\.whl|\.tar\.gz)', file)
            if match:
                name, version, env, ext = match.groups()
                if name not in self.index:
                    self.index[name] = []

                file_info = {
                    'filename': file,
                    'version': version,
                    'environment': env,
                    'type': ext,
                    'size': os.path.getsize(os.path.join(self.directory, file))
                }
                self.index[name].append(file_info)

        # Create the 'simple' directory if it doesn't exist
        simple_dir = os.path.join(self.directory, 'simple')
        os.makedirs(simple_dir, exist_ok=True)

        # Loop over packages and create directories for each package inside 'simple/'
        for package, versions in self.index.items():
            package_dir = os.path.join(simple_dir, package)
            os.makedirs(package_dir, exist_ok=True)

            # Create index.json for each package directory
            metadata_file = os.path.join(package_dir, 'index.json')
            with open(metadata_file, 'w') as f:
                # Create the package metadata in JSON format
                metadata = {
                    "name": package,
                    "versions": [v['version'] for v in versions]
                }
                json.dump(metadata, f)
            
            # Generate the HTML index for each package
            with open(os.path.join(package_dir, 'index.html'), 'w') as f:
                f.write('<html><body>\n')
                f.write('<h1>Available Versions</h1>\n')
                f.write('<table border="1"><tr><th>Version</th><th>Environment</th><th>Size (Bytes)</th><th>Type</th></tr>\n')
                for version_info in versions:
                    f.write(f'<tr><td><a href="{version_info["filename"]}">{version_info["filename"]}</a></td>'
                            f'<td>{version_info["environment"]}</td>'
                            f'<td>{version_info["size"]}</td>'
                            f'<td>{version_info["type"]}</td></tr>\n')
                f.write('</table>\n')
                f.write('</body></html>\n')

        # Generate the root index.html that links to packages
        index_path = os.path.join(self.directory, 'index.html')
        with open(index_path, 'w') as f:
            f.write('<html><body>\n')
            f.write('<h1>Available Packages</h1>\n')
            f.write('<ul>\n')
            for package in self.index.keys():
                f.write(f'<li><a href="simple/{package}/">{package}</a></li>\n')
            f.write('</ul>\n')
            f.write('</body></html>\n')
        print(self.index)


class PackageServer(SimpleHTTPRequestHandler):
    def do_GET(self):
        """Handle GET requests to serve the best matching package."""
        parsed_path = urlparse(self.path)
        package_handler = PackageHandler(self.directory)

        if parsed_path.path.startswith('/simple/'):
            path_parts = parsed_path.path.strip('/').split('/')

        # Serve Package Listing
        if len(path_parts) == 2:
            package_name = path_parts[1].replace("-", "_")
            print(f"searching for:{package_name}")
            package_versions = package_handler.index.get(package_name)

            if not package_versions:
                print("package not found")
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'Package not found')
                return

            # Extract environment information from headers
            user_agent = self.headers.get('User-Agent', '')
            python_version = self._extract_python_version(user_agent)
            platform_env = self._extract_platform_env(user_agent)

            # Try to match the best package based on Python version and environment
            best_package = self._find_best_match(package_versions, python_version, platform_env)

            print(f"best package is {best_package}")
            if best_package:
                self.send_response(301)
                self.send_header("Location", f"/simple/{package_name}/{best_package['filename']}")
                self.end_headers()
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'No suitable package found')
        # Serve Actual Package File
        elif len(path_parts) == 3:
            package_file = path_parts[2]
            file_path = os.path.join(self.directory, package_file)
            if os.path.isfile(file_path):
                self.send_response(200)
                self.send_header('Content-Type', guess_type(file_path)[0] or 'application/octet-stream')
                self.send_header('Content-Length', str(os.path.getsize(file_path)))
                self.end_headers()
                with open(file_path, 'rb') as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'File not found')


    def _extract_python_version(self, user_agent):
        """Extract Python version from the User-Agent header."""
        match = re.search(r'python/(\d+\.\d+)', user_agent)
        return match.group(1) if match else None

    def _extract_platform_env(self, user_agent):
        """Extract platform environment from the User-Agent header."""
        if 'Linux' in user_agent:
            return 'manylinux'
        elif 'Windows' in user_agent:
            return 'win'
        elif 'Darwin' in user_agent:
            return 'macos'
        return None

    def _find_best_match(self, package_versions, python_version, platform_env):
        """Find the best matching package based on the Python version and platform."""
        # Prioritize exact matches
        for pkg in package_versions:
            if python_version and f"cp{python_version.replace('.', '')}" in pkg['filename']:
                if platform_env and platform_env in pkg['filename']:
                    return pkg

        # Fallback to most recent version
        return max(package_versions, key=lambda p: [int(i) for i in re.findall(r'\d+', p['version'])])
   

    def get_environment_version(self, path):
        """Extract the environment or Python version from the path."""
        # Example patterns to extract cp39, py3, etc.
        match = re.search(r'-(cp\d{2}|py\d+)-', path)
        if match:
            return match.group(1)  # Return the environment version (e.g., cp39 or py3)
        return None


    def do_POST(self):
        """Handle POST requests for uploading packages."""
        parsed_path = urlparse(self.path)
        package_handler = PackageHandler(self.directory)

        if parsed_path.path == '/':
            # Handle PyPI package upload
            content_length = int(self.headers.get('Content-Length', 0))
            boundary = self.headers.get('Content-Type').split('boundary=')[-1]
            data = self.rfile.read(content_length)

            # Extract filename from form data
            parts = data.split(b'--' + boundary.encode())
            for part in parts:
                if b'filename="' in part:
                    filename = part.split(b'filename="')[1].split(b'"')[0].decode()
                    file_content = part.split(b'\r\n\r\n')[1].rsplit(b'\r\n', 1)[0]

                    if filename and filename.endswith(('.whl', '.tar.gz')):
                        file_path = os.path.join(self.directory, filename)
                        with open(file_path, 'wb') as f:
                            f.write(file_content)
                        print(f"Package {filename} uploaded successfully.")
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b'Upload successful')
                        package_handler.generate_index()
                        return

            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Invalid package upload')

        elif parsed_path.path == '/remove':
            filename = parse_qs(parsed_path.query).get('filename', [None])[0]
            if filename and package_handler.remove_package(filename):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'Removal successful')
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'Package not found')

        else:
            self.send_response(404)
            self.end_headers()


def start_server(directory, host='0.0.0.0', port=8082):
    """Start the HTTP server to serve PyPI-compatible API."""
    os.makedirs(directory, exist_ok=True)
    os.makedirs(os.path.join(directory, 'simple'), exist_ok=True)
    os.chdir(directory)
    PackageServer.directory = directory

    package_handler = PackageHandler(directory)
    package_handler.generate_index()
    server = HTTPServer(("0.0.0.0", port), PackageServer)
    print(f"Serving PyPI-compatible API on port {port}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down server...")
        server.shutdown()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Python Package Repository Server")
    parser.add_argument('--directory', type=str,default="C:\\temp\\packages", help="Directory to store packages")
    args = parser.parse_args()
    print(f"dir {args.directory}")
    start_server(args.directory)
