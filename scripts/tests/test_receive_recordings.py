"""Unit tests for receive_recordings.py.

Run: python3 -m unittest discover scripts/tests

Each test runs a real server on an ephemeral 127.0.0.1 port with a temporary
trials directory. Recordings are SYNTHETIC fixtures, not experimental data.
"""

import http.client
import json
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import receive_recordings  # noqa: E402

TOKEN = "test-token-123"
STEM = "NS_20261103-101500_ABCD1234_okn"
CSV = "t_s,host_time_s,tracked\n0.000000,100.000000,1\n0.016667,100.016667,1\n"
META = json.dumps({"schemaVersion": 3, "sessionID": "ABCD1234-0000-0000-0000-000000000000"})


class QuietHandler(receive_recordings.Handler):
    def log_message(self, *args):
        pass


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.trials = Path(self.tmp.name)
        self.server = receive_recordings.make_server("127.0.0.1", 0, TOKEN, self.trials)
        self.port = self.server.server_address[1]
        self.server.RequestHandlerClass = QuietHandler
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.05},
                                       daemon=True)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()

    def request(self, method, path, body=None, token=TOKEN, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        h = dict(headers or {})
        if token is not None:
            h["X-Upload-Token"] = token
        conn.request(method, path, body=body, headers=h)
        resp = conn.getresponse()
        data = json.loads(resp.read() or b"{}")
        conn.close()
        return resp.status, data

    def upload(self, stem=STEM, csv=CSV, meta=META, token=TOKEN):
        body = json.dumps({"stem": stem, "csv": csv, "json": meta}).encode()
        return self.request("POST", "/upload", body, token=token)

    def saved_folders(self):
        return sorted(p.name for p in self.trials.iterdir())

    def test_health(self):
        self.assertEqual(self.request("GET", "/health"), (200, {"status": "ok"}))

    def test_health_rejects_wrong_token(self):
        status, _ = self.request("GET", "/health", token="wrong")
        self.assertEqual(status, 401)

    def test_successful_upload_saves_pair_unchanged(self):
        status, data = self.upload()
        self.assertEqual((status, data["status"]), (201, "saved"))
        folder = self.trials / STEM
        self.assertEqual((folder / f"{STEM}.csv").read_text(), CSV)
        self.assertEqual((folder / f"{STEM}.json").read_text(), META)
        self.assertEqual(self.saved_folders(), [STEM])  # no staging folder left

    def test_invalid_token_saves_nothing(self):
        for token in ("wrong", None):
            status, _ = self.upload(token=token)
            self.assertEqual(status, 401)
        self.assertEqual(self.saved_folders(), [])

    def test_invalid_filenames_rejected(self):
        for stem in ("../evil", "NS_20261103-101500_ABCD1234/../x", "/etc/passwd",
                     "trial_001", "NS_20261103-101500_ABCD1234_okn.csv", ""):
            status, data = self.upload(stem=stem)
            self.assertEqual(status, 400, stem)
            self.assertEqual(data["error"], "invalid recording name")
        self.assertEqual(self.saved_folders(), [])

    def test_identical_resend_is_accepted_without_rewrite(self):
        self.assertEqual(self.upload()[0], 201)
        status, data = self.upload()
        self.assertEqual((status, data["status"]), (200, "already_received"))
        self.assertEqual(self.saved_folders(), [STEM])

    def test_different_recording_with_same_name_is_refused(self):
        self.assertEqual(self.upload()[0], 201)
        status, _ = self.upload(csv=CSV + "0.033333,100.033333,0\n")
        self.assertEqual(status, 409)
        self.assertEqual((self.trials / STEM / f"{STEM}.csv").read_text(), CSV)

    def test_malformed_uploads_rejected(self):
        cases = [
            b"not json",
            b"[1, 2]",
            json.dumps({"stem": STEM, "csv": CSV}).encode(),                      # no json
            json.dumps({"stem": STEM, "csv": CSV, "json": "{bad"}).encode(),
            json.dumps({"stem": STEM, "csv": CSV, "json": "[]"}).encode(),
            json.dumps({"stem": STEM, "csv": "", "json": META}).encode(),
            json.dumps({"stem": STEM, "csv": "t_s,tracked\n0.0,1", "json": META}).encode(),  # truncated
            json.dumps({"stem": STEM, "csv": "a,b\n1,2\n", "json": META}).encode(),
        ]
        for body in cases:
            status, _ = self.request("POST", "/upload", body)
            self.assertEqual(status, 400, body)
        self.assertEqual(self.saved_folders(), [])

    def test_oversized_upload_rejected_before_reading(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        conn.putrequest("POST", "/upload")
        conn.putheader("X-Upload-Token", TOKEN)
        conn.putheader("Content-Length", str(receive_recordings.MAX_BODY_BYTES + 1))
        conn.endheaders()
        self.assertEqual(conn.getresponse().status, 413)
        conn.close()

    def test_body_cut_off_mid_upload_saves_nothing(self):
        body = json.dumps({"stem": STEM, "csv": CSV, "json": META}).encode()
        with socket.create_connection(("127.0.0.1", self.port), timeout=5) as s:
            s.sendall((f"POST /upload HTTP/1.1\r\nHost: x\r\nX-Upload-Token: {TOKEN}\r\n"
                       f"Content-Length: {len(body)}\r\n\r\n").encode() + body[:20])
            s.shutdown(socket.SHUT_WR)
            reply = s.recv(4096)
        self.assertIn(b" 400 ", reply.split(b"\r\n")[0])
        self.assertEqual(self.saved_folders(), [])

    def test_unknown_path(self):
        self.assertEqual(self.request("GET", "/trials")[0], 404)


class ParseTests(unittest.TestCase):
    def test_legacy_stem_without_mode_is_valid(self):
        body = json.dumps({"stem": "NS_20261024-101500_ABCD1234", "csv": CSV, "json": META})
        self.assertEqual(receive_recordings.parse_recording(body)[0], "NS_20261024-101500_ABCD1234")


if __name__ == "__main__":
    unittest.main()
