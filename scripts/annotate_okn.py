#!/usr/bin/env python3
"""Mark fast-phase / reset events in NystagmuSense recordings (matplotlib).

    python3 scripts/annotate_okn.py --split evaluation --annotator AA
    python3 scripts/annotate_okn.py --split development --annotator AA --assisted
    python3 scripts/annotate_okn.py trials/<name>/<name>.csv [more.csv ...] --annotator AA

One window walks through a queue of recordings: a split from
analysis/annotations/plan.csv (in plan order), or the CSVs given on the command
line (in the order given). It opens at the first trial this annotator has not
marked reviewed; --start picks another. Moving to another trial (← / →) saves
first and stays put if the save fails.

Labels describe events VISIBLE IN THE ARKIT SIGNAL. They are human-reviewed
reference labels for detector development, not physiological ground truth
from an independent eye tracker.

Two workflows:
  independent (default): detector-derived suggestions are never computed or
      shown. Saved as method "manual".
  assisted (--assisted): permissive velocity-peak suggestions can be toggled
      and accepted. Saved as method "assisted" once shown. Once a trial has an
      assisted session, its labels stay "assisted" for that annotator.
Trials in the plan's evaluation split never get suggestions, even with
--assisted, whatever queue they are opened from.

Raw recordings are only read. Labels go to two small CSVs in --labels-dir:
  events.csv   trial_id, event_time_s, label, annotator_id, annotation_method
  reviews.csv  trial_id, annotator_id, annotation_method, status, counts, ...
A trial with status "complete" and zero events was reviewed and has none; a
trial without a "complete" review row has not been (fully) annotated.

Controls (also shown in the window's help panel, H hides it):
  ← / →            save, then previous / next trial (no wrap-around)
  left-click       add an event at the nearest sample (current label); snaps to
                   a shown suggestion within 60 ms
  right-click      remove the nearest event (within 0.3 s)
  1 / 2 / 3        current label: fast_phase / uncertain / artifact
  z                undo the last add/remove
  x                toggle "trial completely reviewed"
  s                save (closing the window also saves)
  + / -            zoom in / out around the cursor
  shift+← / →      scroll back / forward in time
  r                reset zoom to the whole recording
  h                show / hide the help panel
  t / y            show/hide suggestions, accept shown ones in view (assisted,
                   non-evaluation trials only)
The toolbar's zoom and pan tools also work; clicks don't label while one is active.
"""

import argparse
import csv
import datetime
import json
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
DEFAULT_TRIALS_DIR = Path(__file__).resolve().parents[1] / "trials"
# Which trials are held out for evaluation; the order is the annotation order.
PLAN_CSV = DEFAULT_LABELS_DIR / "plan.csv"
SPLITS = ("evaluation", "development")
CONDITIONS = {"okn": "OKN (watch stripes)", "fixationMovingStripes": "fixation dot + moving stripes",
              "fixationStillStripes": "fixation dot + still stripes"}
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


# ---------------------------------------------------------------- queue

def load_plan(path=PLAN_CSV):
    """trial_id → plan row (split, order, pilot_id, note). Empty if no plan."""
    rows = _read_rows(path)
    for r in rows:
        if r["split"] not in SPLITS:
            raise ValueError(f"unknown split {r['split']!r} in {path}")
    return {r["trial_id"]: r for r in rows}


def split_queue(split, trials_dir, plan):
    """CSV paths of one split in plan order. Every recording must exist."""
    rows = sorted((r for r in plan.values() if r["split"] == split), key=lambda r: int(r["order"]))
    if not rows:
        raise ValueError(f"no trials are assigned to the {split} split in {PLAN_CSV.name}")
    paths = [Path(trials_dir) / r["trial_id"] / f"{r['trial_id']}.csv" for r in rows]
    missing = [str(p) for p in paths if not p.exists()]
    if missing:
        raise ValueError("missing recordings (check --trials-dir):\n  " + "\n  ".join(missing))
    return paths


