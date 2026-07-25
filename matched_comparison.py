#!/usr/bin/env python3
"""
Modality-matched Standard vs Pressure comparison (rebuttal §1.2, AC issue 2).

The AC: the published 54-86% Standard-to-Pressure reduction "shows sensitivity to
the overall evaluation protocol but cannot be attributed specifically to pressure
framing. A modality-matched comparison is needed, or the causal claim should be
moderated."

Auditing the artifact found FOUR differences between the two benchmarks, not the
three the AC listed:

  1. modality   - Standard pools text + tools + sandbox; Pressure is text only
  2. scope      - Standard pools general + domain; Pressure is general only
  3. framing    - the pressure conditions themselves (the factor of interest)
  4. INSTRUMENT - Standard is scored by test_all_scenarios.py (one judge call per
                  probe, mean over risk stages); Pressure is scored by the
                  evaluation/ package (~47 judge calls collapsed into a weighted
                  formula, stored as metrics.primary_score). Pressure records
                  carry no `aggregate_scores` field at all.

This script therefore reports three nested contrasts so the reader can see what
each control removes:

  A. UNMATCHED            as published: everything differs at once
  B. MODALITY+SCOPE       Standard restricted to text + general-context;
                          instruments still differ
  C. FULLY MATCHED        as B, but the Pressure side re-scored with the Standard
                          instrument (requires rescore_pressure_standard_instrument.py)

Only C supports a causal statement about framing. A and B are reported so the
size of each confound is visible.

Usage:
    python matched_comparison.py                     # A and B
    python matched_comparison.py --pressure-rescored # adds C where available
    python matched_comparison.py --metric max_risk_score
"""

import argparse
import json
import os
import statistics as st
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent
CATS = ("update_resistance", "oversight_avoidance", "centralisation")
MODELS = ("sonnet_45", "gemini_25_pro", "gpt_41")
MODEL_LABEL = {"sonnet_45": "Claude Sonnet 4.5", "gemini_25_pro": "Gemini 2.5 Pro",
               "gpt_41": "GPT-4.1"}
RESCORED_DIR = BASE / "pressure_rescored_standard"

try:
    from scipy import stats as _stats
    SCIPY = True
except ImportError:
    SCIPY = False


def _score(agg, metric):
    """Explicit None check so a legitimate 0.0 survives (see variance_analysis.py)."""
    if not isinstance(agg, dict):
        return None
    v = agg.get(metric)
    return float(v) if v is not None else None


def load_standard(metric):
    """Standard benchmark -> {(model, cat, scope, modality): [scores]}."""
    out = defaultdict(list)
    for p in (BASE / "test" / "results").rglob("*.json"):
        f = str(p)
        if "partial" in p.name:
            continue
        parts = f.replace(os.sep, "/").split("/")
        try:
            cat = next(x for x in parts if x in CATS)
            model = next(x for x in parts if x in MODELS)
            scope = next(x for x in parts if x in ("complete_all", "domain"))
            modality = next(x for x in parts if x in ("text", "tools", "sandbox"))
        except StopIteration:
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, list):
            continue
        for x in d:
            if not isinstance(x, dict) or x.get("status") != "completed":
                continue
            s = _score(x.get("aggregate_scores"), metric)
            if s is not None:
                out[(model, cat, scope, modality)].append(s)
    return out


def load_pressure_published():
    """
    Pressure benchmark as published -> {(model, cat): [primary_score]}.

    These come from the evaluation/ package's weighted formula, NOT from
    aggregate_scores, which pressure records do not have. Not on the same scale
    as the Standard scores - that is the point of contrast C.
    """
    out = defaultdict(list)
    for p in (BASE / "phase1_results").rglob("*_results.json"):
        if "partial" in p.name:
            continue
        parts = str(p).replace(os.sep, "/").split("/")
        try:
            model = next(x for x in parts if x in MODELS)
            cat = next(x for x in parts if x in CATS)
        except StopIteration:
            continue
        try:
            recs = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(recs, list):
            continue
        for rec in recs:
            res = rec.get("result")
            if isinstance(res, list):
                res = res[0] if res else None
            if not isinstance(res, dict):
                continue
            le = (res.get("metadata") or {}).get("lock_in_evaluation") or {}
            v = (le.get("metrics") or {}).get("primary_score")
            if v is not None:
                out[(model, cat)].append(float(v))
    return out


def load_pressure_rescored(metric):
    """Pressure re-scored with the Standard instrument -> {(model, cat): [scores]}."""
    out = defaultdict(list)
    if not RESCORED_DIR.exists():
        return out
    for p in RESCORED_DIR.rglob("*_rescored.json"):
        model = p.parent.name
        cat = p.name.replace("_rescored.json", "")
        if model not in MODELS or cat not in CATS:
            continue
        try:
            recs = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for r in recs:
            s = _score(r.get("aggregate_scores"), metric)
            if s is not None:
                out[(model, cat)].append(s)
    return out


