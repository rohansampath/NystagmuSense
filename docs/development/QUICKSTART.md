# Quickstart: Mac Transfer and Annotation

A short checklist for getting a recording off the iPhone and into the
annotation tool. Run everything from the repository folder. The full details
are in the README sections "Automatic Wi-Fi Recording Transfer" and the
annotation section on `scripts/annotate_okn.py`.

## 1. Start the Mac receiver

```bash
# once: create the upload token (stays outside the repo, never commit it)
[ -s ~/.nystagmusense_token ] || openssl rand -hex 6 > ~/.nystagmusense_token

# every session: start the receiver on the local network
NS_UPLOAD_TOKEN=$(cat ~/.nystagmusense_token) python3 scripts/receive_recordings.py --lan
```

- `--lan` is required. Without it the receiver only listens on this Mac, and
  the app reports "connection refused. Start it with --lan."
- The receiver uses only the Python standard library, so any `python3` works.
- If macOS asks whether Python may accept incoming connections, choose **Allow**.
- Leave it running. Press Ctrl+C to stop it when the transfer is done.

Check that it is up (should print `{"status": "ok", ...}`):

```bash
curl -s -H "X-Upload-Token: $(cat ~/.nystagmusense_token)" \
  http://$(ipconfig getifaddr en0):8765/health
```

## 2. Connect the iPhone

In the app, open **Mac Transfer**:

| Field | Value |
|---|---|
| Server | `http://<Mac IP>:8765`, IP from `ipconfig getifaddr en0` |
| Upload token (second box) | output of `cat ~/.nystagmusense_token` |

- Phone and Mac must be on the same Wi-Fi.
- The first time, iOS asks to find devices on the local network. Allow it,
  then tap **Test Connection** again.
- The Mac's IP can change after reconnecting to Wi-Fi. If the test fails,
  check the IP again.

## 3. Confirm the recording arrived

The receiver prints one line per upload:

```
<phone IP> - - [...] saved .../trials/<recording name>
<phone IP> - - [...] "POST /upload HTTP/1.1" 201 -
```

`GET /health ... 200` lines are only connection tests, not recordings. To see
the newest trial:

```bash
ls -t trials | head -3
```

## 4. Open a trial in the annotation tool

```bash
python3 scripts/annotate_okn.py trials/<name>/<name>.csv --annotator <initials>
```

The annotation tool needs `numpy`, `matplotlib` and `scipy`. If it fails with
`ModuleNotFoundError: No module named 'numpy'`, the `python3` on your PATH does
not have them. Either install them:

```bash
python3 -m pip install -r scripts/requirements.txt
```

or run the tool with a Python that already has them, for example Anaconda:

```bash
/Applications/anaconda3/anaconda3/bin/python3 scripts/annotate_okn.py \
  trials/<name>/<name>.csv --annotator <initials>
```

To find which installed Python has them:

```bash
for p in $(which -a python3 | sort -u); do
  echo "$p: $($p -c 'import numpy, matplotlib, scipy; print("ok")' 2>&1 | tail -1)"
done
```

Controls: left-click adds an event, right-click removes the nearest one,
`1`/`2`/`3` set the label (fast_phase / uncertain / artifact), `z` undoes,
`x` marks the trial fully reviewed, `←`/`→` save and move between trials,
`H` toggles the help panel. Labels go to `events.csv` and `reviews.csv` in the
labels folder. Raw recordings are only read.
