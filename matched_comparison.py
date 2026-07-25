#!/usr/bin/env python3
"""
Modality-matched Standard vs Pressure comparison (rebuttal §1.2, AC issue 2).

The problem
-----------
The submission's headline "54-86% reduction from Standard to Pressure" compares
cells that differ on three axes at once:

  * execution modality  - Standard pools text + tools + sandbox; Pressure is
                          text only;
  * scope               - Standard pools general-context + domain-enriched;
                          Pressure is general-context only;
  * framing             - the pressure conditions themselves.

So the contrast estimates sensitivity to the whole evaluation protocol, not to
pressure framing. As the AC put it, it "cannot be attributed specifically to
pressure framing".

What this does
--------------
Rebuilds the contrast on a matched slice: **text modality, general-context
scope, same 15 seeds** on both sides. That holds modality and scope fixed and
leaves framing as the only varying factor, which is the estimate the causal
claim needs.

Both sides are scored with the same instrument (`avg_risk_score` from
test_all_scenarios) and the corrected, non-falsy score extraction.

Usage:
    python matched_comparison.py
    python matched_comparison.py --metric max_risk_score
"""

import argparse
import glob
import json
import os
import statistics as st
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).parent
CATS = ("update_resistance", "oversight_avoidance", "centralisation")
MODELS = ("sonnet_45", "gemini_25_pro", "gpt_41")
MODEL_LABEL = {"sonnet_45": "Claude Sonnet 4.5", "gemini_25_pro": "Gemini 2.5 Pro",
               "gpt_41": "GPT-4.1"}
CAT_LABEL = {"update_resistance": "Update resistance",
             "oversight_avoidance": "Oversight avoidance",
             "centralisation": "Centralization"}

try:
    from scipy import stats as _stats
    SCIPY = True
except ImportError:
    SCIPY = False


def score_of(rec, metric):
    """Corrected extraction: explicit None check, so a legitimate 0.0 survives."""
    agg = rec.get("aggregate_scores") or {}
    v = agg.get(metric)
    return float(v) if v is not None else None


def load_standard(metric):
    """Standard benchmark, indexed by (model, category, scope, modality)."""
    out = defaultdict(list)
    for f in (str(q) for q in (BASE / "test" / "results").rglob("*.json")):
        if "partial" in os.path.basename(f):
            continue
        parts = f.replace(os.sep, "/").split("/")
        try:
            cat = next(p for p in parts if p in CATS)
            model = next(p for p in parts if p in MODELS)
            scope = next(p for p in parts if p in ("complete_all", "domain"))
            modality = next(p for p in parts if p in ("text", "tools", "sandbox"))
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
            s = score_of(x, metric)
            if s is not None:
                out[(model, cat, scope, modality)].append(s)
    return out


def load_pressure(metric):
    """Pressure benchmark, indexed by (model, category). Text, general-context."""
    out = defaultdict(list)
    for f in (str(q) for q in (BASE / "phase1_results").rglob("*.json")):
        if "partial" in os.path.basename(f):
            continue
        parts = f.replace(os.sep, "/").split("/")
        try:
            model = next(p for p in parts if p in MODELS)
            cat = next(p for p in parts if p in CATS)
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
            s = score_of(x, metric)
            if s is not None:
                out[(model, cat)].append(s)
    return out


def pct(a, b):
    return (b - a) / a * 100.0 if a else float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--metric", default="avg_risk_score",
                    choices=["avg_risk_score", "max_risk_score"])
    args = ap.parse_args()

    std = load_standard(args.metric)
    pre = load_pressure(args.metric)

    print("=" * 92)
    print("MODALITY-MATCHED STANDARD vs PRESSURE")
    print(f"metric: {args.metric}   |   matched slice: text modality, general-context scope")
    print("=" * 92)

    # ---- the unmatched contrast, as published --------------------------
    print("\n1. UNMATCHED (as published): Standard pools 3 modalities x 2 scopes")
    print(f"   {'model':16s} {'category':22s} {'Standard':>9s} {'Pressure':>9s} {'change':>9s}")
    unmatched = {}
    for m in MODELS:
        for c in CATS:
            s = [v for (mm, cc, sc, mo), vs in std.items()
                 if mm == m and cc == c for v in vs]
            p = pre.get((m, c), [])
            if not s or not p:
                continue
            unmatched[(m, c)] = (st.mean(s), st.mean(p))
            print(f"   {m:16s} {c:22s} {st.mean(s):9.3f} {st.mean(p):9.3f} "
                  f"{pct(st.mean(s), st.mean(p)):8.1f}%")

    # ---- the matched contrast ------------------------------------------
    print("\n2. MATCHED: Standard text + general-context only, same seeds")
    print(f"   {'model':16s} {'category':22s} {'Standard':>9s} {'Pressure':>9s} "
          f"{'change':>9s} {'n_std':>6s} {'n_pre':>6s} {'MWU p':>9s}")
    matched = {}
    for m in MODELS:
        for c in CATS:
            s = std.get((m, c, "complete_all", "text"), [])
            p = pre.get((m, c), [])
            if not s or not p:
                continue
            pv = float("nan")
            if SCIPY and len(s) >= 3 and len(p) >= 3:
                pv = float(_stats.mannwhitneyu(s, p, alternative="two-sided").pvalue)
            matched[(m, c)] = (st.mean(s), st.mean(p), pv)
            print(f"   {m:16s} {c:22s} {st.mean(s):9.3f} {st.mean(p):9.3f} "
                  f"{pct(st.mean(s), st.mean(p)):8.1f}% {len(s):6d} {len(p):6d} {pv:9.4f}")

    # ---- how much of the published effect survives matching -------------
    print("\n3. HOW MUCH OF THE PUBLISHED EFFECT SURVIVES MATCHING")
    print(f"   {'model':16s} {'category':22s} {'unmatched':>10s} {'matched':>10s} "
          f"{'attributable to':>16s}")
    print(f"   {'':16s} {'':22s} {'change':>10s} {'change':>10s} {'modality+scope':>16s}")
    for k in sorted(set(unmatched) & set(matched)):
        m, c = k
        us, up = unmatched[k]
        ms, mp, _ = matched[k]
        u_ch, m_ch = pct(us, up), pct(ms, mp)
        print(f"   {m:16s} {c:22s} {u_ch:9.1f}% {m_ch:9.1f}% {u_ch - m_ch:15.1f}pp")

    # ---- per-dimension summary ranges ----------------------------------
    print("\n4. PER-DIMENSION RANGES (across models)")
    print(f"   {'category':22s} {'unmatched change':>18s} {'matched change':>18s}")
    for c in CATS:
        u = [pct(*unmatched[(m, c)]) for m in MODELS if (m, c) in unmatched]
        mm = [pct(matched[(m, c)][0], matched[(m, c)][1]) for m in MODELS if (m, c) in matched]
        if not u or not mm:
            continue
        print(f"   {c:22s} {min(u):7.0f}% to {max(u):5.0f}%   "
              f"{min(mm):7.0f}% to {max(mm):5.0f}%")

    print("\nThe matched column is the estimate the causal claim needs; the difference")
    print("between the two columns is what modality and scope were contributing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
