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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import receive_recordings  # noqa: E402

TOKEN = "test-token-123"
STEM = "NS_20261103-101500_ABCD1234_okn"
CSV = "t_s,host_time_s,tracked\n0.000000,100.000000,1\n0.016667,100.016667,1\n"
META = json.dumps({"schemaVersion": 3, "sessionID": "ABCD1234-0000-0000-0000-000000000000"})


class QuietHandler(receive_recordings.Handler):
    def log_message(self, *args):
        pass


class ServerTestCase(unittest.TestCase):
    """Starts a receiver on an ephemeral port with a temporary trials directory."""
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



class ReceiverTests(ServerTestCase):
    def test_health(self):
        self.assertEqual(self.request("GET", "/health"),
                         (200, {"status": "ok", "name_contract": receive_recordings.NAME_CONTRACT}))

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


class DescriptiveNameTests(ServerTestCase):
    """Schema-4 names: {experiment}_T###_{MODE}_{DIRECTION}_{UTC}."""
    NAME = "P02_T001_OKN_RIGHT_20261104_143022"

    def test_descriptive_name_saved_as_matching_pair(self):
        self.assertEqual(self.upload(stem=self.NAME)[0], 201)
        self.assertEqual(sorted(p.name for p in (self.trials / self.NAME).iterdir()),
                         [self.NAME + ".csv", self.NAME + ".json"])

    def test_all_modes_and_directions_accepted(self):
        for stem in ("P02_T002_FIXMOVE_LEFT_20261104_143105", "P02_T003_FIXSTILL_NONE_20261104_143145",
                     "PILOT-3_T1000_OKN_LEFT_20261104_143145"):
            self.assertEqual(self.upload(stem=stem)[0], 201, stem)

    def test_duplicate_descriptive_upload_never_overwrites(self):
        self.assertEqual(self.upload(stem=self.NAME)[0], 201)
        self.assertEqual(self.upload(stem=self.NAME), (200, {"status": "already_received", "stem": self.NAME}))
        status, _ = self.upload(stem=self.NAME, csv=CSV + "0.033333,100.033333,1\n")
        self.assertEqual(status, 409)
        self.assertEqual((self.trials / self.NAME / f"{self.NAME}.csv").read_text(), CSV)

    def test_malformed_descriptive_names_rejected(self):
        for stem in ("p02_T001_OKN_RIGHT_20261104_143022",      # lower case
                     "P02_T01_OKN_RIGHT_20261104_143022",       # 2-digit trial
                     "P02_T001_OKN_UP_20261104_143022",
                     "P02_T001_okn_RIGHT_20261104_143022",
                     "P_02_T001_OKN_RIGHT_20261104_143022",
                     "P02_T001_OKN_RIGHT_20261104_143022/../x",
                     "P02_T001_OKN_RIGHT_20261104"):
            self.assertEqual(self.upload(stem=stem)[0], 400, stem)
        self.assertEqual(self.saved_folders(), [])


FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "recording_names.json").read_text())


class SharedNameContractTests(ServerTestCase):
    """Names from tests/fixtures/recording_names.json, the same file the Swift
    tests check RecordingName against, so app and receiver can't drift apart."""

    def test_contract_versions_match(self):
        self.assertEqual(FIXTURE["contract_version"], receive_recordings.NAME_CONTRACT)

    def test_every_app_generated_name_is_accepted_in_sequence(self):
        for case in FIXTURE["generated"]:          # sequential trials, every mode/direction/test type
            status, data = self.upload(stem=case["name"])
            self.assertEqual((status, data.get("status")), (201, "saved"), case["name"])
        for case in FIXTURE["generated"]:
            folder = self.trials / case["name"]
            self.assertEqual(sorted(p.name for p in folder.iterdir()),
                             [case["name"] + ".csv", case["name"] + ".json"])

    def test_older_names_still_accepted(self):
        for stem in FIXTURE["legacy_valid"]:
            self.assertEqual(self.upload(stem=stem)[0], 201, stem)

    def test_invalid_and_malicious_names_rejected_with_code(self):
        for stem in FIXTURE["invalid"]:
            status, data = self.upload(stem=stem)
            self.assertEqual((status, data["code"]), (400, "invalid_name"), stem)
        self.assertEqual(self.saved_folders(), [])

    def test_retry_is_idempotent_and_conflict_never_overwrites(self):
        name = FIXTURE["generated"][1]["name"]      # DIR_T002_OKN_LEFT_...
        self.assertEqual(self.upload(stem=name)[0], 201)
        self.assertEqual(self.upload(stem=name), (200, {"status": "already_received", "stem": name}))
        status, data = self.upload(stem=name, meta=json.dumps({"schemaVersion": 5, "other": True}))
        self.assertEqual((status, data["code"]), (409, "conflict"))
        self.assertEqual((self.trials / name / f"{name}.json").read_text(), META)
        self.assertEqual(self.saved_folders(), [name])

    def test_error_codes_for_token_and_malformed_body(self):
        status, data = self.upload(token="wrong")
        self.assertEqual((status, data["code"]), (401, "unauthorized"))
        status, data = self.request("POST", "/upload", b"not json")
        self.assertEqual((status, data["code"]), (400, "malformed"))


