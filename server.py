"""Loopback-only web app: public examples and ephemeral local audio analysis."""

from __future__ import annotations

import argparse
import base64
import binascii
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
import os
from pathlib import Path
import re
import subprocess
import sys
from tempfile import TemporaryDirectory
import threading
from urllib.parse import unquote, urlsplit

from speechcontrast.alignment import normalize_transcript

ROOT = Path(__file__).resolve().parent
MAX_UPLOAD = 8_000_000
MAX_BODY = 22_000_000
ALLOWED_EXTENSIONS = {"wav", "mp3", "flac", "ogg", "webm"}
ANALYSIS_LOCK = threading.Lock()


def decode_upload(upload: dict) -> tuple[str, bytes]:
    if not isinstance(upload, dict) or not isinstance(upload.get("data"), str):
        raise ValueError("Choose two audio files.")
    extension = str(upload.get("extension", "")).lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValueError("Supported formats: WAV, MP3, FLAC, OGG and WebM.")
    if len(upload["data"]) > (MAX_UPLOAD + 2) // 3 * 4:
        raise ValueError("Each audio file must be at most 8 MB.")
    try:
        body = base64.b64decode(upload["data"], validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("Audio encoding is invalid.") from None
    if not body or len(body) > MAX_UPLOAD:
        raise ValueError("Each audio file must contain between 1 byte and 8 MB.")
    return extension, body


def no_json_constant(value):
    raise ValueError("Non-finite JSON values are not accepted.")


def load_manifest():
    path = ROOT / "data/manifest.json"
    return json.loads(path.read_text())


class Handler(BaseHTTPRequestHandler):
    server_version = "SpeechContrast"
    protocol_version = "HTTP/1.1"

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        # Never log request bodies, transcript text or local filenames.
        return

    def headers_common(self, media, length, status=200, extra=None):
        self.send_response(status)
        self.send_header("Content-Type", media)
        self.send_header("Content-Length", str(length))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; media-src 'self' blob:; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()

    def reply(self, payload, status=200):
        body = json.dumps(payload, allow_nan=False).encode()
        self.headers_common("application/json; charset=utf-8", len(body), status)
        self.wfile.write(body)

    def same_origin(self):
        port = self.server.server_address[1]
        valid_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        host = self.headers.get("Host", "")
        if host not in valid_hosts:
            return False
        origin = self.headers.get("Origin")
        return origin is None or origin in {"http://" + item for item in valid_hosts}

    def file(self, path, media):
        body = path.read_bytes()
        range_header = self.headers.get("Range")
        if range_header and media.startswith("audio/"):
            match = re.fullmatch(r"bytes=(\d*)-(\d*)", range_header)
            if not match or not any(match.groups()):
                self.reply({"error": "Unsupported byte range."}, 416)
                return
            start, end = match.groups()
            if not start:
                first, last = max(0, len(body) - int(end)), len(body) - 1
            else:
                first, last = int(start), min(int(end) if end else len(body) - 1, len(body) - 1)
            if not 0 <= first <= last < len(body):
                self.reply({"error": "Byte range outside audio."}, 416)
                return
            chunk = body[first:last + 1]
            self.headers_common(media, len(chunk), 206, {"Content-Range": f"bytes {first}-{last}/{len(body)}", "Accept-Ranges": "bytes"})
            self.wfile.write(chunk)
        else:
            self.headers_common(media, len(body), extra={"Accept-Ranges": "bytes"} if media.startswith("audio/") else None)
            self.wfile.write(body)

    def do_GET(self):
        if not self.same_origin():
            self.reply({"error": "Loopback host required."}, 403)
            return
        path = unquote(urlsplit(self.path).path)
        try:
            if path == "/api/manifest":
                self.reply(load_manifest())
                return
            match = re.fullmatch(r"/api/(analysis|audio)/([a-z0-9._-]+)(?:/(reference|delivery))?", path)
            if match:
                kind, example_id, side = match.groups()
                manifest = load_manifest()
                example = next((e for e in manifest["examples"] if e["id"] == example_id), None)
                if not example:
                    self.reply({"error": "Example not found."}, 404)
                    return
                if kind == "analysis" and not side:
                    if example["abstained"]:
                        self.reply({"abstained": True, "score": None, "regions": [], "reason": example["abstention_reason"], "transcript": example["transcript"]})
                    else:
                        self.file(ROOT / example["analysis"], "application/json; charset=utf-8")
                    return
                if kind == "audio" and side:
                    reference = next(r for r in manifest["references"] if r["id"] == example["source_id"])
                    relative = reference["audio"] if side == "reference" else example["audio"]
                    self.file(ROOT / relative, "audio/wav")
                    return
                self.reply({"error": "Unknown example route."}, 404)
                return
            if path.startswith("/api/"):
                self.reply({"error": "Endpoint not found."}, 404)
                return
            base = ROOT / "web/dist"
            requested = (base / path.lstrip("/")).resolve()
            if not requested.is_relative_to(base.resolve()):
                self.reply({"error": "Invalid path."}, 404)
                return
            if not requested.is_file():
                if Path(path).suffix:
                    self.reply({"error": "File not found."}, 404)
                    return
                requested = base / "index.html"
            if not requested.is_file():
                self.reply({"error": "Build the frontend with pnpm build before starting."}, 503)
                return
            self.file(requested, mimetypes.guess_type(requested.name)[0] or "application/octet-stream")
        except (OSError, ValueError, KeyError):
            self.reply({"error": "This local artifact is unavailable or invalid."}, 503)

    def do_POST(self):
        if not self.same_origin():
            self.reply({"error": "Same-origin loopback request required."}, 403)
            return
        if urlsplit(self.path).path != "/api/compare":
            self.reply({"error": "Endpoint not found."}, 404)
            return
        if self.headers.get("Transfer-Encoding"):
            self.reply({"error": "Chunked uploads are not accepted."}, 400)
            self.close_connection = True
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 1 <= length <= MAX_BODY:
            self.reply({"error": "Request exceeds the two-file upload limit."}, 413)
            self.close_connection = True
            return
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            self.reply({"error": "JSON request required."}, 415)
            self.close_connection = True
            return
        if not ANALYSIS_LOCK.acquire(blocking=False):
            self.reply({"error": "Another local comparison is running. Try again after it finishes."}, 503)
            self.close_connection = True
            return
        try:
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise ValueError("Upload was interrupted.")
            request = json.loads(raw, parse_constant=no_json_constant)
            if not isinstance(request, dict):
                raise ValueError("Comparison request must be an object.")
            transcript = request.get("transcript")
            normalize_transcript(transcript)
            uploads = [decode_upload(request.get(side)) for side in ("reference", "delivery")]
            with TemporaryDirectory(prefix="speechcontrast-") as folder:
                temporary = Path(folder)
                files = []
                for i, (extension, body) in enumerate(uploads):
                    path = temporary / f"audio-{i}.{extension}"
                    path.write_bytes(body)
                    path.chmod(0o600)
                    files.append(path)
                input_path, output_path = temporary / "request.json", temporary / "result.json"
                input_path.write_text(json.dumps({"reference": str(files[0]), "delivery": str(files[1]), "transcript": transcript}))
                input_path.chmod(0o600)
                env = {"PATH": os.environ.get("PATH", "/opt/homebrew/bin:/usr/bin:/bin"), "LANG": "en_US.UTF-8",
                       "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1", "OMP_NUM_THREADS": "2", "TOKENIZERS_PARALLELISM": "false"}
                process = subprocess.run([sys.executable, "-m", "speechcontrast.analyze", str(input_path), str(output_path)],
                                         cwd=ROOT, env=env, capture_output=True, timeout=90)
                if output_path.is_file():
                    result = json.loads(output_path.read_text())
                    status = 422 if "error" in result else 200
                else:
                    result = {"error": "Local analysis could not finish. Verify the pinned model files and audio formats."}
                    status = 503
            # Delete PCM, transcript and child output before returning a result.
            self.reply(result, status)
        except ValueError as error:
            self.reply({"error": str(error)[:200]}, 400)
        except (UnicodeError, OSError):
            self.reply({"error": "Invalid audio or transcript upload."}, 400)
        except subprocess.TimeoutExpired:
            self.reply({"error": "Local analysis exceeded 90 seconds. Try a shorter excerpt."}, 504)
        finally:
            ANALYSIS_LOCK.release()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=5276)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("Choose a non-privileged port.")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Speech Contrast Lab: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
