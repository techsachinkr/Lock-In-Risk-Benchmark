#!/usr/bin/env python3
"""
Benchmark cross-run variance analysis.

Reads compare_runs/{run}/{category}/{model}/{scope}/{variant}/ and produces
a report matching the structure of variance_analysis_report.txt.

Usage:
    python variance_analysis.py
    python variance_analysis.py --runs-dir compare_runs --output variance_analysis_report.txt
"""

import json
import math
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from itertools import combinations

try:
    from scipy import stats as _scipy_stats
    SCIPY = True
except ImportError:
    SCIPY = False

BASE = Path(__file__).parent


# ─────────────────────────── data loading ────────────────────────────────────

def load_compare_runs(runs_dir: Path):
    """
    Returns:
        summaries: list of dicts with keys
            run, category, model, scope, variant, avg_risk_score, scores
        scenarios: list of dicts with keys
            run, category, model, scope, variant, score
    """
    summaries = []
    scenarios = []
    n_summaries = 0

    for summary_file in sorted(runs_dir.glob("**/*_summary.json")):
        parts = summary_file.relative_to(runs_dir).parts
        # expected: run / category / model / scope / variant / filename
        if len(parts) < 6:
            continue
        run, category, model, scope, variant = parts[0], parts[1], parts[2], parts[3], parts[4]
        try:
            data = json.loads(summary_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        risk_stats = data.get("risk_statistics", {})
        avg = risk_stats.get("avg_risk_score")
        scores = risk_stats.get("scores", [])
        if avg is None:
            continue
        summaries.append({
            "run": run, "category": category, "model": model,
            "scope": scope, "variant": variant,
            "avg_risk_score": avg, "scores": scores,
        })
        n_summaries += 1

    # load per-scenario scores from results files
    for results_file in sorted(runs_dir.glob("**/*_results.json")):
        parts = results_file.relative_to(runs_dir).parts
        if len(parts) < 6:
            continue
        run, category, model, scope, variant = parts[0], parts[1], parts[2], parts[3], parts[4]
        try:
            rows = json.loads(results_file.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            agg = row.get("aggregate_scores", {})
            score = (agg.get("avg_risk_score") or
                     agg.get("max_risk_score") or
                     agg.get("final_risk_score"))
            if score is not None:
                scenarios.append({
                    "run": run, "category": category, "model": model,
                    "scope": scope, "variant": variant,
                    "score": float(score),
                })

    return summaries, scenarios, n_summaries


# ─────────────────────────── statistics helpers ──────────────────────────────

def mean(xs): return sum(xs) / len(xs) if xs else 0.0
def variance(xs):
    if len(xs) < 2: return 0.0
    m = mean(xs)
    return sum((x - m) ** 2 for x in xs) / (len(xs) - 1)
def std(xs): return math.sqrt(variance(xs))
def cv(xs): return (std(xs) / mean(xs) * 100) if mean(xs) else 0.0

def ci95(xs):
    n = len(xs)
    if n < 2:
        return (xs[0], xs[0]) if xs else (0.0, 0.0)
    if SCIPY:
        lo, hi = _scipy_stats.t.interval(0.95, df=n-1, loc=mean(xs), scale=_scipy_stats.sem(xs))
    else:
        t = 1.96  # approximate
        se = std(xs) / math.sqrt(n)
        lo, hi = mean(xs) - t * se, mean(xs) + t * se
    return (lo, hi)

def kruskal(*groups):
    if not SCIPY:
        return None, None
    groups = [g for g in groups if len(g) >= 1]
    if len(groups) < 2:
        return None, None
    try:
        h, p = _scipy_stats.kruskal(*groups)
        return h, p
    except Exception:
        return None, None

def mannwhitney(a, b):
    if not SCIPY or len(a) < 1 or len(b) < 1:
        return None, None
    try:
        u, p = _scipy_stats.mannwhitneyu(a, b, alternative="two-sided")
        return u, p
    except Exception:
        return None, None

def sig_code(p):
    if p is None: return "n/a"
    if p < 0.001: return "***"
    if p < 0.01:  return "**"
    if p < 0.05:  return "*"
    return "ns"


# ─────────────────────────── report sections ─────────────────────────────────

W = 100

def write_report(lines: List[str], out_path: Optional[Path]) -> None:
    text = "\n".join(lines) + "\n"
    print(text)
    if out_path:
        out_path.write_text(text, encoding="utf-8")
        print(f"[saved to {out_path}]")


def section(lines, title):
    lines += ["", "=" * 80, f"  {title}", "=" * 80, ""]


def build_report(summaries, scenarios, n_summary_files, runs_dir):
    lines = []
    lines.append(f"Found {n_summary_files} summary files in {runs_dir.name}")

    # discover dimensions
    runs      = sorted({s["run"]      for s in summaries})
    cats      = sorted({s["category"] for s in summaries})
    models    = sorted({s["model"]    for s in summaries})
    scopes    = sorted({s["scope"]    for s in summaries})
    variants  = sorted({s["variant"]  for s in summaries})

    lines += ["", "",
              "=" * 80,
              "  BENCHMARK CROSS-RUN ANALYSIS",
              "=" * 80,
              f"  Runs      : {', '.join(runs)}",
              f"  Categories: {', '.join(cats)}",
              f"  Models    : {', '.join(models)}",
              f"  Scopes    : {', '.join(scopes)}",
              f"  Variants  : {', '.join(variants)}",
              f"  Scipy     : {'available' if SCIPY else 'NOT available (install scipy for significance tests)'}",
              ""]

    # ── index summaries ───────────────────────────────────────────────────────
    # (model, cat, scope, variant) -> {run -> avg_risk_score}
    cell: Dict[Tuple, Dict[str, float]] = defaultdict(dict)
    for s in summaries:
        cell[(s["model"], s["category"], s["scope"], s["variant"])][s["run"]] = s["avg_risk_score"]

    # (model, cat, scope, variant, run) -> [scores]  (per-scenario)
    scen_idx: Dict[Tuple, List[float]] = defaultdict(list)
    for sc in scenarios:
        scen_idx[(sc["model"], sc["category"], sc["scope"], sc["variant"], sc["run"])].append(sc["score"])

    # ── 1. run-to-run variance ────────────────────────────────────────────────
    section(lines, "1. RUN-TO-RUN VARIANCE  (per model x category x scope x variant)")
    hdr = f"{'Combination':<55} {'Mean':>8} {'Std':>8} {'Var':>8} {'CV%':>7}  {'95% CI':>20}  Runs w/data"
    lines.append(hdr)
    lines.append("-" * 103)

    for model in models:
        for cat in cats:
            for scope in scopes:
                for variant in variants:
                    key = (model, cat, scope, variant)
                    run_avgs = cell.get(key, {})
                    vals = [run_avgs[r] for r in runs if r in run_avgs]
                    if not vals:
                        continue
                    m = mean(vals)
                    s = std(vals)
                    v = variance(vals)
                    c = cv(vals)
                    lo, hi = ci95(vals)
                    label = f"{model}/{cat}/{scope}/{variant}"
                    lines.append(
                        f"  {label:<53} {m:>8.4f} {s:>8.4f} {v:>8.4f} {c:>6.1f}%"
                        f"  [{lo:.4f}, {hi:.4f}]  {len(vals)}/{len(runs)}"
                    )

    # ── 2. aggregated variance per model × category ────────────────────────────
    section(lines, "2. AGGREGATED VARIANCE  (across scopes & variants per model x category)")
    hdr2 = f"{'Model':<20} {'Category':<24} {'N runs x cells':>14} {'Mean':>8} {'Std':>8} {'Min':>8} {'Max':>8} {'CV%':>7}"
    lines.append(hdr2)
    lines.append("-" * 95)

    for model in models:
        for cat in cats:
            all_vals = []
            for scope in scopes:
                for variant in variants:
                    key = (model, cat, scope, variant)
                    run_avgs = cell.get(key, {})
                    all_vals.extend(run_avgs.values())
            if not all_vals:
                continue
            m = mean(all_vals)
            s = std(all_vals)
            mn, mx = min(all_vals), max(all_vals)
            c = cv(all_vals)
            lines.append(
                f"  {model:<20} {cat:<24} {len(all_vals):>14}  {m:>8.4f} {s:>8.4f}"
                f"  {mn:>8.4f}  {mx:>8.4f} {c:>6.1f}%"
            )

    # ── 3. run consistency (Kruskal-Wallis) ───────────────────────────────────
    section(lines, "3. RUN CONSISTENCY TESTS  (Kruskal-Wallis: are all runs equivalent?)")
    lines.append("For each (model x category), pool per-run avg_risk_scores and test H0: all runs drawn from same distribution.")
    lines.append("")
    hdr3 = f"{'Model':<20} {'Category':<24} {'Run scores':<55} {'KW H':>8} {'p':>10}   sig"
    lines.append(hdr3)
    lines.append("-" * 105)

    for model in models:
        for cat in cats:
            # per-run: collect all avg_risk_scores across scope x variant cells
            per_run: Dict[str, List[float]] = defaultdict(list)
            for scope in scopes:
                for variant in variants:
                    key = (model, cat, scope, variant)
                    for run, avg in cell.get(key, {}).items():
                        per_run[run].append(avg)

            if len(per_run) < 2:
                continue

            run_summaries = {r: [round(v, 3) for v in vals] for r, vals in sorted(per_run.items())}
            run_str = "  ".join(f"{r}={v}" for r, v in run_summaries.items())

            groups = [per_run[r] for r in sorted(per_run)]
            h, p = kruskal(*groups)

            if h is not None:
                lines.append(f"  {model:<20} {cat:<24} {run_str:<55} {h:>8.3f} {p:>10.4f}  {sig_code(p):>4}")
            else:
                lines.append(f"  {model:<20} {cat:<24} {run_str:<55} {'n/a':>8} {'n/a':>10}  n/a")

    # ── 4. model comparisons per category (Mann-Whitney U) ────────────────────
    section(lines, "4. MODEL COMPARISONS PER CATEGORY  (Mann-Whitney U, two-sided)")
    lines.append("Using all individual scenario-level risk scores pooled across runs.")
    lines.append("")
    hdr4 = (f"{'Category':<24} {'Model A':<20} {'Model B':<20}"
            f" {'nA':>5} {'nB':>5} {'U':>10} {'p':>10}   sig"
            f" {'meanA':>8} {'meanB':>8} {'delta':>8}")
    lines.append(hdr4)
    lines.append("-" * 103)

    for cat in cats:
        for ma, mb in combinations(models, 2):
            a_scores = [sc["score"] for sc in scenarios if sc["category"] == cat and sc["model"] == ma]
            b_scores = [sc["score"] for sc in scenarios if sc["category"] == cat and sc["model"] == mb]
            u, p = mannwhitney(a_scores, b_scores)
            ma_mean = mean(a_scores)
            mb_mean = mean(b_scores)
            delta = ma_mean - mb_mean
            if u is not None:
                lines.append(
                    f"  {cat:<24} {ma:<20} {mb:<20}"
                    f" {len(a_scores):>5} {len(b_scores):>5} {u:>10.1f} {p:>10.4f}  {sig_code(p):>4}"
                    f"  {ma_mean:>7.4f}  {mb_mean:>7.4f}  {delta:>+8.4f}"
                )
            else:
                lines.append(
                    f"  {cat:<24} {ma:<20} {mb:<20}"
                    f" {len(a_scores):>5} {len(b_scores):>5} {'n/a':>10} {'n/a':>10}   n/a"
                    f"  {ma_mean:>7.4f}  {mb_mean:>7.4f}  {delta:>+8.4f}"
                )

    # ── 5. category comparisons per model (Mann-Whitney U) ────────────────────
    section(lines, "5. CATEGORY COMPARISONS PER MODEL  (Mann-Whitney U, two-sided)")
    lines.append("Test whether the same model shows significantly different risk across categories.")
    lines.append("")
    hdr5 = (f"{'Model':<20} {'Category A':<26} {'Category B':<26}"
            f" {'nA':>5} {'nB':>5} {'U':>10} {'p':>10}   sig"
            f" {'meanA':>8} {'meanB':>8} {'delta':>8}")
    lines.append(hdr5)
    lines.append("-" * 110)

    for model in models:
        for ca, cb in combinations(cats, 2):
            a_scores = [sc["score"] for sc in scenarios if sc["model"] == model and sc["category"] == ca]
            b_scores = [sc["score"] for sc in scenarios if sc["model"] == model and sc["category"] == cb]
            u, p = mannwhitney(a_scores, b_scores)
            ma_mean = mean(a_scores)
            mb_mean = mean(b_scores)
            delta = ma_mean - mb_mean
            if u is not None:
                lines.append(
                    f"  {model:<20} {ca:<26} {cb:<26}"
                    f" {len(a_scores):>5} {len(b_scores):>5} {u:>10.1f} {p:>10.4f}  {sig_code(p):>4}"
                    f"  {ma_mean:>7.4f}  {mb_mean:>7.4f}  {delta:>+8.4f}"
                )
            else:
                lines.append(
                    f"  {model:<20} {ca:<26} {cb:<26}"
                    f" {len(a_scores):>5} {len(b_scores):>5} {'n/a':>10} {'n/a':>10}   n/a"
                    f"  {ma_mean:>7.4f}  {mb_mean:>7.4f}  {delta:>+8.4f}"
                )

    # ── 6. scope & variant effects ─────────────────────────────────────────────
    section(lines, "6. SCOPE & VARIANT EFFECTS  (domain vs complete_all, text vs tools)")
    lines.append("")

    for cat in cats:
        lines.append(f"\n  [{cat}]")
        cat_sc = [sc for sc in scenarios if sc["category"] == cat]

        # scope effect
        scope_groups: Dict[str, List[float]] = defaultdict(list)
        for sc in cat_sc:
            scope_groups[sc["scope"]].append(sc["score"])

        for sa, sb in combinations(sorted(scope_groups), 2):
            a, b = scope_groups[sa], scope_groups[sb]
            u, p = mannwhitney(a, b)
            ma, mb = mean(a), mean(b)
            sa_std, sb_std = std(a), std(b)
            u_str = f"{u:.1f}" if u is not None else "n/a"
            p_str = f"{p:.4f}" if p is not None else "n/a"
            lines.append(
                f"    Scope  {sa:<16} vs {sb:<14}: "
                f"mean=[{ma:.4f} vs {mb:.4f}]  std=[{sa_std:.4f} vs {sb_std:.4f}]"
                f"  U={u_str}  p={p_str}  {sig_code(p)}"
            )

        # variant effect
        var_groups: Dict[str, List[float]] = defaultdict(list)
        for sc in cat_sc:
            var_groups[sc["variant"]].append(sc["score"])

        for va, vb in combinations(sorted(var_groups), 2):
            a, b = var_groups[va], var_groups[vb]
            u, p = mannwhitney(a, b)
            ma, mb = mean(a), mean(b)
            sa_std, sb_std = std(a), std(b)
            u_str = f"{u:.1f}" if u is not None else "n/a"
            p_str = f"{p:.4f}" if p is not None else "n/a"
            lines.append(
                f"    Variant {va:<16} vs {vb:<12}: "
                f"mean=[{ma:.4f} vs {mb:.4f}]  std=[{sa_std:.4f} vs {sb_std:.4f}]"
                f"  U={u_str}  p={p_str}  {sig_code(p)}"
            )

    # ── 7. summary mean ± std ─────────────────────────────────────────────────
    section(lines, "7. SUMMARY: MEAN +/- STD RISK SCORE  (across all runs)")
    hdr7 = f"{'Model':<20} {'Category':<24} {'N':>5}  {'Mean +/- Std':<25}  {'95% CI':<24}  CV%"
    lines.append(hdr7)
    lines.append("-" * 100)

    for model in models:
        for cat in cats:
            all_vals = []
            for scope in scopes:
                for variant in variants:
                    key = (model, cat, scope, variant)
                    all_vals.extend(cell.get(key, {}).values())
            if not all_vals:
                continue
            m = mean(all_vals)
            s = std(all_vals)
            c = cv(all_vals)
            lo, hi = ci95(all_vals)
            lines.append(
                f"  {model:<20} {cat:<24} {len(all_vals):>5}"
                f"  {m:.4f} +/- {s:.4f}          "
                f"  [{lo:.4f}, {hi:.4f}]  {c:>6.1f}%"
            )

    # ── 8. model × category × scope cross-tab ────────────────────────────────
    section(lines, "8. MODEL x CATEGORY x SCOPE CROSS-TAB  (domain vs complete_all)")
    lines.append("Aggregated across all variants and runs.  MW = Mann-Whitney U (domain vs complete_all).")
    lines.append("")

    # header
    col = 10
    scope_labels = " | ".join(f"{s:^{col*3+4}}" for s in scopes)
    lines.append(f"  {'Model':<20} {'Category':<24}  {scope_labels}  {'MW U':>9} {'p':>8}   sig   delta")
    sub = " | ".join(f"{'n':>4} {'mean':>7} {'std':>6}" for _ in scopes)
    lines.append(f"  {'':20} {'':24}  {sub}")
    lines.append("  " + "-" * 100)

    for model in models:
        for cat in cats:
            # collect run-level avg_risk_scores per scope (across all variants)
            scope_run_vals: Dict[str, List[float]] = defaultdict(list)
            for scope in scopes:
                for variant in variants:
                    key = (model, cat, scope, variant)
                    scope_run_vals[scope].extend(cell.get(key, {}).values())

            # collect per-scenario scores per scope
            scope_sc_vals: Dict[str, List[float]] = defaultdict(list)
            for sc in scenarios:
                if sc["model"] == model and sc["category"] == cat:
                    scope_sc_vals[sc["scope"]].append(sc["score"])

            # MW test between the two scopes (per-scenario level)
            scope_pair = sorted(scopes)
            if len(scope_pair) == 2:
                sa, sb = scope_pair
                u, p = mannwhitney(scope_sc_vals[sa], scope_sc_vals[sb])
                delta = mean(scope_sc_vals[sa]) - mean(scope_sc_vals[sb]) if scope_sc_vals[sa] and scope_sc_vals[sb] else 0.0
            else:
                u, p, delta = None, None, 0.0

            cells_str = " | ".join(
                f"{len(scope_run_vals[s]):>4} {mean(scope_run_vals[s]):>7.4f} {std(scope_run_vals[s]):>6.4f}"
                if scope_run_vals[s] else f"{'—':>4} {'—':>7} {'—':>6}"
                for s in scopes
            )
            u_str = f"{u:>9.1f}" if u is not None else f"{'n/a':>9}"
            p_str = f"{p:>8.4f}" if p is not None else f"{'n/a':>8}"
            d_str = f"{delta:>+.4f}" if p is not None else "n/a"
            lines.append(
                f"  {model:<20} {cat:<24}  {cells_str}  {u_str} {p_str}  {sig_code(p):>4}  {d_str}"
            )
        lines.append("")

    lines += ["", "",
              "Significance codes: *** p<0.001  ** p<0.01  * p<0.05  ns p>=0.05  n/a p not computed",
              "CV% = coefficient of variation (std/mean x 100); lower -> more consistent across runs.",
              ""]
    return lines


# ─────────────────────────────── main ────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Cross-run variance analysis for benchmark results")
    parser.add_argument("--runs-dir", default="compare_runs", help="Directory containing run subdirs")
    parser.add_argument("--output", "-o", default="variance_analysis_report.txt",
                        help="Output report file (default: variance_analysis_report.txt)")
    args = parser.parse_args()

    runs_dir = BASE / args.runs_dir
    if not runs_dir.exists():
        print(f"ERROR: {runs_dir} not found.")
        return

    print(f"Loading from {runs_dir} ...")
    summaries, scenarios, n_summary_files = load_compare_runs(runs_dir)
    print(f"  {n_summary_files} summary files, {len(scenarios)} individual scenario scores")

    lines = build_report(summaries, scenarios, n_summary_files, runs_dir)
    write_report(lines, BASE / args.output)


if __name__ == "__main__":
    main()
