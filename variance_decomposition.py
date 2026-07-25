#!/usr/bin/env python3
"""
Variance decomposition by design factor (rebuttal §1.3, DYAi Q3).

Why this exists
---------------
The submission reported ICC < 0.01 for the base scenario and read it as evidence
that the deterministically-generated variants are effectively independent.
Reviewer DYAi objected that a near-zero ICC is equally consistent with the
opposite reading: that surface features of the variants (modality labels, prompt
templates, scope wording) swamp the seed's construct identity.

Both readings are unsupported, because the ICC itself is uninformative here. It
comes from a per-category mixed model with only 8, 4 and 3 seed groups
(clustered_reanalysis.py). With that few clusters the REML variance component
collapses to the boundary - the reported random-effect variances are 0.0002,
0.0000 and 0.0000, and the oversight-avoidance and centralisation fits are
degenerate (intercept 0.000 with no standard error). A variance component
estimated at zero from three groups is not evidence of anything.

This script answers the question directly instead, with a decomposition that
requires no variance-component fit: the share of total score variance explained
by each design factor (one-way eta-squared), plus seed eta-squared computed
within each model x category cell so that seed is not confounded with category.

Usage:
    python variance_decomposition.py
    python variance_decomposition.py --runs-dir compare_runs
"""

import argparse
import glob
import json
import os
import re
from pathlib import Path

import numpy as np

BASE = Path(__file__).parent
CATS = ("update_resistance", "oversight_avoidance", "centralisation")
SCOPES = ("complete_all", "domain")
VARIANTS = ("text", "tools", "sandbox")


def load(runs_dir):
    """One row per completed scenario-run, tagged with its design factors."""
    rows = []
    for f in glob.glob(str(BASE / runs_dir / "**" / "*.json"), recursive=True):
        if "partial" in os.path.basename(f):
            continue
        parts = f.replace(os.sep, "/").split("/")
        run = next((p for p in parts if re.fullmatch(r"run\d", p)), None)
        cat = next((p for p in parts if p in CATS), None)
        scope = next((p for p in parts if p in SCOPES), None)
        variant = next((p for p in parts if p in VARIANTS), None)
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, list):
            continue
        for x in d:
            if not isinstance(x, dict) or x.get("status") != "completed":
                continue
            # Corrected extraction: an explicit None check, so a legitimate 0.0
            # is retained (see variance_analysis.py for the original bug).
            agg = x.get("aggregate_scores") or {}
            v = agg.get("avg_risk_score")
            if v is None:
                continue
            sid = x["scenario_id"]
            seed = re.sub(r"_(TOOLS|TEXT|SANDBOX)_", "_", sid).split("_DOMAIN")[0]
            rows.append(dict(y=float(v), run=run, model=x.get("model"), cat=cat,
                             scope=scope, variant=variant, seed=seed, sid=sid))
    return rows


def eta_squared(rows, factor, ys=None):
    """Share of total variance explained by `factor` (one-way, unadjusted)."""
    y = np.array([r["y"] for r in rows]) if ys is None else ys
    sst = ((y - y.mean()) ** 2).sum()
    if sst == 0:
        return float("nan"), 0
    groups = {}
    for r in rows:
        groups.setdefault(r[factor], []).append(r["y"])
    ssb = sum(len(v) * (np.mean(v) - y.mean()) ** 2 for v in groups.values())
    return ssb / sst, len(groups)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs-dir", default="compare_runs")
    args = ap.parse_args()

    rows = load(args.runs_dir)
    if not rows:
        print(f"[FAIL] no completed scenario-runs found under {args.runs_dir}")
        return 1
    y = np.array([r["y"] for r in rows])

    print("=" * 78)
    print("VARIANCE DECOMPOSITION BY DESIGN FACTOR")
    print("=" * 78)
    print(f"  n = {len(y)} completed scenario-runs   grand mean = {y.mean():.4f}   "
          f"SST = {((y - y.mean())**2).sum():.2f}\n")
    print(f"  {'factor':22s} {'levels':>7s} {'eta^2':>8s}")
    print("  " + "-" * 39)
    results = {}
    for fac, label in [("seed", "Seed scenario"), ("model", "Model"),
                       ("cat", "Category"), ("variant", "Modality"),
                       ("scope", "Scope"), ("run", "Replication run"),
                       ("sid", "Scenario instance")]:
        e, k = eta_squared(rows, fac)
        results[fac] = e
        print(f"  {label:22s} {k:7d} {e:8.3f}")

    design = sum(results[f] for f in ("model", "cat", "variant", "scope", "run"))
    print("\n  Seed scenario explains {:.1%} of variance; model + category + modality +"
          .format(results["seed"]))
    print(f"  scope + run together explain {design:.1%}.")
    if results["seed"] > design:
        print("  -> Seed identity carries MORE signal than all design factors combined,")
        print("     so the variants are NOT independent draws (the submission's claim")
        print("     is withdrawn). But modality and scope are the SMALLEST factors")
        print("     ({:.1%}, {:.1%}), so surface features do not dominate the seed"
              .format(results["variant"], results["scope"]))
        print("     either (DYAi's alternative is also not supported).")
        print("  -> Seed-level clustering remains the correct conservative unit.")

    print("\n" + "-" * 78)
    print("Seed eta^2 WITHIN each model x category cell")
    print("(category held fixed, so seed is not confounded with dimension)")
    print("-" * 78)
    cells = {}
    for r in rows:
        cells.setdefault((r["model"], r["cat"]), []).append(r)
    for (m, c), rs in sorted(cells.items()):
        if len(rs) < 8:
            continue
        yy = np.array([r["y"] for r in rs])
        e, k = eta_squared(rs, "seed", ys=yy)
        print(f"  {str(m)[:28]:30s} {str(c):22s} n={len(rs):3d} seeds={k:2d} "
              f"eta^2={e:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
