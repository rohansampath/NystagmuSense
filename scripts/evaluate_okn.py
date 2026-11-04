#!/usr/bin/env python3
"""Compare detect_okn.py fast phases with human-reviewed reset labels.

    python3 scripts/evaluate_okn.py [--labels-dir analysis/annotations] [--trials-dir trials]
                                    [--tolerance-ms 100] [--annotator AA]

Event-level scoring rules (documented so results are reproducible):

- Only trials whose review status is "complete" are scored. Unreviewed or
  in-progress trials are listed and never contribute to any number.
- References = labels "fast_phase". Predictions = start times of the
  detector's fast phases with DEFAULT parameters (the detector is not tuned here).
- Matching is one-to-one within ±tolerance: labels and predictions are taken
  in time order and each label is paired with the earliest unmatched
  prediction inside its window (maximum matching for equal 1-D windows).
- "uncertain" labels are excluded from the primary score: after matching the
  fast_phase labels, any remaining prediction within tolerance of an uncertain
  label is dropped (neither TP nor FP), and uncertain labels are never FN.
- "artifact" labels are not references; predictions on them stay false positives.
- precision = TP/(TP+FP), recall = TP/(TP+FN), F1 = 2TP/(2TP+FP+FN);
  each is "n/a" when its denominator is 0 (e.g. recall with no resets).
- Results are split by annotation_method. "manual" (independent, suggestions
  hidden) is the primary evaluation; "assisted" labels were made with
  velocity-peak suggestions visible and are reported separately.
- Fixation-mode trials also report false detections per reviewed trial.

Labels describe events visible in ARKit data, not physiological ground truth.
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import annotate_okn  # noqa: E402
import detect_okn  # noqa: E402

DEFAULT_TOLERANCE_S = 0.100
FIXATION_MODES = {"fixationMovingStripes", "fixationStillStripes"}


def match_events(references, predictions, tolerance):
    """One-to-one matching. Returns (pairs, unmatched_refs, unmatched_preds)."""
    refs, preds = sorted(references), sorted(predictions)
    used = [False] * len(preds)
    pairs, missed = [], []
    j = 0
    for r in refs:
        while j < len(preds) and (used[j] or preds[j] < r - tolerance):
            j += 1
        k = j
        while k < len(preds) and used[k]:
            k += 1
        if k < len(preds) and preds[k] <= r + tolerance:
            used[k] = True
            pairs.append((r, preds[k]))
        else:
            missed.append(r)
    return pairs, missed, [p for p, u in zip(preds, used) if not u]


def score_trial(events, predictions, tolerance=DEFAULT_TOLERANCE_S):
    """events = [(t, label)]; returns counts under the documented rules."""
    refs = [t for t, label in events if label == "fast_phase"]
    uncertain = [t for t, label in events if label == "uncertain"]
    pairs, missed, extra = match_events(refs, predictions, tolerance)
    still_extra = [p for p in extra if not any(abs(p - u) <= tolerance for u in uncertain)]
    return dict(tp=len(pairs), fn=len(missed), fp=len(still_extra),
                excluded_uncertain=len(extra) - len(still_extra),
                mean_abs_offset_s=(sum(abs(p - r) for r, p in pairs) / len(pairs)) if pairs else None)


def prf(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    denominator = 2 * tp + fp + fn
    f1 = 2 * tp / denominator if denominator else None
    return precision, recall, f1


def detector_predictions(csv_path):
    r = detect_okn.analyse(detect_okn.load_session(csv_path), detect_okn.Params())
    return [f["start"] for f in r["fast"]]


def find_recording(trial_id, trials_dir, review):
    candidates = [Path(trials_dir) / trial_id / f"{trial_id}.csv"]
    if review and review.get("source_csv"):
        candidates.append(Path(review["source_csv"]))
    return next((c for c in candidates if c.exists()), None)


def evaluate(labels_dir, trials_dir, tolerance=DEFAULT_TOLERANCE_S, annotator=None, predict=detector_predictions):
    labels_dir = Path(labels_dir)
    reviews = annotate_okn._read_rows(labels_dir / "reviews.csv")
    events = annotate_okn._read_rows(labels_dir / "events.csv")
    if annotator:
        reviews = [r for r in reviews if r["annotator_id"] == annotator]
    scored, skipped = [], []
    for rev in reviews:
        if rev["status"] != "complete":
            skipped.append((rev["trial_id"], rev["annotator_id"], rev["status"]))
            continue
        path = find_recording(rev["trial_id"], trials_dir, rev)
        if path is None:
            skipped.append((rev["trial_id"], rev["annotator_id"], "recording not found"))
            continue
        evs = [(float(e["event_time_s"]), e["label"]) for e in events
               if e["trial_id"] == rev["trial_id"] and e["annotator_id"] == rev["annotator_id"]]
        s = score_trial(evs, predict(path), tolerance)
        s.update(trial_id=rev["trial_id"], annotator=rev["annotator_id"],
                 method=rev["annotation_method"], mode=detect_okn.load_trial_mode(path))
        scored.append(s)
    return scored, skipped


def fmt(v):
    return "n/a" if v is None else f"{v:.2f}"


def report(scored, skipped, tolerance):
    print(f"tolerance ±{tolerance * 1000:.0f} ms; predictions = detect_okn fast-phase starts (default params)")
    print("labels are ARKit-visible events, not physiological ground truth\n")
    print(f"{'trial':40} {'annot':6} {'method':8} {'mode':22} TP FP FN unc  P     R     F1")
    for s in sorted(scored, key=lambda s: (s["method"], s["trial_id"])):
        p, r, f = prf(s["tp"], s["fp"], s["fn"])
        print(f"{s['trial_id'][:40]:40} {s['annotator'][:6]:6} {s['method']:8} {s['mode'][:22]:22} "
              f"{s['tp']:2d} {s['fp']:2d} {s['fn']:2d} {s['excluded_uncertain']:3d}  {fmt(p):5} {fmt(r):5} {fmt(f)}")
    for method in ("manual", "assisted"):
        group = [s for s in scored if s["method"] == method]
        if not group:
            print(f"\n{method}: no completely reviewed trials")
            continue
        tp, fp, fn = (sum(s[k] for s in group) for k in ("tp", "fp", "fn"))
        p, r, f = prf(tp, fp, fn)
        label = "PRIMARY (independent labels)" if method == "manual" else "assisted labels (suggestions shown; biased)"
        print(f"\n{method} — {label}: {len(group)} trials, TP {tp} FP {fp} FN {fn}: "
              f"precision {fmt(p)}, recall {fmt(r)}, F1 {fmt(f)}")
        fix = [s for s in group if s["mode"] in FIXATION_MODES]
        if fix:
            print(f"  fixation trials: {sum(s['fp'] for s in fix)} false detections in {len(fix)} reviewed trials "
                  f"({sum(s['fp'] for s in fix) / len(fix):.2f} per trial)")
    if skipped:
        print("\nnot scored (not completely reviewed or missing):")
        for trial, who, why in skipped:
            print(f"  {trial} [{who}]: {why}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--labels-dir", type=Path, default=annotate_okn.DEFAULT_LABELS_DIR)
    ap.add_argument("--trials-dir", type=Path, default=Path(__file__).resolve().parents[1] / "trials")
    ap.add_argument("--tolerance-ms", type=float, default=DEFAULT_TOLERANCE_S * 1000)
    ap.add_argument("--annotator")
    args = ap.parse_args(argv)
    if args.tolerance_ms <= 0:
        ap.error("--tolerance-ms must be positive")
    scored, skipped = evaluate(args.labels_dir, args.trials_dir, args.tolerance_ms / 1000, args.annotator)
    if not scored and not skipped:
        print(f"no reviews found in {args.labels_dir}")
        return 1
    report(scored, skipped, args.tolerance_ms / 1000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
