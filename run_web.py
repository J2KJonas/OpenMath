#!/usr/bin/env python3
"""
OpenMath WebApp Local Development Server
Usage:
    python run_web.py
Starts an HTTP server and opens the browser to the OpenMath WebApp.
"""

import os
import sys
import webbrowser
from http.server import HTTPServer, SimpleHTTPRequestHandler
import socket

PORT = 8000

class OpenMathHTTPRequestHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # Enable CORS and shared-array headers for WebAssembly
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cross-Origin-Opener-Policy", "same-origin")
        self.send_header("Cross-Origin-Embedder-Policy", "require-corp")
        super().end_headers()

    def guess_type(self, path):
        if path.endswith(".js"):
            return "application/javascript"
        if path.endswith(".json"):
            return "application/json"
        if path.endswith(".css"):
            return "text/css"
        if path.endswith(".png"):
            return "image/png"
        return super().guess_type(path)


def find_free_port(start_port=8000):
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def main():
    # Ensure current working directory is the project root
    project_root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(project_root)

    # Re-generate cas_bundle.json if bundle_cas.py exists
    bundle_script = os.path.join(project_root, "web", "bundle_cas.py")
    if os.path.isfile(bundle_script):
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("bundle_cas", bundle_script)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            if hasattr(mod, "bundle_cas"):
                mod.bundle_cas()
        except Exception as e:
            print(f"[!] Note: Could not auto-rebundle cas_engine: {e}")

    port = find_free_port(PORT)
    url = f"http://localhost:{port}/web/index.html"

    print("=" * 65)
    print("       OpenMath WebApp — Local Development Server")
    print("=" * 65)
    print(f" Serving directory : {project_root}")
    print(f" Local WebApp URL   : {url}")
    print(" Press Ctrl+C to terminate server.")
    print("=" * 65)

    server = HTTPServer(("127.0.0.1", port), OpenMathHTTPRequestHandler)

    # Open browser automatically
    try:
        webbrowser.open(url)
    except Exception:
        pass

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Server stopped.")
        server.server_close()


if __name__ == "__main__":
    main()
