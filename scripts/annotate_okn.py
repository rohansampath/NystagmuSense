#!/usr/bin/env python3
"""Mark fast-phase / reset events in a NystagmuSense recording (matplotlib).

    python3 scripts/annotate_okn.py trials/<name>/<name>.csv --annotator AA
    python3 scripts/annotate_okn.py <csv> --annotator AA --assisted   # show suggestions

Labels describe events VISIBLE IN THE ARKIT SIGNAL. They are human-reviewed
reference labels for detector development, not physiological ground truth
from an independent eye tracker.

Two workflows:
  independent (default): detector-derived suggestions are never computed or
      shown. Use for trials reserved for evaluation. Saved as method "manual".
  assisted (--assisted): permissive velocity-peak suggestions can be toggled
      and accepted. Saved as method "assisted". Once a trial has an assisted
      session, its labels stay "assisted" for that annotator.

Raw recordings are only read. Labels go to two small CSVs in --labels-dir:
  events.csv   trial_id, event_time_s, label, annotator_id, annotation_method
  reviews.csv  trial_id, annotator_id, annotation_method, status, counts, ...
A trial with status "complete" and zero events was reviewed and has none; a
trial without a "complete" review row has not been (fully) annotated.

Controls (also printed when the window opens):
  left-click   add an event at the nearest sample (current label); snaps to a
               shown suggestion within 60 ms
  right-click  remove the nearest event (within 0.3 s)
  1 / 2 / 3    current label: fast_phase / uncertain / artifact
  z            undo the last add/remove
  t            show/hide suggestions (assisted mode only)
  y            accept all shown suggestions in the visible time range
  x            toggle "trial completely reviewed"
  s            save
Zoom and pan with the toolbar; clicks are ignored while a toolbar tool is active.
"""

import argparse
import csv
import datetime
import os
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import detect_okn  # noqa: E402

LABELS = ("fast_phase", "uncertain", "artifact")
METHODS = ("manual", "assisted")
EVENT_FIELDS = ["trial_id", "event_time_s", "label", "annotator_id", "annotation_method"]
REVIEW_FIELDS = ["trial_id", "annotator_id", "annotation_method", "status",
                 "n_fast_phase", "n_uncertain", "n_artifact", "updated_at_utc", "source_csv"]
DEFAULT_LABELS_DIR = Path(__file__).resolve().parents[1] / "analysis" / "annotations"
# Two events closer than this are treated as the same event (duplicate).
MIN_EVENT_SEPARATION_S = 0.05
# Suggestions: NOT a validated threshold; only helps the annotator find events.
SUGGEST_MIN_VELOCITY = 20.0      # deg/s
SUGGEST_MIN_SEPARATION_S = 0.15
SNAP_TO_SUGGESTION_S = 0.06
REMOVE_RADIUS_S = 0.3


def trial_id_for(csv_path):
    """Stable ID: the recording stem shared by the CSV, JSON and folder."""
    return Path(csv_path).stem


# ---------------------------------------------------------------- storage

