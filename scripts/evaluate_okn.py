#!/usr/bin/env python3
"""Compare detect_okn.py fast phases with human-reviewed reset labels.

    python3 scripts/evaluate_okn.py [--labels-dir analysis/annotations] [--trials-dir trials]
                                    [--tolerance-ms 100] [--annotator AA]
    python3 scripts/evaluate_okn.py --manifest analysis/pilot_03/manifest.csv --split development \
        --labels-dir <labels> --artifacts exclude --output-csv results.csv

With --manifest only the manifest's primary trials of --split are scored, and
the held-out evaluation split needs --allow-evaluation (use it once, with the
detector frozen).

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
- "artifact" labels are never references. --artifacts false-positive (default,
  as before) keeps predictions on them as false positives; --artifacts exclude
  drops predictions within tolerance of an artifact label (neither TP nor FP),
  counted as excluded_artifact.
- Trials with no fast_phase label are scored too: every prediction is a false
  positive and recall is n/a. False positives are also given per 10 s of
  recording.
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
import math
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


def score_trial(events, predictions, tolerance=DEFAULT_TOLERANCE_S, artifacts="false-positive"):
    """events = [(t, label)]; returns counts under the documented rules."""
    refs = [t for t, label in events if label == "fast_phase"]
    uncertain = [t for t, label in events if label == "uncertain"]
    artifact = [t for t, label in events if label == "artifact"] if artifacts == "exclude" else []
    pairs, missed, extra = match_events(refs, predictions, tolerance)
    still_extra = [p for p in extra if not any(abs(p - u) <= tolerance for u in uncertain)]
    scored_extra = [p for p in still_extra if not any(abs(p - a) <= tolerance for a in artifact)]
    return dict(tp=len(pairs), fn=len(missed), fp=len(scored_extra),
                excluded_uncertain=len(extra) - len(still_extra),
                excluded_artifact=len(still_extra) - len(scored_extra),
                n_ref=len(refs), n_pred=len(predictions),
                mean_abs_offset_s=(sum(abs(p - r) for r, p in pairs) / len(pairs)) if pairs else None)


def prf(tp, fp, fn):
    precision = tp / (tp + fp) if tp + fp else None
    recall = tp / (tp + fn) if tp + fn else None
    denominator = 2 * tp + fp + fn
    f1 = 2 * tp / denominator if denominator else None
    return precision, recall, f1


def score_manifest_trial(events, predictions, condition, tolerance=DEFAULT_TOLERANCE_S, artifacts="false-positive"):
    """Pilot 03 still-stripe controls contribute false alarms, never true OKN resets."""
    if condition == "FIXSTILL":
        events = [(t, label) for t, label in events if label != "fast_phase"]
    return score_trial(events, predictions, tolerance, artifacts)


def detector_predictions(csv_path, method="sg", threshold=None):
    data = detect_okn.load_session(csv_path)
    threshold = (22 if method == "sg-direction" else 40) if threshold is None else threshold
    r = detect_okn.analyse(data, detect_okn.Params(fast_threshold=threshold),
                           method="sg" if method == "sg-direction" else method)
    fast = r["fast"]
    if method == "sg-direction":
        import okn_variants
        direction = detect_okn.stimulus_direction(data)
        displacement = data.get("stim_displacement_pt")
        if displacement is None or not all(math.isfinite(x) for x in displacement):
            raise ValueError("sg-direction requires finite recorded stimulus displacement")
        if direction == 0 and any(x != displacement[0] for x in displacement):
            raise ValueError("sg-direction cannot score a reversing stimulus")
        fast = okn_variants.direction_filter(fast, okn_variants.expected_reset_direction(direction))
    return [f["start"] for f in fast]


def find_recording(trial_id, trials_dir, review):
    candidates = [Path(trials_dir) / trial_id / f"{trial_id}.csv"]
    if review and review.get("source_csv"):
        candidates.append(Path(review["source_csv"]))
    return next((c for c in candidates if c.exists()), None)


def load_manifest(path, split):
    """trial_id → manifest row for the primary trials of one split."""
    rows = [r for r in annotate_okn._read_rows(path) if r.get("eligibility") == "primary" and r.get("split") == split]
    if not rows:
        raise ValueError(f"no primary {split} trials in {path}")
    return {r["trial_id"]: r for r in rows}


def development_reviews(labels_dir, include, annotator=None):
    """Select one independent annotator for development analysis.

    Never pool repeated reviews as additional recordings or mix their events.
    Infer the annotator only when the selection is unambiguous.
    """
    reviews = [r for r in annotate_okn._read_rows(Path(labels_dir) / "reviews.csv")
               if r["trial_id"] in include and (annotator is None or r["annotator_id"] == annotator)]
    ids = {r["annotator_id"] for r in reviews}
    if len(ids) > 1:
        raise ValueError("multiple annotators found; select one with --annotator")
    selected = {}
    for r in reviews:
        if r["trial_id"] in selected:
            raise ValueError(f"duplicate review for {r['trial_id']}")
        if r["annotation_method"] != "manual":
            raise ValueError(f"{r['trial_id']}: development benchmark requires independent manual labels")
        selected[r["trial_id"]] = r
    return selected


def review_events(events, review):
    """Events belonging to exactly the selected trial and annotator."""
    return [(float(e["event_time_s"]), e["label"]) for e in events
            if e["trial_id"] == review["trial_id"] and e["annotator_id"] == review["annotator_id"]]


def evaluate(labels_dir, trials_dir, tolerance=DEFAULT_TOLERANCE_S, annotator=None, predict=detector_predictions,
             include=None, artifacts="false-positive"):
    """Scores completely reviewed trials; `include` (trial_id → manifest row)
    restricts scoring to those trials and adds their participant/condition."""
    labels_dir = Path(labels_dir)
    reviews = annotate_okn._read_rows(labels_dir / "reviews.csv")
    events = annotate_okn._read_rows(labels_dir / "events.csv")
    if annotator:
        reviews = [r for r in reviews if r["annotator_id"] == annotator]
    scored, skipped = [], []
    if include is not None:
        reviews = [r for r in reviews if r["trial_id"] in include]
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
        t = detect_okn.load_session(path)["t_s"]
        row = (include or {}).get(rev["trial_id"], {})
        s = score_manifest_trial(evs, predict(path), row.get("condition"), tolerance, artifacts)
        s.update(trial_id=rev["trial_id"], annotator=rev["annotator_id"],
                 method=rev["annotation_method"], mode=detect_okn.load_trial_mode(path),
                 duration_s=float(t[-1] - t[0]), participant=row.get("participant", ""),
                 condition=row.get("condition", ""), direction=row.get("direction", ""), split=row.get("split", ""))
        scored.append(s)
    if include is not None:
        reviewed = {r["trial_id"] for r in reviews}
        skipped += [(tid, annotator or "-", "not opened") for tid in sorted(include) if tid not in reviewed]
    return scored, skipped


def summarize(scored):
    """Pooled counts and metrics for a group of scored trials."""
    tp, fp, fn = (sum(s[k] for s in scored) for k in ("tp", "fp", "fn"))
    p, r, f = prf(tp, fp, fn)
    seconds = sum(s["duration_s"] for s in scored)
    offsets = [s["mean_abs_offset_s"] * s["tp"] for s in scored if s["mean_abs_offset_s"] is not None]
    return dict(n_trials=len(scored), tp=tp, fp=fp, fn=fn, precision=p, recall=r, f1=f,
                fp_per_10s=10 * fp / seconds if seconds else None,
                mean_abs_offset_ms=1000 * sum(offsets) / tp if tp else None)


def group_rows(scored):
    """(group, summary) for all trials, each participant, each condition and each participant × condition."""
    keyed = [("all", lambda s: "all"), ("participant", lambda s: s["participant"]),
             ("condition", lambda s: s["condition"] or s["mode"]),
             ("participant x condition", lambda s: f"{s['participant']} {s['condition'] or s['mode']}")]
    out = []
    for kind, key in keyed:
        for value in sorted({key(s) for s in scored}):
            if kind != "all" and not value.strip():
                continue
            out.append((kind, value, summarize([s for s in scored if key(s) == value])))
    return out


TRIAL_FIELDS = ["trial_id", "participant", "condition", "direction", "split", "annotator", "method",
                "detector", "fast_threshold", "duration_s", "n_ref",
                "n_pred", "tp", "fp", "fn", "excluded_uncertain", "excluded_artifact", "mean_abs_offset_ms",
                "precision", "recall", "f1"]


def write_trial_csv(scored, path):
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRIAL_FIELDS, lineterminator="\n")
        w.writeheader()
        for s in sorted(scored, key=lambda s: s["trial_id"]):
            p, r, f1 = prf(s["tp"], s["fp"], s["fn"])
            w.writerow({**{k: s.get(k, "") for k in TRIAL_FIELDS}, "duration_s": f"{s['duration_s']:.3f}",
                        "mean_abs_offset_ms": "" if s["mean_abs_offset_s"] is None else f"{1000 * s['mean_abs_offset_s']:.1f}",
                        "precision": fmt(p), "recall": fmt(r), "f1": fmt(f1)})


def fmt(v):
    return "n/a" if v is None else f"{v:.2f}"


def report(scored, skipped, tolerance):
    print(f"tolerance ±{tolerance * 1000:.0f} ms; predictions = detector fast-phase starts")
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
    if any(s["participant"] for s in scored):
        print(f"\n{'group':34} trials  TP  FP  FN  P     R     F1    FP/10s")
        for kind, value, g in group_rows(scored):
            print(f"{kind + ': ' + value:34} {g['n_trials']:5d} {g['tp']:3d} {g['fp']:3d} {g['fn']:3d}  "
                  f"{fmt(g['precision']):5} {fmt(g['recall']):5} {fmt(g['f1']):5} {fmt(g['fp_per_10s'])}")
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
    ap.add_argument("--detector", choices=("sg", "hybrid", "both", "sg-direction"), default="sg",
                    help="detector to score on the same reviewed labels; default: sg")
    ap.add_argument("--fast-threshold", type=float,
                    help="deg/s; default 40 for sg/hybrid, frozen candidate 22 for sg-direction")
    ap.add_argument("--manifest", type=Path, help="e.g. analysis/pilot_03/manifest.csv; requires --split")
    ap.add_argument("--split", choices=("development", "evaluation"))
    ap.add_argument("--allow-evaluation", action="store_true",
                    help="required for --split evaluation: only once the detector is frozen")
    ap.add_argument("--artifacts", choices=("false-positive", "exclude"), default="false-positive",
                    help="predictions on artifact labels: count as FP (default) or leave unscored")
    ap.add_argument("--output-csv", type=Path, help="per-trial results (one file per detector)")
    args = ap.parse_args(argv)
    if not math.isfinite(args.tolerance_ms) or args.tolerance_ms <= 0:
        ap.error("--tolerance-ms must be finite and positive")
    if args.fast_threshold is not None and (not math.isfinite(args.fast_threshold) or args.fast_threshold <= 0):
        ap.error("--fast-threshold must be finite and positive")
    if bool(args.manifest) != bool(args.split):
        ap.error("--manifest and --split go together")
    if args.split == "evaluation" and not args.allow_evaluation:
        ap.error("the evaluation split is held out; add --allow-evaluation only once the detector is frozen")
    try:
        include = load_manifest(args.manifest, args.split) if args.manifest else None
    except ValueError as e:
        ap.error(str(e))
    if args.manifest is None:
        held = {tid for tid, row in annotate_okn.load_plan(annotate_okn.P03_MANIFEST).items()
                if row["split"] == "evaluation"}
        reviews = annotate_okn._read_rows(args.labels_dir / "reviews.csv")
        if any(r["trial_id"] in held and (args.annotator is None or r["annotator_id"] == args.annotator)
               for r in reviews):
            ap.error("Pilot 03 evaluation reviews found; select --manifest and --split explicitly")
    if args.split:
        print(f"split: {args.split} ({len(include)} primary trials in {args.manifest}); artifacts: {args.artifacts}")
    methods = ("sg", "hybrid") if args.detector == "both" else (args.detector,)
    if args.output_csv:
        sources = {args.labels_dir / "events.csv", args.labels_dir / "reviews.csv"}
        if args.manifest:
            sources.add(args.manifest)
        for review in annotate_okn._read_rows(args.labels_dir / "reviews.csv"):
            recording = find_recording(review["trial_id"], args.trials_dir, review)
            if recording:
                sources.update((recording, recording.with_suffix(".json")))
        outputs = [args.output_csv] if len(methods) == 1 else [
            args.output_csv.with_stem(f"{args.output_csv.stem}_{method}") for method in methods]
        if {p.resolve() for p in outputs} & {p.resolve() for p in sources}:
            ap.error("output would overwrite source labels, manifest or recording; choose another path")
    for method in methods:
        threshold = args.fast_threshold if args.fast_threshold is not None else (22 if method == "sg-direction" else 40)
        scored, skipped = evaluate(args.labels_dir, args.trials_dir, args.tolerance_ms / 1000,
                                   args.annotator, predict=lambda path: detector_predictions(path, method, threshold),
                                   include=include, artifacts=args.artifacts)
        if not scored and not skipped:
            print(f"no reviews found in {args.labels_dir}")
            return 1
        for row in scored:
            row.update(detector=method, fast_threshold=threshold)
        label = "baseline" if method == "sg" else "experimental"
        print(f"\nDetector: {method} ({label}), fast threshold {threshold:g} deg/s")
        report(scored, skipped, args.tolerance_ms / 1000)
        if args.output_csv:
            out = args.output_csv if len(methods) == 1 else args.output_csv.with_stem(f"{args.output_csv.stem}_{method}")
            write_trial_csv(scored, out)
            print(f"per-trial results: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
