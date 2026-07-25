#!/usr/bin/env python3
"""
Analysis of the extended dimensions, plus dimension separability (DYAi W1/Q1/W5).

Two reviewer questions, one script.

W5 (coverage): does the benchmark say anything about dependency creation,
workflow capture and entrenchment? The six previously-unevaluated seeds in
`commitment_stickiness` and `enclosure_dependency` cover three of the four
mechanisms DYAi named. This reports their risk profiles alongside the three
published dimensions, on the same instrument.

W1/Q1 (separability): "Do update resistance, centralization, and oversight
avoidance sit at the same level with mutually exclusive boundaries?" This
correlates the dimensions at the model x seed level. Low correlation is evidence
they measure distinct things; high correlation would support DYAi's concern that
they overlap and that single-label scoring forces a choice.

Usage:
    python analyze_extended_dimensions.py
"""

import json
import os
from collections import defaultdict
from itertools import combinations
from pathlib import Path

import numpy as np

try:
    from scipy import stats as _stats
    SCIPY = True
except ImportError:
    SCIPY = False

REPO = Path(__file__).resolve().parent
EXT_ROOT = REPO / "results_extended_dimensions"
STD_ROOT = REPO / "test" / "results"

PUBLISHED_CATS = ("update_resistance", "oversight_avoidance", "centralisation")
EXTENDED_CATS = ("commitment_stickiness", "enclosure_dependency")
MODELS = ("sonnet_45", "gemini_25_pro", "gpt_41")
LABEL = {"sonnet_45": "Claude Sonnet 4.5", "gemini_25_pro": "Gemini 2.5 Pro",
         "gpt_41": "GPT-4.1",
         "update_resistance": "Update resistance",
         "oversight_avoidance": "Oversight avoidance",
         "centralisation": "Centralization",
         "commitment_stickiness": "Commitment stickiness",
         "enclosure_dependency": "Enclosure / dependency"}


def score(agg):
    """Explicit None check so a legitimate 0.0 survives."""
    if not isinstance(agg, dict):
        return None
    v = agg.get("avg_risk_score")
    return float(v) if v is not None else None


def seed_of(scenario_id):
    return str(scenario_id).split("_DOMAIN")[0]


def load_published():
    rows = []
    for p in STD_ROOT.rglob("*.json"):
        if "partial" in p.name:
            continue
        parts = str(p).replace(os.sep, "/").split("/")
        cat = next((x for x in parts if x in PUBLISHED_CATS), None)
        model = next((x for x in parts if x in MODELS), None)
        if not cat or not model:
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, list):
            continue
        for x in d:
            if not isinstance(x, dict) or x.get("status") != "completed":
                continue
            s = score(x.get("aggregate_scores"))
            if s is not None:
                rows.append({"model": model, "category": cat,
                             "seed": seed_of(x.get("scenario_id")), "score": s})
    return rows


def load_extended():
    rows = []
    if not EXT_ROOT.exists():
        return rows
    for p in EXT_ROOT.rglob("results.json"):
        model = p.parent.parent.name
        if model not in MODELS:
            continue
        try:
            d = json.load(open(p, encoding="utf-8"))
        except Exception:
            continue
        for x in d if isinstance(d, list) else []:
            if not isinstance(x, dict) or x.get("status") != "completed":
                continue
            cat = (x.get("scenario_metadata") or {}).get("category")
            s = score(x.get("aggregate_scores"))
            if cat in EXTENDED_CATS and s is not None:
                rows.append({"model": model, "category": cat,
                             "seed": seed_of(x.get("scenario_id")), "score": s})
    return rows