def _read_rows(path):
    if not Path(path).exists():
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def _write_rows(path, fields, rows):
    """Atomic replace, so an interrupted save never leaves a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def dedupe(events):
    """Sorted (time, label) list with events closer than MIN_EVENT_SEPARATION_S
    collapsed (the first one wins)."""
    out = []
    for t, label in sorted(events):
        if out and t - out[-1][0] < MIN_EVENT_SEPARATION_S:
            continue
        out.append((t, label))
    return out


def load_annotations(labels_dir, trial_id, annotator):
    """(events, review) for one trial and annotator. events = [(t, label)];
    review = the reviews.csv row or None."""
    labels_dir = Path(labels_dir)
    events = [(float(r["event_time_s"]), r["label"])
              for r in _read_rows(labels_dir / "events.csv")
              if r["trial_id"] == trial_id and r["annotator_id"] == annotator]
    for _, label in events:
        if label not in LABELS:
            raise ValueError(f"unknown label {label!r} in events.csv")
    review = next((r for r in _read_rows(labels_dir / "reviews.csv")
                   if r["trial_id"] == trial_id and r["annotator_id"] == annotator), None)
    return dedupe(events), review


def save_annotations(labels_dir, trial_id, annotator, events, method, complete, source_csv=""):
    """Replace this trial+annotator's rows; every other row is kept as it is
    on disk at save time (re-read, not cached)."""
    if method not in METHODS:
        raise ValueError(f"annotation_method must be one of {METHODS}")
    labels_dir = Path(labels_dir)
    events = dedupe(events)
    for _, label in events:
        if label not in LABELS:
            raise ValueError(f"label must be one of {LABELS}")
    keep = [r for r in _read_rows(labels_dir / "events.csv")
            if not (r["trial_id"] == trial_id and r["annotator_id"] == annotator)]
    mine = [dict(trial_id=trial_id, event_time_s=f"{t:.6f}", label=label,
                 annotator_id=annotator, annotation_method=method) for t, label in events]
    _write_rows(labels_dir / "events.csv", EVENT_FIELDS,
                sorted(keep + mine, key=lambda r: (r["trial_id"], r["annotator_id"], float(r["event_time_s"]))))
    reviews = [r for r in _read_rows(labels_dir / "reviews.csv")
               if not (r["trial_id"] == trial_id and r["annotator_id"] == annotator)]
    counts = {label: sum(1 for _, l in events if l == label) for label in LABELS}
    reviews.append(dict(trial_id=trial_id, annotator_id=annotator, annotation_method=method,
                        status="complete" if complete else "in_progress",
                        n_fast_phase=counts["fast_phase"], n_uncertain=counts["uncertain"],
                        n_artifact=counts["artifact"],
                        updated_at_utc=datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        source_csv=str(source_csv)))
    _write_rows(labels_dir / "reviews.csv", REVIEW_FIELDS,
                sorted(reviews, key=lambda r: (r["trial_id"], r["annotator_id"])))


def add_event(events, t, label):
    """Adds unless it duplicates an existing event; returns whether it was added."""
    if any(abs(t - e) < MIN_EVENT_SEPARATION_S for e, _ in events):
        return False
    events.append((t, label))
    events.sort()
    return True


def nearest_event(events, t, radius):
    if not events:
        return None
    i = int(np.argmin([abs(e - t) for e, _ in events]))
    return i if abs(events[i][0] - t) <= radius else None


# ---------------------------------------------------------------- signal

def load_signal(csv_path, p=None):
    """Angle, velocity and validity exactly as detect_okn.py computes them."""
    p = p or detect_okn.Params()
    data = detect_okn.load_session(csv_path)
    t = data["t_s"]
    dt = float(np.median(np.diff(t)))
    angle = detect_okn.eye_angle(data)
    valid = detect_okn.valid_mask(t, angle, data, p)
    vel = detect_okn.sg_velocity(angle, valid, dt, p, t=t)
    return dict(t=t, angle=angle, valid=valid, velocity=vel, dt=dt)


def propose_candidates(t, velocity, valid, min_velocity=SUGGEST_MIN_VELOCITY,
                       min_separation_s=SUGGEST_MIN_SEPARATION_S):
    """Times of local |velocity| peaks above a permissive threshold, on valid
    samples only. Suggestions for a human, not detections."""
    from scipy.signal import find_peaks
    speed = np.where(valid & np.isfinite(velocity), np.abs(velocity), 0.0)
    dt = float(np.median(np.diff(t))) if len(t) > 1 else 1.0
    peaks, _ = find_peaks(speed, height=min_velocity, distance=max(1, int(round(min_separation_s / dt))))
    return [float(t[i]) for i in peaks]


# ---------------------------------------------------------------- GUI

class Annotator:
    """Matplotlib annotation window. Handlers are plain methods so they can be
    driven directly in tests."""

    COLORS = {"fast_phase": "tab:green", "uncertain": "tab:orange", "artifact": "tab:purple"}

    def __init__(self, csv_path, annotator, labels_dir, assisted=False, show=True):
        import matplotlib
        if not show:
            matplotlib.use("Agg")
        for key in ("keymap.save", "keymap.fullscreen", "keymap.xscale", "keymap.yscale"):
            matplotlib.rcParams[key] = []   # keys used below; toolbar buttons still work
        import matplotlib.pyplot as plt
        self.plt = plt
        self.csv_path = Path(csv_path)
        self.trial_id = trial_id_for(csv_path)
        self.annotator = annotator
        self.labels_dir = Path(labels_dir)
        self.assisted = assisted
        self.sig = load_signal(csv_path)
        self.mode = detect_okn.load_trial_mode(csv_path)
        self.events, review = load_annotations(labels_dir, self.trial_id, annotator)
        self.previous_method = review["annotation_method"] if review else None
        self.complete = bool(review and review["status"] == "complete")
        if self.previous_method == "assisted" and not assisted:
            print("note: this trial already has assisted labels from this annotator; "
                  "it stays 'assisted' even if suggestions are hidden now.")
        self.suggestions_shown = False
        self.suggestions = (propose_candidates(self.sig["t"], self.sig["velocity"], self.sig["valid"])
                            if assisted else [])
        self.label = "fast_phase"
        self.history = []
        self.dirty = False
        self._build()

    @property
    def method(self):
        used = self.suggestions_shown or self.previous_method == "assisted"
        return "assisted" if used else "manual"

    # ------------------------------------------------------------ drawing

    def _build(self):
        s = self.sig
        self.fig, (self.ax_a, self.ax_v) = self.plt.subplots(2, 1, sharex=True, figsize=(13, 7),
                                                              gridspec_kw={"height_ratios": [2, 1]})
        angle = np.where(s["valid"], s["angle"], np.nan)
        self.ax_a.plot(s["t"], angle, color="k", lw=0.9)
        self.ax_v.plot(s["t"], s["velocity"], color="0.3", lw=0.8)
        for ax in (self.ax_a, self.ax_v):
            for a, b in detect_okn.runs(~s["valid"]):
                ax.axvspan(s["t"][a], s["t"][min(b, len(s["t"]) - 1)], color="0.85", zorder=0)
            ax.grid(alpha=0.3)
        self.ax_a.set_ylabel("horizontal eye angle (deg)\ndetect_okn convention")
        self.ax_v.set_ylabel("SG velocity (deg/s)")
        self.ax_v.set_xlabel("time since session start (s)   ·   grey = invalid (untracked / blink-masked)")
        self.fig.text(0.01, 0.005, "click add · right-click remove · 1/2/3 fast/uncertain/artifact · "
                      "z undo · t suggestions · y accept shown · x reviewed · s save", fontsize=8)
        self.artists = []
        self.fig.canvas.mpl_connect("button_press_event", self.on_click)
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.fig.canvas.mpl_connect("close_event", self.on_close)
        self.redraw()

    def redraw(self):
        for a in self.artists:
            a.remove()
        self.artists = []
        for t, label in self.events:
            for ax in (self.ax_a, self.ax_v):
                self.artists.append(ax.axvline(t, color=self.COLORS[label], lw=1.5,
                                               ls="-" if label == "fast_phase" else "--"))
        if self.suggestions_shown:
            y = np.nanmax(np.abs(self.sig["velocity"])) if np.any(np.isfinite(self.sig["velocity"])) else 1
            self.artists.append(self.ax_v.scatter(self.suggestions, [y * 0.9] * len(self.suggestions),
                                                  marker="v", color="tab:blue", s=30, zorder=5))
        n = {label: sum(1 for _, l in self.events if l == label) for label in LABELS}
        self.ax_a.set_title(
            f"{self.trial_id}  ·  mode {self.mode}  ·  annotator {self.annotator}  ·  method {self.method}\n"
            f"next click: {self.label}  ·  fast {n['fast_phase']} / uncertain {n['uncertain']} / "
            f"artifact {n['artifact']}  ·  {'REVIEWED' if self.complete else 'not reviewed'}"
            f"{'  ·  unsaved' if self.dirty else ''}", fontsize=9)
        self.fig.canvas.draw_idle()

    # ------------------------------------------------------------ actions

    def nearest_sample_time(self, x):
        t = self.sig["t"]
        return float(t[int(np.argmin(np.abs(t - x)))])

    def add_at(self, x):
        t = self.nearest_sample_time(x)
        if self.suggestions_shown and self.suggestions:
            near = min(self.suggestions, key=lambda s: abs(s - t))
            if abs(near - t) <= SNAP_TO_SUGGESTION_S:
                t = near
        if add_event(self.events, t, self.label):
            self.history.append(("add", (t, self.label)))
            self.dirty = True
        else:
            print(f"ignored: an event already exists within {MIN_EVENT_SEPARATION_S * 1000:.0f} ms of {t:.3f} s")
        self.redraw()

    def remove_near(self, x):
        i = nearest_event(self.events, x, REMOVE_RADIUS_S)
        if i is not None:
            self.history.append(("remove", self.events.pop(i)))
            self.dirty = True
            self.redraw()

    def undo(self):
        if not self.history:
            return
        op, ev = self.history.pop()
        if op == "add":
            self.events.remove(ev)
        else:
            self.events.append(ev)
            self.events.sort()
        self.dirty = True
        self.redraw()

    def accept_visible_suggestions(self):
        if not self.suggestions_shown:
            return
        lo, hi = self.ax_a.get_xlim()
        for t in self.suggestions:
            if lo <= t <= hi and add_event(self.events, t, "fast_phase"):
                self.history.append(("add", (t, "fast_phase")))
                self.dirty = True
        self.redraw()

    def save(self):
        save_annotations(self.labels_dir, self.trial_id, self.annotator, self.events,
                         self.method, self.complete, source_csv=self.csv_path)
        self.previous_method = self.method
        self.dirty = False
        print(f"saved {len(self.events)} events ({self.method}, "
              f"{'complete' if self.complete else 'in progress'}) → {self.labels_dir}")
        self.redraw()

    # ------------------------------------------------------------ handlers

    def on_click(self, event):
        toolbar = getattr(self.fig.canvas, "toolbar", None)
        if event.inaxes not in (self.ax_a, self.ax_v) or event.xdata is None:
            return
        if toolbar is not None and getattr(toolbar, "mode", ""):
            return      # zoom/pan active
        if event.button == 1:
            self.add_at(event.xdata)
        elif event.button == 3:
            self.remove_near(event.xdata)

    def on_key(self, event):
        key = event.key
        if key in ("1", "2", "3"):
            self.label = LABELS[int(key) - 1]
            self.redraw()
        elif key == "z":
            self.undo()
        elif key == "t":
            if not self.assisted:
                print("suggestions are disabled in independent mode (start with --assisted)")
                return
            self.suggestions_shown = not self.suggestions_shown
            self.redraw()
        elif key == "y":
            self.accept_visible_suggestions()
        elif key == "x":
            self.complete = not self.complete
            self.dirty = True
            self.redraw()
        elif key == "s":
            self.save()

    def on_close(self, _event):
        if self.dirty:
            print("WARNING: window closed with unsaved changes (not saved).")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("csv", help="session CSV exported from the app")
    ap.add_argument("--annotator", required=True, help="your initials, e.g. AA")
    ap.add_argument("--assisted", action="store_true",
                    help="allow detector-derived suggestions (development labels only)")
    ap.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    args = ap.parse_args(argv)
    try:
        a = Annotator(args.csv, args.annotator, args.labels_dir, assisted=args.assisted)
    except (detect_okn.SessionError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(__doc__[__doc__.index("Controls"):])
    print(f"trial {a.trial_id}: {len(a.events)} existing events, "
          f"{'complete' if a.complete else 'not reviewed'}; workflow "
          f"{'assisted' if args.assisted else 'independent (suggestions hidden)'}")
    a.plt.show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
