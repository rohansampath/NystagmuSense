#!/usr/bin/env python3
"""Receive NystagmuSense recordings from the iPhone over local Wi-Fi.

Each upload is one recording: the app's CSV and JSON sidecar, saved unchanged
as trials/<stem>/<stem>.csv and trials/<stem>/<stem>.json (the same folder
layout the app uses on the phone). Standard library only.

    openssl rand -hex 6 > ~/.nystagmusense_token
    NS_UPLOAD_TOKEN=$(cat ~/.nystagmusense_token) python3 scripts/receive_recordings.py --lan

Without --lan the server only listens on this Mac (127.0.0.1).

Endpoints (both require the X-Upload-Token header):
    GET  /health   -> 200 {"status": "ok"}
    POST /upload   body {"stem": "...", "csv": "...", "json": "..."}
                   -> 201 saved, 200 identical recording already received,
                      400 malformed, 401 bad token, 409 different recording
                      with the same name exists, 413 too large

This is a local research tool, not a production web service.
"""

import argparse
import hmac
import http.server
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

TOKEN_ENV = "NS_UPLOAD_TOKEN"
MIN_TOKEN_LENGTH = 8
DEFAULT_PORT = 8765
DEFAULT_TRIALS_DIR = Path(__file__).resolve().parents[1] / "trials"
# A 10 s recording is ~100 KB; this leaves plenty of room for longer sessions.
MAX_BODY_BYTES = 10 * 1024 * 1024
# RecordingName (schema 4+): {experiment}_T{###}_{MODE}_{DIRECTION}_{UTC yyyyMMdd_HHmmss},
# e.g. P02_T001_OKN_RIGHT_20261104_143022; or the legacy SessionRecorder.fileStem
# NS_<yyyyMMdd-HHmmss>_<8 hex>[_<mode>].
STEM_RE = re.compile(
    r"[A-Z0-9-]{1,16}_T\d{3,}_(?:OKN|FIXMOVE|FIXSTILL)_(?:RIGHT|LEFT|NONE)_\d{8}_\d{6}"
    r"|NS_\d{8}-\d{6}_[0-9A-Fa-f]{8}(?:_[a-z]+)?")


class UploadError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def parse_recording(body):
    """Validates an upload body; returns (stem, csv_text, json_text)."""
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise UploadError(400, "body is not valid JSON")
    if not isinstance(payload, dict):
        raise UploadError(400, "body must be a JSON object")
    stem, csv_text, json_text = (payload.get(k) for k in ("stem", "csv", "json"))
    if not all(isinstance(v, str) for v in (stem, csv_text, json_text)):
        raise UploadError(400, "expected string fields: stem, csv, json")
    if not STEM_RE.fullmatch(stem):
        raise UploadError(400, "invalid recording name")
    # The app ends every CSV with a newline, so a missing one means truncation.
    if not csv_text.startswith("t_s,") or not csv_text.endswith("\n") or csv_text.count("\n") < 2:
        raise UploadError(400, "csv is empty, incomplete or not a NystagmuSense export")
    try:
        meta = json.loads(json_text)
    except json.JSONDecodeError:
        raise UploadError(400, "metadata is not valid JSON")
    if not isinstance(meta, dict):
        raise UploadError(400, "metadata must be a JSON object")
    return stem, csv_text, json_text


def save_recording(trials_dir, stem, csv_text, json_text):
    """Writes both files, or neither. Returns (created, folder).

    Re-sending an identical recording (e.g. a retry after a lost response) is
    accepted without rewriting; a different recording under the same name is
    refused so nothing on the Mac is ever overwritten.
    """
    final = trials_dir / stem
    files = {f"{stem}.csv": csv_text, f"{stem}.json": json_text}
    if final.exists():
        same = all((final / name).is_file()
                   and (final / name).read_text(encoding="utf-8") == text
                   for name, text in files.items())
        if same:
            return False, final
        raise UploadError(409, "a different recording with this name already exists")

    # Stage in a hidden folder, then rename: both files appear together.
    staging = Path(tempfile.mkdtemp(prefix=".incoming-", dir=trials_dir))
    try:
        for name, text in files.items():
            with open(staging / name, "w", encoding="utf-8", newline="") as f:
                f.write(text)
                f.flush()
                os.fsync(f.fileno())
        os.rename(staging, final)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return True, final


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "NystagmuSenseReceiver/1"
    # Seconds to wait on a stalled client, so one bad upload can't hang the server.
    timeout = 30

    def do_GET(self):
        if self.path != "/health":
            return self.reply(404, {"error": "not found"})
        if not self.authorized():
            return self.reply(401, {"error": "invalid upload token"})
        self.reply(200, {"status": "ok"})

    def do_POST(self):
        if self.path != "/upload":
            return self.reply(404, {"error": "not found"})
        if not self.authorized():
            return self.reply(401, {"error": "invalid upload token"})
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.reply(411, {"error": "Content-Length required"})
        if length <= 0:
            return self.reply(400, {"error": "empty upload"})
        if length > MAX_BODY_BYTES:
            return self.reply(413, {"error": f"upload larger than {MAX_BODY_BYTES} bytes"})
        try:
            body = self.rfile.read(length)
        except OSError:
            self.close_connection = True
            return
        if len(body) != length:
            return self.reply(400, {"error": "upload was cut off"})

        try:
            stem, csv_text, json_text = parse_recording(body)
            created, folder = save_recording(self.server.trials_dir, stem, csv_text, json_text)
        except UploadError as e:
            return self.reply(e.status, {"error": e.message})
        except OSError as e:
            self.log_message("could not write recording: %s", e)
            return self.reply(500, {"error": "could not write files on the Mac"})

        if created:
            self.log_message("saved %s", folder)
            self.reply(201, {"status": "saved", "stem": stem})
        else:
            self.log_message("already have %s (identical resend)", folder)
            self.reply(200, {"status": "already_received", "stem": stem})

    def authorized(self):
        sent = self.headers.get("X-Upload-Token", "")
        return hmac.compare_digest(sent.encode(), self.server.token.encode())

    def reply(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        if status >= 400:
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(body)


def make_server(host, port, token, trials_dir):
    """Builds (but doesn't start) the server. Request logs never include the token."""
    server = http.server.HTTPServer((host, port), Handler)
    server.token = token
    server.trials_dir = Path(trials_dir)
    return server


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--lan", action="store_true",
                        help="listen on the local network so the iPhone can connect "
                             "(default: this Mac only)")
    parser.add_argument("--trials-dir", type=Path, default=DEFAULT_TRIALS_DIR)
    args = parser.parse_args(argv)

    token = os.environ.get(TOKEN_ENV, "")
    if len(token) < MIN_TOKEN_LENGTH:
        sys.exit(f"Set {TOKEN_ENV} to a random token of at least {MIN_TOKEN_LENGTH} characters:\n"
                 f"  openssl rand -hex 6 > ~/.nystagmusense_token\n"
                 f"  export {TOKEN_ENV}=$(cat ~/.nystagmusense_token)")

    args.trials_dir.mkdir(parents=True, exist_ok=True)
    host = "0.0.0.0" if args.lan else "127.0.0.1"
    server = make_server(host, args.port, token, args.trials_dir)
    print(f"Saving recordings to {args.trials_dir.resolve()}")
    if args.lan:
        print(f"Listening on the local network, port {args.port}. On the iPhone, enter")
        print(f"  http://<this Mac's IP>:{args.port}   (find the IP with: ipconfig getifaddr en0)")
    else:
        print(f"Listening on 127.0.0.1:{args.port} only (add --lan for the iPhone)")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