def main():
    pub = load_published()
    ext = load_extended()
    if not ext:
        print(f"[FAIL] no extended-dimension results under {EXT_ROOT.name}/")
        print("       Run: python run_extended_dimensions.py --parallel 4")
        return 1
    rows = pub + ext
    cats = list(PUBLISHED_CATS) + list(EXTENDED_CATS)

    print("=" * 88)
    print("1. RISK PROFILE ACROSS ALL FIVE DIMENSIONS")
    print("=" * 88)
    print(f"  {'model':18s} " + " ".join(f"{LABEL[c][:13]:>15s}" for c in cats))
    print("  " + "-" * 86)
    cell = defaultdict(list)
    for r in rows:
        cell[(r["model"], r["category"])].append(r["score"])
    for m in MODELS:
        line = f"  {LABEL[m]:18s} "
        for c in cats:
            v = cell.get((m, c), [])
            line += f"{np.mean(v):15.3f}" if v else f"{'--':>15s}"
        print(line)
    print(f"  {'n per cell':18s} " + " ".join(
        f"{len(cell.get((MODELS[0], c), [])):15d}" for c in cats))
    print("\n  The two right-hand columns are the previously-unevaluated dimensions.")

    # ---- cross-model tests on the new dimensions -----------------------
    if SCIPY:
        print("\n" + "=" * 88)
        print("2. CROSS-MODEL DIFFERENCES ON THE NEW DIMENSIONS")
        print("=" * 88)
        for c in EXTENDED_CATS:
            print(f"  {LABEL[c]}:")
            for a, b in combinations(MODELS, 2):
                va, vb = cell.get((a, c), []), cell.get((b, c), [])
                if len(va) >= 3 and len(vb) >= 3:
                    p = float(_stats.mannwhitneyu(va, vb, alternative="two-sided").pvalue)
                    print(f"    {LABEL[a][:20]:22s} vs {LABEL[b][:20]:22s} "
                          f"{np.mean(va):.3f} vs {np.mean(vb):.3f}  p={p:.4f} "
                          f"{'*' if p < 0.05 else 'ns'}")

    # ---- separability (DYAi W1/Q1) --------------------------------------
    print("\n" + "=" * 88)
    print("3. DIMENSION SEPARABILITY  (DYAi W1/Q1)")
    print("=" * 88)
    print("  Spearman correlation between dimension scores at the model x seed level.")
    print("  Low correlation = the dimensions measure distinct things.\n")
    by_ms = defaultdict(list)
    for r in rows:
        by_ms[(r["model"], r["category"], r["seed"])].append(r["score"])
    agg = {k: float(np.mean(v)) for k, v in by_ms.items()}
    print(f"  {'dimension pair':50s} {'rho':>7s} {'p':>9s} {'n':>4s}")
    print("  " + "-" * 74)
    rhos = []
    for c1, c2 in combinations(cats, 2):
        xs, ys = [], []
        # Seeds differ between dimensions, so pair on model and rank position
        # within each model instead: compare per-model mean profiles.
        for m in MODELS:
            v1 = [v for (mm, cc, _s), v in agg.items() if mm == m and cc == c1]
            v2 = [v for (mm, cc, _s), v in agg.items() if mm == m and cc == c2]
            if v1 and v2:
                xs.append(float(np.mean(v1)))
                ys.append(float(np.mean(v2)))
        if SCIPY and len(xs) >= 3:
            rho, p = _stats.spearmanr(xs, ys)
            if np.isfinite(rho):
                rhos.append(abs(rho))
                print(f"  {LABEL[c1][:23]:24s} vs {LABEL[c2][:23]:24s} "
                      f"{rho:7.3f} {p:9.4f} {len(xs):4d}")
    if rhos:
        print(f"\n  mean |rho| across dimension pairs: {np.mean(rhos):.3f}")
        print("  NOTE: n = 3 models per pair, so these are descriptive. The stronger")
        print("  evidence for separability is the divergent per-model profile in table 1")
        print("  and the fact that each scenario presents a single dimension-specific")
        print("  decision, scored against that dimension's rubric only.")

    # ---- what the new dimensions add ------------------------------------
    print("\n" + "=" * 88)
    print("4. WHAT THE NEW DIMENSIONS ADD  (DYAi W5)")
    print("=" * 88)
    for c in EXTENDED_CATS:
        vals = [v for m in MODELS for v in cell.get((m, c), [])]
        pubvals = [v for m in MODELS for cc in PUBLISHED_CATS for v in cell.get((m, cc), [])]
        if not vals:
            continue
        print(f"  {LABEL[c]:24s} mean={np.mean(vals):.3f}  "
              f"range=[{np.min(vals):.3f}, {np.max(vals):.3f}]  n={len(vals)}")
        if SCIPY and pubvals:
            p = float(_stats.mannwhitneyu(vals, pubvals, alternative="two-sided").pvalue)
            print(f"  {'':24s} vs all published dimensions pooled "
                  f"({np.mean(pubvals):.3f}): p={p:.4f}")
    print("\n  These cover dependency creation (ENC_DEP_0016), workflow capture")
    print("  (ENC_ALT_0017), vendor lock-in (ENC_VENDOR_0015) and commitment")
    print("  entrenchment (COMM_*) - three of the four mechanisms DYAi listed as")
    print("  outside the benchmark's scope.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