def review_statuses(labels_dir, annotator):
    """trial_id → saved review status for one annotator."""
    return {r["trial_id"]: r["status"] for r in _read_rows(Path(labels_dir) / "reviews.csv")
            if r["annotator_id"] == annotator}


def first_unreviewed(queue, statuses):
    """Index of the first trial not marked complete; 0 if all are."""
    return next((i for i, p in enumerate(queue)
                 if statuses.get(trial_id_for(p)) != "complete"), 0)


def resolve_start(queue, plan, value):
    """--start accepts a 1-based queue number, a Pilot ID (A3) or a trial_id."""
    ids = [trial_id_for(p) for p in queue]
    if value.isdigit() and 1 <= int(value) <= len(queue):
        return int(value) - 1
    for i, trial_id in enumerate(ids):
        if value in (trial_id, (plan.get(trial_id) or {}).get("pilot_id")):
            return i
    raise ValueError(f"--start {value!r} is not in this queue")


def stimulus_direction(csv_path):
    """Stripe direction from the JSON sidecar ('rightward' / 'leftward'), or None."""
    try:
        meta = json.loads(Path(csv_path).with_suffix(".json").read_text())
    except (OSError, json.JSONDecodeError):
        return None
    return ((meta or {}).get("stimulus") or {}).get("direction")


# ---------------------------------------------------------------- GUI

PLOT_LEFT, PLOT_RIGHT, HELP_LEFT = 0.07, 0.975, 0.775
ANGLE_BOTTOM, ANGLE_HEIGHT, VEL_BOTTOM, VEL_HEIGHT = 0.42, 0.42, 0.16, 0.22
SPLIT_TAGS = {"evaluation": ("HELD-OUT EVALUATION · suggestions disabled", "tab:red"),
              "development": ("DEVELOPMENT", "tab:blue"),
              None: ("not in the plan", "0.4")}
MESSAGE_COLORS = {"info": "0.25", "ok": "tab:green", "warn": "tab:orange", "error": "tab:red"}