def pct(a, b):
    return (b - a) / a * 100.0 if a else float("nan")


def block(title, note, std_key, pressure, std, metric):
    """Print one contrast and return {(model,cat): pct_change}."""
    print("\n" + "=" * 96)
    print(title)
    print(note)
    print("=" * 96)
    print(f"  {'model':16s} {'category':22s} {'Standard':>9s} {'Pressure':>9s} "
          f"{'change':>9s} {'n_std':>6s} {'n_pre':>6s} {'MWU p':>10s}")
    changes = {}
    for m in MODELS:
        for c in CATS:
            s = std_key(std, m, c)
            p = pressure.get((m, c), [])
            if not s or not p:
                continue
            pv = float("nan")
            if SCIPY and len(s) >= 3 and len(p) >= 3:
                pv = float(_stats.mannwhitneyu(s, p, alternative="two-sided").pvalue)
            ch = pct(st.mean(s), st.mean(p))
            changes[(m, c)] = ch
            print(f"  {m:16s} {c:22s} {st.mean(s):9.3f} {st.mean(p):9.3f} "
                  f"{ch:8.1f}% {len(s):6d} {len(p):6d} {pv:10.4f}")
    return changes


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metric", default="avg_risk_score",
                    choices=["avg_risk_score", "max_risk_score"])
    ap.add_argument("--pressure-rescored", action="store_true",
                    help="Include contrast C using pressure_rescored_standard/")
    args = ap.parse_args()

    std = load_standard(args.metric)
    pre_pub = load_pressure_published()
    pre_res = load_pressure_rescored(args.metric) if args.pressure_rescored else {}

    print("=" * 96)
    print("MODALITY-MATCHED STANDARD vs PRESSURE")
    print(f"Standard metric: {args.metric}")
    print("=" * 96)
    if not std:
        print("[FAIL] no Standard results found under test/results")
        return 1
    if not pre_pub:
        print("[FAIL] no Pressure results found under phase1_results")
        return 1

    a = block(
        "A. UNMATCHED (as published)",
        "   Standard pools 3 modalities x 2 scopes; Pressure is text/general and uses\n"
        "   a DIFFERENT scoring instrument. Four differences at once.",
        lambda s, m, c: [v for (mm, cc, sc, mo), vs in s.items()
                         if mm == m and cc == c for v in vs],
        pre_pub, std, args.metric)

    b = block(
        "B. MODALITY + SCOPE MATCHED",
        "   Standard restricted to text + general-context. Modality and scope are now\n"
        "   held fixed; the scoring INSTRUMENT still differs, so this is not yet causal.",
        lambda s, m, c: s.get((m, c, "complete_all", "text"), []),
        pre_pub, std, args.metric)

    c = {}
    if args.pressure_rescored:
        if pre_res:
            c = block(
                "C. FULLY MATCHED (modality + scope + instrument)",
                "   Standard text/general vs Pressure re-scored with the Standard judge.\n"
                "   Framing is the only remaining difference. THIS is the causal estimate.",
                lambda s, m, c_: s.get((m, c_, "complete_all", "text"), []),
                pre_res, std, args.metric)
        else:
            print("\n[WARN] --pressure-rescored given but no data in "
                  f"{RESCORED_DIR.name}/.\n"
                  "       Run: python rescore_pressure_standard_instrument.py "
                  "--categories update_resistance --parallel 4")

    # ---- what each control removed -------------------------------------
    print("\n" + "=" * 96)
    print("WHAT EACH CONTROL REMOVES  (percentage-point change in the estimate)")
    print("=" * 96)
    print(f"  {'model':16s} {'category':22s} {'A unmatched':>12s} {'B +mod/scope':>13s} "
          f"{'C +instrument':>14s}")
    for k in sorted(set(a) | set(b) | set(c)):
        m, cat = k
        fa = f"{a[k]:11.1f}%" if k in a else "         --"
        fb = f"{b[k]:12.1f}%" if k in b else "          --"
        fc = f"{c[k]:13.1f}%" if k in c else "           --"
        print(f"  {m:16s} {cat:22s} {fa} {fb} {fc}")

    print("\nReading: A is the published figure. B removes modality and scope. C removes")
    print("the instrument difference as well and is the only contrast that isolates")
    print("framing. Report C where available; where it is not, moderate the claim.")
    if not c:
        print("\nNo fully-matched estimate available yet. For update resistance run:")
        print("  python rescore_pressure_standard_instrument.py --categories update_resistance --parallel 4")
        print("  python matched_comparison.py --pressure-rescored")
        print("Oversight avoidance and centralisation cannot be instrument-matched:")
        print("their pressure probes use stage vocabularies (assessment, awareness,")
        print("reflection, resolution, stakeholder_response) with no counterpart in the")
        print("Standard risk stages. Moderate the claim for those two dimensions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