class Pilot03Tests(ServerTestCase):
    """Participant-tagged names (P03-P01_...) and the metadata that must agree with them."""

    def meta(self, name, **overrides):
        fields = dict(schemaVersion=6, experimentID="P03", participantID=name[4:7], recordingName=name,
                      directionCode=name.split("_")[3])
        fields.update(overrides)
        return json.dumps(fields)

    def p03_cases(self):
        return [c for c in FIXTURE["generated"] if c["testType"] == "P03"]

    def test_all_five_pilot_03_combinations_arrive_as_matching_pairs(self):
        cases = self.p03_cases()
        self.assertEqual(len(cases), 5)
        for case in cases:
            name = case["name"]
            self.assertEqual(self.upload(stem=name, meta=self.meta(name))[0], 201, name)
            self.assertEqual(sorted(p.name for p in (self.trials / name).iterdir()), [name + ".csv", name + ".json"])
            self.assertEqual(json.loads((self.trials / name / f"{name}.json").read_text())["participantID"],
                             case["participant"])

    def test_retry_of_a_pilot_03_trial_is_idempotent(self):
        name = self.p03_cases()[0]["name"]
        self.assertEqual(self.upload(stem=name, meta=self.meta(name))[0], 201)
        self.assertEqual(self.upload(stem=name, meta=self.meta(name)), (200, {"status": "already_received", "stem": name}))
        status, data = self.upload(stem=name, meta=self.meta(name, trialNumber=99))
        self.assertEqual((status, data["code"]), (409, "conflict"))

    def test_metadata_that_disagrees_with_the_name_is_refused(self):
        name = self.p03_cases()[1]["name"]              # P03-P02_T042_OKN_LEFT_...
        for meta in (self.meta(name, recordingName=name.replace("_LEFT_", "_RIGHT_")),
                     self.meta(name, participantID="P01"),
                     self.meta(name, experimentID="P02")):
            status, data = self.upload(stem=name, meta=meta)
            self.assertEqual((status, data["code"]), (400, "mismatched_metadata"), meta)
        self.assertEqual(self.saved_folders(), [])

    def test_received_pilot_03_recording_is_read_by_plotting_and_detection(self):
        import contextlib
        import io
        import matplotlib
        matplotlib.use("Agg")
        import detect_okn
        import plot_gaze
        from test_detect_okn import okn_angle, synthetic_csv
        name = self.p03_cases()[0]["name"]              # P03-P01_T041_OKN_RIGHT_...
        meta = self.meta(name, stimulus={"trialMode": "okn", "direction": "rightward"})
        self.assertEqual(self.upload(stem=name, csv=synthetic_csv(okn_angle), meta=meta)[0], 201)
        csv_path = self.trials / name / f"{name}.csv"
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(plot_gaze.main([str(csv_path), "--out", str(self.trials / "plot.png")]), 0)
        self.assertEqual(detect_okn.load_trial_mode(csv_path), "okn")
        result = detect_okn.analyse(detect_okn.load_session(csv_path), detect_okn.Params())
        self.assertGreater(len(result["fast"]), 0)

    def test_schema_5_sidecars_with_their_own_name_are_still_accepted(self):
        name = "DIR_T005_OKN_RIGHT_20261104_074541"
        meta = json.dumps({"schemaVersion": 5, "experimentID": "DIR", "recordingName": name})
        self.assertEqual(self.upload(stem=name, meta=meta)[0], 201)


class ParseTests(unittest.TestCase):
    def test_legacy_stem_without_mode_is_valid(self):
        body = json.dumps({"stem": "NS_20261024-101500_ABCD1234", "csv": CSV, "json": META})
        self.assertEqual(receive_recordings.parse_recording(body)[0], "NS_20261024-101500_ABCD1234")


if __name__ == "__main__":
    unittest.main()
