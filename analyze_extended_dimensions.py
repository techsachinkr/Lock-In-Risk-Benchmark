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
    print("  Scenario-level correlation between dimensions is IMPOSSIBLE by construction:")
    print("  each scenario presents one dimension-specific decision and is scored against")
    print("  that dimension's rubric only, so no scenario carries two dimension scores.")
    print("  Correlating per-model means instead would be a 3-point correlation and is")
    print("  not reported: with n=3 Spearman returns +/-1.0 by arithmetic.\n")
    print("  The available empirical evidence is RANK REVERSAL across dimensions. If the")
    print("  five dimensions measured one underlying trait, model ordering would be")
    print("  stable across them.\n")

    ranks = {}
    print(f"  {'dimension':26s} " + " ".join(f"{LABEL[m][:13]:>15s}" for m in MODELS))
    print("  " + "-" * 74)
    for c in cats:
        means = {m: (np.mean(cell[(m, c)]) if cell.get((m, c)) else float("nan"))
                 for m in MODELS}
        order = sorted([m for m in MODELS if np.isfinite(means[m])],
                       key=lambda m: -means[m])
        ranks[c] = {m: order.index(m) + 1 for m in order}
        line = f"  {LABEL[c][:26]:26s} "
        for m in MODELS:
            r = ranks[c].get(m)
            line += f"{means[m]:10.3f} (#{r})" if r else f"{'--':>15s}"
        print(line)

    print()
    reversals = 0
    pairs = 0
    for c1, c2 in combinations([c for c in cats if ranks.get(c)], 2):
        common = [m for m in MODELS if m in ranks[c1] and m in ranks[c2]]
        for a, b in combinations(common, 2):
            pairs += 1
            if (ranks[c1][a] < ranks[c1][b]) != (ranks[c2][a] < ranks[c2][b]):
                reversals += 1
    print(f"  Model-pair orderings that REVERSE between two dimensions: "
          f"{reversals}/{pairs} ({100*reversals/pairs:.0f}%)")
    top = {c: min(ranks[c], key=ranks[c].get) for c in cats if ranks.get(c)}
    distinct = len(set(top.values()))
    print(f"  Distinct models holding the top rank across the {len(top)} dimensions: {distinct}")
    for c in cats:
        if c in top:
            print(f"    {LABEL[c][:26]:28s} highest = {LABEL[top[c]]}")
    if distinct > 1:
        print("\n  No single model is highest on every dimension, and model orderings")
        print("  reverse between dimensions, so the dimensions are not collapsing onto one")
        print("  latent trait. This is the claim the data supports; it does not establish")
        print("  that the dimensions are mutually exclusive at the BEHAVIOUR level, which")
        print("  is a design question we answer by scenario construction rather than")
        print("  statistically.")

    # Within-model spread: is any model's profile flat?
    if SCIPY:
        print("\n  Within-model variation across dimensions (Kruskal-Wallis):")
        for m in MODELS:
            groups = [cell[(m, c)] for c in cats if len(cell.get((m, c), [])) >= 3]
            if len(groups) >= 3:
                h, p = _stats.kruskal(*groups)
                print(f"    {LABEL[m]:20s} H={h:7.3f}  p={p:.4f}  "
                      f"{'profile is NOT flat' if p < 0.05 else 'profile is flat (ns)'}")

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