class Annotator:
    """Matplotlib annotation window over a queue of recordings. Handlers are
    plain methods so they can be driven directly in tests."""

    COLORS = {"fast_phase": "tab:green", "uncertain": "tab:orange", "artifact": "tab:purple"}
    STYLES = {"fast_phase": "-", "uncertain": "--", "artifact": ":"}
    NAMES = {"fast_phase": "FAST PHASE", "uncertain": "UNCERTAIN", "artifact": "ARTIFACT"}

    def __init__(self, trials, annotator, labels_dir, assisted=False, show=True, start=None, plan=None):
        import matplotlib
        if not show:
            matplotlib.use("Agg")
        # Keys used below (arrows were back/forward, h/r home); toolbar buttons still work.
        for key in ("keymap.save", "keymap.fullscreen", "keymap.xscale", "keymap.yscale",
                    "keymap.back", "keymap.forward", "keymap.home"):
            matplotlib.rcParams[key] = []
        import matplotlib.pyplot as plt
        self.plt = plt
        self.queue = [Path(trials)] if isinstance(trials, (str, Path)) else [Path(p) for p in trials]
        if not self.queue:
            raise ValueError("no recordings to annotate")
        self.annotator = annotator
        self.labels_dir = Path(labels_dir)
        self.assisted = assisted
        self.plan = load_plan() if plan is None else plan
        self.statuses = review_statuses(labels_dir, annotator)
        self.index = None
        self.show_help = True
        self.message, self.message_kind = "", "info"
        self._build()
        if not self.load(first_unreviewed(self.queue, self.statuses) if start is None else start):
            raise ValueError(self.message)

    @property
    def method(self):
        used = self.suggestions_ever_shown or self.previous_method == "assisted"
        return "assisted" if used else "manual"

    @property
    def suggestions_allowed(self):
        return self.assisted and self.split != "evaluation"

    # ------------------------------------------------------------ trials

    def load(self, i):
        """Open queue entry i. On a read error the current trial stays open."""
        path = self.queue[i]
        trial_id = trial_id_for(path)
        try:
            sig = load_signal(path)
            mode = detect_okn.load_trial_mode(path)
            events, review = load_annotations(self.labels_dir, trial_id, self.annotator)
        except (detect_okn.SessionError, ValueError, OSError) as e:
            self.notify(f"could not open {trial_id}: {e}", "error")
            return False
        plan_row = self.plan.get(trial_id) or {}
        self.index, self.csv_path, self.trial_id, self.sig, self.mode = i, path, trial_id, sig, mode
        self.split, self.pilot_id = plan_row.get("split"), plan_row.get("pilot_id")
        self.direction = stimulus_direction(path)
        self.events = events
        self.previous_method = review["annotation_method"] if review else None
        self.complete = bool(review and review["status"] == "complete")
        if self.previous_method == "assisted" and not self.suggestions_allowed:
            print(f"note: {trial_id} already has assisted labels from this annotator; "
                  "it stays 'assisted' even with suggestions hidden.")
        self.suggestions_shown = False
        self.suggestions_ever_shown = False
        # Held-out trials never compute suggestions at all.
        self.suggestions = (propose_candidates(sig["t"], sig["velocity"], sig["valid"])
                            if self.suggestions_allowed else [])
        self.label = "fast_phase"
        self.history = []
        self.dirty = False
        self._plot_signal()
        self.notify(f"opened {self.pilot_id or trial_id}: {len(events)} saved labels, "
                    f"{'reviewed' if self.complete else 'not reviewed'}")
        return True

    def go(self, step):
        """Save if needed, then open the neighbouring trial. Never wraps."""
        if self.dirty and not self.save():
            return False
        j = self.index + step
        if not 0 <= j < len(self.queue):
            n, done = len(self.queue), self.reviewed_count()
            where = "first" if j < 0 else "last"
            self.notify(f"this is the {where} trial in the queue ({done} / {n} reviewed); "
                        f"nothing {'before' if j < 0 else 'after'} it", "warn")
            return False
        return self.load(j)

    def reviewed_count(self):
        return sum(self.statuses.get(trial_id_for(p)) == "complete" for p in self.queue)

    # ------------------------------------------------------------ drawing

    def _build(self):
        from matplotlib.text import Annotation
        from matplotlib.widgets import Button
        self.fig = self.plt.figure(figsize=(14, 8.5))
        self.ax_a = self.fig.add_axes([PLOT_LEFT, ANGLE_BOTTOM, 0.1, ANGLE_HEIGHT])
        self.ax_v = self.fig.add_axes([PLOT_LEFT, VEL_BOTTOM, 0.1, VEL_HEIGHT], sharex=self.ax_a)
        self.ax_help = self.fig.add_axes([HELP_LEFT, VEL_BOTTOM, PLOT_RIGHT - HELP_LEFT, 0.69])
        self.ax_help.set_axis_off()
        self.header = self.fig.text(PLOT_LEFT, 0.975, "", fontsize=13, weight="bold", va="top")
        self.subheader = self.fig.text(PLOT_LEFT, 0.940, "", fontsize=11, weight="bold", va="top")
        self.details = self.fig.text(PLOT_LEFT, 0.908, "", fontsize=10, color="0.35", va="top")
        self.badge = self.fig.text(PLOT_LEFT, 0.876, "", fontsize=11, weight="bold", va="top")
        # The action message follows the review badge, however long that is.
        self.status = self.fig.add_artist(Annotation("", xy=(1, 1), xycoords=self.badge, xytext=(14, 0),
                                                     textcoords="offset points", fontsize=11, va="top"))
        self.label_badge = self.fig.text(PLOT_RIGHT, 0.975, "", fontsize=12, weight="bold", ha="right",
                                         va="top", color="white")
        self.buttons = {}
        specs = [("prev", "← Previous", lambda _e: self.go(-1)), ("next", "Next →", lambda _e: self.go(1)),
                 ("save", "Save", lambda _e: self.save()), ("review", "Mark reviewed", lambda _e: self.toggle_reviewed()),
                 ("zoom", "Reset zoom", lambda _e: self.reset_zoom()), ("help", "Help", lambda _e: self.toggle_help())]
        for k, (name, text, callback) in enumerate(specs):
            b = Button(self.fig.add_axes([PLOT_LEFT + k * 0.125, 0.025, 0.115, 0.055]), text)
            b.label.set_fontsize(11)
            b.on_clicked(callback)
            self.buttons[name] = b
        self.artists = []
        self._layout()
        self.fig.canvas.mpl_connect("button_press_event", self.on_click)
        self.fig.canvas.mpl_connect("key_press_event", self.on_key)
        self.fig.canvas.mpl_connect("close_event", self.on_close)

    def _layout(self):
        right = HELP_LEFT - 0.03 if self.show_help else PLOT_RIGHT
        self.ax_a.set_position([PLOT_LEFT, ANGLE_BOTTOM, right - PLOT_LEFT, ANGLE_HEIGHT])
        self.ax_v.set_position([PLOT_LEFT, VEL_BOTTOM, right - PLOT_LEFT, VEL_HEIGHT])
        self.ax_help.set_visible(self.show_help)

    def _plot_signal(self):
        s = self.sig
        for ax in (self.ax_a, self.ax_v):
            ax.cla()
        self.artists = []
        self.ax_a.plot(s["t"], np.where(s["valid"], s["angle"], np.nan), color="k", lw=1.0)
        self.ax_v.plot(s["t"], s["velocity"], color="0.3", lw=0.8)
        for ax in (self.ax_a, self.ax_v):
            for a, b in detect_okn.runs(~s["valid"]):
                ax.axvspan(s["t"][a], s["t"][min(b, len(s["t"]) - 1)], color="0.88", zorder=0)
            ax.grid(alpha=0.3)
            ax.tick_params(labelsize=10)
        self.ax_a.tick_params(labelbottom=False)
        self.ax_a.set_ylabel("horizontal eye angle (deg)\n+ = subject's left (Pilot 01)", fontsize=10)
        self.ax_v.set_ylabel("SG velocity (deg/s)", fontsize=10)
        self.ax_v.set_xlabel("time since session start (s)   ·   grey = invalid (untracked / blink-masked)",
                             fontsize=10)
        self.full_xlim = (float(s["t"][0]), float(s["t"][-1]))
        self.ax_a.set_xlim(*self.full_xlim)
        self.full_ylim = {ax: ax.get_ylim() for ax in (self.ax_a, self.ax_v)}
        toolbar = getattr(self.fig.canvas, "toolbar", None)
        if toolbar is not None and hasattr(toolbar, "update"):
            toolbar.update()        # forget the previous trial's zoom history
        self.redraw()

    def label_guide(self):
        """What a reset looks like in this trial, in the plotted convention
        (+ = subject's left, from the Pilot 01 look-left/right trials)."""
        if self.mode == "fixationStillStripes":
            return "stripes are STILL", ["no OKN expected", "saccades are not fast phases", "(use 2 if unsure)"]
        if self.direction == "rightward":
            return "stripes move RIGHT →", ["slow phase: gradual drift DOWN ↓", "reset: sharp jump UP ↑  → press 1",
                                            "sharp jump DOWN = not a reset"]
        if self.direction == "leftward":
            return "stripes move ← LEFT", ["slow phase: gradual drift UP ↑", "reset: sharp jump DOWN ↓  → press 1",
                                           "sharp jump UP = not a reset"]
        return "stripe direction unknown", ["reset = sharp jump against", "the slow drift"]

    def _draw_help(self):
        ax = self.ax_help
        ax.clear()
        ax.set_axis_off()
        title, lines = self.label_guide()
        ax.text(0, 1.0, "What to label", fontsize=11, weight="bold", va="top", transform=ax.transAxes)
        ax.text(0.02, 0.952, title + "\n" + "\n".join(lines), fontsize=10, va="top", linespacing=1.45,
                transform=ax.transAxes, bbox=dict(boxstyle="round,pad=0.4", facecolor="#fff6d5", edgecolor="#d9b84a"))
        if self.suggestions_allowed:
            suggestion_rows = [("T", "show / hide suggestions"), ("Y", "accept shown ones in view")]
        else:
            why = "held-out trial" if self.split == "evaluation" else "start with --assisted"
            suggestion_rows = [("", f"off ({why})")]
        sections = [
            ("Trials", [("← / →", "save + previous / next")]),
            ("Labelling", [("1", ("fast phase", "fast_phase")), ("2", ("uncertain", "uncertain")),
                           ("3", ("artifact", "artifact")), ("click", "add label"),
                           ("right-click", "remove nearest"), ("Z", "undo")]),
            ("Saving", [("S", "save (closing also saves)"), ("X", "mark reviewed / not")]),
            ("View", [("+ / −", "zoom at cursor"), ("shift+← / →", "scroll in time"),
                      ("R", "reset zoom"), ("H", "hide this panel")]),
            ("Suggestions", suggestion_rows),
        ]
        y = 0.952 - 0.032 * (len(lines) + 1) - 0.05
        for title, rows in sections:
            ax.text(0, y, title, fontsize=11, weight="bold", va="top", transform=ax.transAxes)
            y -= 0.044
            for key, desc in rows:
                ax.text(0.02, y, key, fontsize=10, family="monospace", weight="bold", va="top",
                        transform=ax.transAxes)
                if isinstance(desc, tuple):
                    text, label = desc
                    ax.plot([0.40, 0.52], [y - 0.012] * 2, color=self.COLORS[label], ls=self.STYLES[label],
                            lw=2.2, transform=ax.transAxes, clip_on=False)
                    ax.text(0.56, y, text, fontsize=10, va="top", transform=ax.transAxes)
                else:
                    ax.text(0.40, y, desc, fontsize=10, va="top", transform=ax.transAxes)
                y -= 0.036
            y -= 0.014

    def redraw(self):
        for a in self.artists:
            a.remove()
        self.artists = []
        for t, label in self.events:
            for ax in (self.ax_a, self.ax_v):
                self.artists.append(ax.axvline(t, color=self.COLORS[label], lw=1.8, ls=self.STYLES[label],
                                               zorder=3))
        if self.suggestions_shown:
            y = np.nanmax(np.abs(self.sig["velocity"])) if np.any(np.isfinite(self.sig["velocity"])) else 1
            self.artists.append(self.ax_v.scatter(self.suggestions, [y * 0.9] * len(self.suggestions),
                                                  marker="v", color="tab:blue", s=30, zorder=5))
        n_total, done = len(self.queue), self.reviewed_count()
        self.header.set_text(f"Trial {self.index + 1} / {n_total}   |   Reviewed {done} / {n_total}   |   "
                             f"Remaining {n_total - done}")
        tag, color = SPLIT_TAGS[self.split]
        condition = CONDITIONS.get(self.mode, self.mode)
        if self.mode == "fixationStillStripes":
            direction = " · stripes still"
        else:
            direction = f" · stripes {self.direction}" if self.direction else ""
        pilot = f"{self.pilot_id} · " if self.pilot_id else ""
        self.subheader.set_text(f"{tag}   ·   {pilot}{condition}{direction}")
        self.subheader.set_color(color)
        self.details.set_text(f"{self.trial_id}   ·   annotator {self.annotator}   ·   method {self.method}")
        n = {label: sum(1 for _, l in self.events if l == label) for label in LABELS}
        if not self.complete:
            review, review_color = "NOT REVIEWED", "tab:orange"
        elif n["fast_phase"] == 0:
            review, review_color = "REVIEWED · no fast phases", "tab:green"
        else:
            review, review_color = f"REVIEWED · {n['fast_phase']} fast phases", "tab:green"
        save_state = "UNSAVED" if self.dirty else "saved"
        self.badge.set_text(f"{review}   ·   fast {n['fast_phase']} / uncertain {n['uncertain']} / "
                            f"artifact {n['artifact']}   ·   {save_state}")
        self.badge.set_color(review_color)
        self.status.set_text(self.message)
        self.status.set_color(MESSAGE_COLORS[self.message_kind])
        self.label_badge.set_text(f" label: {self.NAMES[self.label]}  [{LABELS.index(self.label) + 1}] ")
        self.label_badge.set_bbox(dict(facecolor=self.COLORS[self.label], edgecolor="none", pad=4))
        self.buttons["review"].label.set_text("Mark not reviewed" if self.complete else "Mark reviewed")
        if self.show_help:
            self._draw_help()
        self.fig.canvas.draw_idle()

    def notify(self, message, kind="info"):
        self.message, self.message_kind = message, kind
        if self.index is not None:
            self.redraw()

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
            self.notify(f"added {self.label} at {t:.3f} s   (Z undoes)")
        else:
            self.notify(f"ignored: a label already exists within {MIN_EVENT_SEPARATION_S * 1000:.0f} ms "
                        f"of {t:.3f} s", "warn")

    def remove_near(self, x):
        i = nearest_event(self.events, x, REMOVE_RADIUS_S)
        if i is None:
            self.notify(f"no label within {REMOVE_RADIUS_S} s to remove", "warn")
            return
        t, label = self.events.pop(i)
        self.history.append(("remove", (t, label)))
        self.dirty = True
        self.notify(f"removed {label} at {t:.3f} s   (Z undoes)")

    def undo(self):
        if not self.history:
            self.notify("nothing to undo", "warn")
            return
        op, ev = self.history.pop()
        if op == "add":
            self.events.remove(ev)
        else:
            self.events.append(ev)
            self.events.sort()
        self.dirty = True
        self.notify(f"undid {op} of {ev[1]} at {ev[0]:.3f} s")

    def toggle_suggestions(self):
        if not self.suggestions_allowed:
            why = ("held-out evaluation trial" if self.split == "evaluation"
                   else "independent mode (start with --assisted)")
            self.notify(f"suggestions are disabled: {why}", "warn")
            return
        self.suggestions_shown = not self.suggestions_shown
        if self.suggestions_shown:
            self.suggestions_ever_shown = True
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

    def toggle_reviewed(self):
        self.complete = not self.complete
        self.dirty = True
        self.notify("marked reviewed (S or ← / → saves)" if self.complete else "marked NOT reviewed")

    def _write(self):
        """Write this trial's labels; returns an error message or None."""
        try:
            save_annotations(self.labels_dir, self.trial_id, self.annotator, self.events,
                             self.method, self.complete, source_csv=self.csv_path)
        except (OSError, ValueError, csv.Error) as e:
            return str(e) or type(e).__name__
        self.previous_method = self.method
        self.statuses[self.trial_id] = "complete" if self.complete else "in_progress"
        self.dirty = False
        return None

    def save(self):
        error = self._write()
        if error:
            print(f"SAVE FAILED for {self.trial_id}: {error}", file=sys.stderr)
            self.notify(f"SAVE FAILED: {error} — edits kept; trial navigation blocked until a save works",
                        "error")
            return False
        status = "complete" if self.complete else "in progress"
        print(f"saved {self.trial_id}: {len(self.events)} events ({self.method}, {status}) → {self.labels_dir}")
        self.notify(f"saved ✓  {len(self.events)} labels, {status}", "ok")
        return True

    # ------------------------------------------------------------ view

    def _set_xlim(self, lo, hi):
        t0, t1 = self.full_xlim
        width = min(hi - lo, t1 - t0)
        lo = min(max(lo, t0), t1 - width)
        self.ax_a.set_xlim(lo, lo + width)
        self.fig.canvas.draw_idle()

    def zoom(self, factor, x=None):
        lo, hi = self.ax_a.get_xlim()
        c = x if x is not None and lo <= x <= hi else (lo + hi) / 2
        width = max((hi - lo) * factor, 0.1)
        self._set_xlim(c - (c - lo) * width / (hi - lo), c + (hi - c) * width / (hi - lo))

    def scroll(self, direction):
        lo, hi = self.ax_a.get_xlim()
        shift = direction * (hi - lo) / 2
        self._set_xlim(lo + shift, hi + shift)

    def reset_zoom(self):
        self.ax_a.set_xlim(*self.full_xlim)
        for ax, ylim in self.full_ylim.items():
            ax.set_ylim(*ylim)
        self.fig.canvas.draw_idle()

    def toggle_help(self):
        self.show_help = not self.show_help
        self._layout()
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
            self.toggle_suggestions()
        elif key == "y":
            if self.suggestions_allowed:
                self.accept_visible_suggestions()
            else:
                self.toggle_suggestions()       # explains why it's disabled
        elif key == "x":
            self.toggle_reviewed()
        elif key == "s":
            self.save()
        elif key in ("right", "left"):
            self.go(1 if key == "right" else -1)
        elif key in ("shift+right", "shift+left"):
            self.scroll(1 if key == "shift+right" else -1)
        elif key in ("+", "="):
            self.zoom(0.5, getattr(event, "xdata", None))
        elif key == "-":
            self.zoom(2.0, getattr(event, "xdata", None))
        elif key == "r":
            self.reset_zoom()
        elif key == "h":
            self.toggle_help()

    def on_close(self, _event):
        if not self.dirty:
            return
        error = self._write()
        if error:
            print(f"WARNING: window closed but saving {self.trial_id} FAILED ({error}); "
                  "its unsaved changes are lost.", file=sys.stderr)
        else:
            print(f"saved {self.trial_id} on close: {len(self.events)} events "
                  f"({'complete' if self.complete else 'in progress'})")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("csv", nargs="*", help="session CSV(s) exported from the app, annotated in the order given")
    ap.add_argument("--split", choices=SPLITS,
                    help=f"annotate every recording of this split in analysis/annotations/{PLAN_CSV.name}")
    ap.add_argument("--annotator", required=True, help="your initials, e.g. AA")
    ap.add_argument("--assisted", action="store_true",
                    help="allow detector-derived suggestions (development labels only; "
                         "never for evaluation trials)")
    ap.add_argument("--start", help="open this trial first: queue number, Pilot ID (e.g. A3) or trial_id "
                                    "(default: first trial you haven't marked reviewed)")
    ap.add_argument("--trials-dir", type=Path, default=DEFAULT_TRIALS_DIR,
                    help="folder holding <trial_id>/<trial_id>.csv (used with --split)")
    ap.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS_DIR)
    args = ap.parse_args(argv)
    if bool(args.csv) == bool(args.split):
        ap.error("give either CSV path(s) or --split, not both")
    try:
        plan = load_plan()
        queue = split_queue(args.split, args.trials_dir, plan) if args.split else [Path(p) for p in args.csv]
        start = resolve_start(queue, plan, args.start) if args.start else None
        if args.split == "evaluation" and args.assisted:
            print("note: --assisted has no effect here; evaluation trials never show suggestions.")
        a = Annotator(queue, args.annotator, args.labels_dir, assisted=args.assisted, start=start, plan=plan)
    except (detect_okn.SessionError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(__doc__[__doc__.index("Controls"):])
    print(f"queue: {len(queue)} trials ({args.split or 'from the command line'}), "
          f"{a.reviewed_count()} already reviewed by {args.annotator}; opening trial {a.index + 1}")
    a.plt.show()
    return 0


if __name__ == "__main__":
    sys.exit(main())
