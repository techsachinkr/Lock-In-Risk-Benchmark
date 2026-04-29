#!/usr/bin/env python3
"""
Aggregate stats from test/results and phase1_results summary files.

Usage:
    python aggregate_benchmarks.py
    python aggregate_benchmarks.py --output aggregated_benchmarks.json
    python aggregate_benchmarks.py --test-dir test/results --phase1-dir phase1_results
"""

import json
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any
from datetime import datetime

BASE = Path(__file__).parent

RISK_ORDER = ["none", "low", "moderate", "high", "critical"]

# Normalise risk level labels so test/results and phase1_results are comparable
RISK_NORM = {
    "none": "none",
    "minimal": "none",
    "low": "low",
    "medium": "moderate",
    "moderate": "moderate",
    "high": "high",
    "critical": "critical",
}


# ─────────────────────────────── loaders ─────────────────────────────────────

def load_test_results(root: Path) -> List[Dict]:
    """
    Load *_summary.json files from:
        test/results/{category}/{model}/{config}/{variant}/
    """
    records = []
    for f in sorted(root.glob("**/*_summary.json")):
        parts = f.relative_to(root).parts
        if len(parts) < 5:
            continue
        category, model_dir, config, variant = parts[0], parts[1], parts[2], parts[3]
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  Warning: could not read {f}: {e}")
            continue
        records.append({
            "source": "test",
            "file": str(f.relative_to(BASE)),
            "category": category,
            "model_dir": model_dir,
            "agent_model": data.get("agent_model", ""),
            "judge_model": data.get("judge_model", ""),
            "config": config,       # e.g. complete_all / domain
            "variant": variant,     # e.g. text / sandbox / tools
            "total_scenarios": data.get("total_scenarios", 0),
            "completed": data.get("by_status", {}).get("completed", 0),
            "failed": data.get("by_status", {}).get("failed", 0),
            "risk_stats": data.get("risk_statistics", {}),
            "by_risk_level": data.get("by_risk_level", {}),
            "by_difficulty": data.get("by_difficulty", {}),
            "high_risk_scenarios": data.get("high_risk_scenarios", []),
        })
    return records


def load_phase1_results(root: Path) -> List[Dict]:
    """
    Load benchmark_*_summary.json files from:
        phase1_results/{model}/{category}/
    """
    records = []
    for f in sorted(root.glob("**/benchmark_*_summary.json")):
        parts = f.relative_to(root).parts
        if len(parts) < 3:
            continue
        model_dir, category = parts[0], parts[1]
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"  Warning: could not read {f}: {e}")
            continue
        records.append({
            "source": "phase1",
            "file": str(f.relative_to(BASE)),
            "category": category,
            "model_dir": model_dir,
            "agent_model": data.get("agent_model", ""),
            "judge_model": data.get("judge_model", ""),
            "config": "phase1",
            "variant": "all",
            "total_scenarios": data.get("total_scenarios", 0),
            "completed": data.get("by_status", {}).get("completed", 0),
            "failed": data.get("by_status", {}).get("failed", 0),
            "risk_stats": data.get("risk_statistics", {}),
            "by_risk_level": data.get("by_risk_level", {}),
            "by_difficulty": data.get("by_difficulty", {}),
            "high_risk_scenarios": data.get("high_risk_scenarios", []),
        })
    return records


# ─────────────────────────────── helpers ─────────────────────────────────────

def normalise_risk(by_risk_level: Dict[str, int]) -> Dict[str, int]:
    out: Dict[str, int] = defaultdict(int)
    for level, count in by_risk_level.items():
        out[RISK_NORM.get(level.lower(), level)] += count
    return dict(out)


def merge_risk(records: List[Dict]) -> Dict[str, int]:
    merged: Dict[str, int] = defaultdict(int)
    for r in records:
        for level, count in normalise_risk(r["by_risk_level"]).items():
            merged[level] += count
    return {k: merged[k] for k in RISK_ORDER if k in merged}


def all_scores(records: List[Dict]) -> List[float]:
    out = []
    for r in records:
        out.extend(r["risk_stats"].get("scores", []))
    return out


def agg_group(records: List[Dict]) -> Dict:
    scores = all_scores(records)
    high_risk = [s for r in records for s in r["high_risk_scenarios"]]
    return {
        "runs": len(records),
        "total_scenarios": sum(r["total_scenarios"] for r in records),
        "completed": sum(r["completed"] for r in records),
        "failed": sum(r["failed"] for r in records),
        "avg_risk_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "max_risk_score": round(max(scores), 4) if scores else 0.0,
        "min_risk_score": round(min(scores), 4) if scores else 0.0,
        "by_risk_level": merge_risk(records),
        "high_risk_count": len(high_risk),
        "high_risk_scenarios": sorted(high_risk, key=lambda x: x.get("risk_score", 0), reverse=True),
    }


# ─────────────────────────────── aggregation ─────────────────────────────────

def build_aggregations(records: List[Dict]) -> Dict:
    by_source: Dict[str, List] = defaultdict(list)
    by_model: Dict[str, List] = defaultdict(list)
    by_category: Dict[str, List] = defaultdict(list)
    by_model_category: Dict[str, Dict[str, List]] = defaultdict(lambda: defaultdict(list))
    by_variant: Dict[str, List] = defaultdict(list)
    by_model_variant: Dict[str, Dict[str, List]] = defaultdict(lambda: defaultdict(list))

    for r in records:
        by_source[r["source"]].append(r)
        by_model[r["agent_model"]].append(r)
        by_category[r["category"]].append(r)
        by_model_category[r["agent_model"]][r["category"]].append(r)
        if r["source"] == "test":
            by_variant[r["variant"]].append(r)
            by_model_variant[r["agent_model"]][r["variant"]].append(r)

    return {
        "generated_at": datetime.now().isoformat(),
        "overall": agg_group(records),
        "by_source": {k: agg_group(v) for k, v in sorted(by_source.items())},
        "by_model": {k: agg_group(v) for k, v in sorted(by_model.items())},
        "by_category": {k: agg_group(v) for k, v in sorted(by_category.items())},
        "by_model_x_category": {
            m: {c: agg_group(v) for c, v in sorted(cats.items())}
            for m, cats in sorted(by_model_category.items())
        },
        "by_variant_type": {k: agg_group(v) for k, v in sorted(by_variant.items())},
        "by_model_x_variant": {
            m: {v: agg_group(recs) for v, recs in sorted(vmap.items())}
            for m, vmap in sorted(by_model_variant.items())
        },
    }


# ─────────────────────────────── printer ─────────────────────────────────────

W = 92

def fmt_risk(by_risk_level: Dict[str, int], total: int) -> str:
    if not total:
        return "-"
    parts = []
    for level in RISK_ORDER:
        if level in by_risk_level:
            n = by_risk_level[level]
            parts.append(f"{level}:{n}({n * 100 // total}%)")
    return "  ".join(parts)


def print_group(g: Dict, indent: int = 2) -> None:
    pad = " " * indent
    total = g["total_scenarios"]
    print(f"{pad}scenarios:{total:>4}  completed:{g['completed']:>4}  failed:{g['failed']:>2}  "
          f"avg:{g['avg_risk_score']:.4f}  max:{g['max_risk_score']:.4f}  "
          f"high_risk:{g['high_risk_count']:>3}")
    print(f"{pad}{fmt_risk(g['by_risk_level'], total)}")


def print_report(agg: Dict) -> None:
    print("=" * W)
    print("LOCK-IN RISK BENCHMARK - AGGREGATED STATS")
    print("=" * W)

    SEP = "-" * W

    print("\nOVERALL")
    print_group(agg["overall"])

    print(f"\n{SEP}")
    print("BY SOURCE")
    for src, g in agg["by_source"].items():
        print(f"  {src}")
        print_group(g, indent=4)

    print(f"\n{SEP}")
    print("BY MODEL")
    for model, g in agg["by_model"].items():
        label = model.split("/")[-1] if "/" in model else model
        print(f"  {label}  ({model})")
        print_group(g, indent=4)

    print(f"\n{SEP}")
    print("BY CATEGORY")
    for cat, g in agg["by_category"].items():
        print(f"  {cat}")
        print_group(g, indent=4)

    print(f"\n{SEP}")
    print("MODEL x CATEGORY")
    for model, cats in agg["by_model_x_category"].items():
        label = model.split("/")[-1] if "/" in model else model
        print(f"  {label}")
        for cat, g in cats.items():
            print(f"    {cat:<28}", end="")
            total = g["total_scenarios"]
            print(f"  n:{total:>3}  avg:{g['avg_risk_score']:.4f}  "
                  f"max:{g['max_risk_score']:.4f}  high:{g['high_risk_count']:>2}")

    if agg["by_variant_type"]:
        print(f"\n{SEP}")
        print("BY VARIANT TYPE  (test/results only)")
        for v, g in agg["by_variant_type"].items():
            print(f"  {v}")
            print_group(g, indent=4)

    if agg["by_model_x_variant"]:
        print(f"\n{SEP}")
        print("MODEL x VARIANT TYPE  (test/results only)")
        for model, vmap in agg["by_model_x_variant"].items():
            label = model.split("/")[-1] if "/" in model else model
            print(f"  {label}")
            for v, g in vmap.items():
                total = g["total_scenarios"]
                print(f"    {v:<10}  n:{total:>3}  avg:{g['avg_risk_score']:.4f}  "
                      f"max:{g['max_risk_score']:.4f}  high:{g['high_risk_count']:>2}")

    print(f"\n{'=' * W}")


# ─────────────────────── per-scenario loaders ────────────────────────────────

import re as _re


def _extract_score_from_str(score_str: str):
    """Parse value and answer from a stringified Score object."""
    val = _re.search(r"value=([0-9.e+\-]+)", score_str)
    ans = _re.search(r"answer='([^']+)'", score_str)
    return (float(val.group(1)) if val else None,
            ans.group(1) if ans else None)


def load_test_scenarios(root: Path) -> List[Dict]:
    """Load per-scenario records from test/results/**/*_results.json."""
    scenarios = []
    for f in sorted(root.glob("**/*_results.json")):
        parts = f.relative_to(root).parts
        if len(parts) < 5:
            continue
        cat_dir = parts[0]
        try:
            rows = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            meta = row.get("scenario_metadata", {})
            result = row.get("result", {})
            agg_sc = row.get("aggregate_scores", {})
            risk_score = result.get("risk_score") or agg_sc.get("max_risk_score")
            risk_level = result.get("risk_level") or agg_sc.get("overall_risk_level")
            scenarios.append({
                "source": "test",
                "scenario_id": row.get("scenario_id", ""),
                "category": meta.get("category") or cat_dir,
                "subcategory": meta.get("subcategory", ""),
                "difficulty": meta.get("difficulty", ""),
                "agent_model": row.get("model", ""),
                "judge_model": row.get("judge_model", ""),
                "variant_type": row.get("variant_type", ""),
                "status": row.get("status", ""),
                "risk_score": float(risk_score) if risk_score is not None else None,
                "risk_level": RISK_NORM.get((risk_level or "").lower(), risk_level or ""),
            })
    return scenarios


def load_phase1_scenarios(root: Path) -> List[Dict]:
    """Load per-scenario records from phase1_results/**/benchmark_*_results.json."""
    scenarios = []
    for f in sorted(root.glob("**/benchmark_*_results.json")):
        parts = f.relative_to(root).parts
        if len(parts) < 3:
            continue
        cat_dir = parts[1]
        try:
            rows = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(rows, list):
            continue
        for row in rows:
            meta = row.get("scenario_metadata", {})
            result_list = row.get("result", [])
            risk_score, risk_level = None, None
            if isinstance(result_list, list) and result_list:
                r0 = result_list[0]
                score = r0.get("score")
                lock_in = r0.get("metadata", {}).get("lock_in_evaluation", {})
                metrics = lock_in.get("metrics", {}) if isinstance(lock_in, dict) else {}
                if isinstance(score, str):
                    risk_score, risk_level = _extract_score_from_str(score)
                elif isinstance(score, dict):
                    risk_score = score.get("value")
                    risk_level = score.get("answer")
                # prefer structured risk_level from metrics when available
                if isinstance(metrics, dict) and metrics.get("risk_level"):
                    risk_level = metrics["risk_level"]
            scenarios.append({
                "source": "phase1",
                "scenario_id": row.get("scenario_id", ""),
                "category": meta.get("category") or cat_dir,
                "subcategory": meta.get("subcategory", ""),
                "difficulty": meta.get("difficulty", ""),
                "agent_model": row.get("agent_model", ""),
                "judge_model": row.get("judge_model", ""),
                "variant_type": meta.get("variant_type", ""),
                "status": "completed",
                "risk_score": float(risk_score) if risk_score is not None else None,
                "risk_level": RISK_NORM.get((risk_level or "").lower(), risk_level or ""),
            })
    return scenarios


# ──────────────────── per-scenario aggregation ───────────────────────────────

def agg_scenarios(rows: List[Dict]) -> Dict:
    scores = [r["risk_score"] for r in rows if r["risk_score"] is not None]
    risk_dist: Dict[str, int] = defaultdict(int)
    for r in rows:
        if r["risk_level"]:
            risk_dist[r["risk_level"]] += 1
    return {
        "n": len(rows),
        "scored": len(scores),
        "avg_risk_score": round(sum(scores) / len(scores), 4) if scores else 0.0,
        "max_risk_score": round(max(scores), 4) if scores else 0.0,
        "min_risk_score": round(min(scores), 4) if scores else 0.0,
        "by_risk_level": {k: risk_dist[k] for k in RISK_ORDER if k in risk_dist},
    }


def build_scenario_aggregations(scenarios: List[Dict]) -> Dict:
    # buckets
    by_src_cat:              Dict = defaultdict(lambda: defaultdict(list))
    by_src_cat_model:        Dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    # test: model x variant x category
    by_model_variant_cat:    Dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    # phase1: pressure variant x category  /  model x pressure variant x category
    by_pvar_cat:             Dict = defaultdict(lambda: defaultdict(list))
    by_model_pvar_cat:       Dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for s in scenarios:
        src   = s["source"]
        cat   = s["category"]
        model = s["agent_model"]
        vt    = s["variant_type"]

        by_src_cat[src][cat].append(s)
        by_src_cat_model[src][cat][model].append(s)

        if src == "test":
            by_model_variant_cat[model][vt][cat].append(s)
        else:  # phase1
            by_pvar_cat[vt][cat].append(s)
            by_model_pvar_cat[model][vt][cat].append(s)

    # ── source x category (existing) ─────────────────────────────────────────
    src_cat: Dict = {}
    for src in sorted(by_src_cat):
        src_cat[src] = {}
        for cat in sorted(by_src_cat[src]):
            rows = by_src_cat[src][cat]
            src_cat[src][cat] = {
                **agg_scenarios(rows),
                "by_model": {
                    m: agg_scenarios(mr)
                    for m, mr in sorted(by_src_cat_model[src][cat].items())
                },
            }

    # ── model x variant x category (test only) ────────────────────────────────
    mvc: Dict = {}
    for model in sorted(by_model_variant_cat):
        mvc[model] = {}
        for vt in sorted(by_model_variant_cat[model]):
            mvc[model][vt] = {
                cat: agg_scenarios(rows)
                for cat, rows in sorted(by_model_variant_cat[model][vt].items())
            }

    # ── pressure variant x category (phase1 only) ────────────────────────────
    pvc: Dict = {}
    for vt in sorted(by_pvar_cat):
        pvc[vt] = {
            cat: agg_scenarios(rows)
            for cat, rows in sorted(by_pvar_cat[vt].items())
        }

    # ── model x pressure variant x category (phase1 only) ────────────────────
    mpvc: Dict = {}
    for model in sorted(by_model_pvar_cat):
        mpvc[model] = {}
        for vt in sorted(by_model_pvar_cat[model]):
            mpvc[model][vt] = {
                cat: agg_scenarios(rows)
                for cat, rows in sorted(by_model_pvar_cat[model][vt].items())
            }

    return {
        "per_scenario_total": len(scenarios),
        "by_source_x_category": src_cat,
        "by_model_x_variant_x_category": mvc,
        "by_pressure_variant_x_category": pvc,
        "by_model_x_pressure_variant_x_category": mpvc,
    }


def _print_cat_row(cat: str, g: Dict) -> None:
    print(f"      {cat:<28} n:{g['n']:>4}  avg:{g['avg_risk_score']:.4f}  "
          f"max:{g['max_risk_score']:.4f}  {fmt_risk(g['by_risk_level'], g['n'])}")


def print_scenario_report(agg: Dict) -> None:
    SEP = "-" * W
    print(f"\n{'=' * W}")
    print("PER-SCENARIO STATS")
    print(f"{'=' * W}")
    print(f"Total individual scenarios: {agg['per_scenario_total']}\n")

    # ── source x category ────────────────────────────────────────────────────
    print(f"{SEP}")
    print("SOURCE x CATEGORY")
    print(f"{SEP}")
    for src, cats in agg["by_source_x_category"].items():
        print(f"  [{src}]")
        for cat, g in cats.items():
            total = g["n"]
            print(f"    {cat}")
            print(f"      n:{total:>4}  avg:{g['avg_risk_score']:.4f}  "
                  f"max:{g['max_risk_score']:.4f}  min:{g['min_risk_score']:.4f}")
            print(f"      {fmt_risk(g['by_risk_level'], total)}")
            for model, mg in g["by_model"].items():
                label = model.split("/")[-1] if "/" in model else model
                print(f"        {label:<28} n:{mg['n']:>4}  "
                      f"avg:{mg['avg_risk_score']:.4f}  max:{mg['max_risk_score']:.4f}")
        print()

    # ── model x variant x category (test) ─────────────────────────────────────
    print(f"{SEP}")
    print("MODEL x VARIANT x CATEGORY  (test/results)")
    print(f"{SEP}")
    for model, vmap in agg["by_model_x_variant_x_category"].items():
        label = model.split("/")[-1] if "/" in model else model
        print(f"  {label}")
        for vt, cats in vmap.items():
            print(f"    [{vt}]")
            for cat, g in cats.items():
                _print_cat_row(cat, g)
        print()

    # ── pressure variant x category (phase1) ──────────────────────────────────
    print(f"{SEP}")
    print("PRESSURE VARIANT x CATEGORY  (phase1_results)")
    print(f"{SEP}")
    for vt, cats in agg["by_pressure_variant_x_category"].items():
        print(f"  [{vt}]")
        for cat, g in cats.items():
            _print_cat_row(cat, g)
    print()

    # ── model x pressure variant x category (phase1) ──────────────────────────
    print(f"{SEP}")
    print("MODEL x PRESSURE VARIANT x CATEGORY  (phase1_results)")
    print(f"{SEP}")
    for model, vmap in agg["by_model_x_pressure_variant_x_category"].items():
        label = model.split("/")[-1] if "/" in model else model
        print(f"  {label}")
        for vt, cats in vmap.items():
            print(f"    [{vt}]")
            for cat, g in cats.items():
                _print_cat_row(cat, g)
        print()

    print("=" * W)


# ─────────────────────────────── main ────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Aggregate stats from test/results and phase1_results")
    parser.add_argument("--test-dir", default="test/results", help="Path to test/results directory")
    parser.add_argument("--phase1-dir", default="phase1_results", help="Path to phase1_results directory")
    parser.add_argument("--output", "-o", help="Save aggregated JSON to this file")
    args = parser.parse_args()

    test_root = BASE / args.test_dir
    phase1_root = BASE / args.phase1_dir

    # --- summary-based stats ---
    test_records = load_test_results(test_root) if test_root.exists() else []
    phase1_records = load_phase1_results(phase1_root) if phase1_root.exists() else []
    all_records = test_records + phase1_records

    print(f"Loaded {len(test_records):>3} summary runs from {args.test_dir}")
    print(f"Loaded {len(phase1_records):>3} summary runs from {args.phase1_dir}")
    print(f"Total:  {len(all_records):>3} summary runs\n")

    if not all_records:
        print("No results found.")
        return

    agg = build_aggregations(all_records)
    print_report(agg)

    # --- per-scenario stats ---
    test_scenarios = load_test_scenarios(test_root) if test_root.exists() else []
    phase1_scenarios = load_phase1_scenarios(phase1_root) if phase1_root.exists() else []
    all_scenarios = test_scenarios + phase1_scenarios

    print(f"\nLoaded {len(test_scenarios):>4} individual scenarios from {args.test_dir}")
    print(f"Loaded {len(phase1_scenarios):>4} individual scenarios from {args.phase1_dir}")

    scenario_agg = build_scenario_aggregations(all_scenarios)
    print_scenario_report(scenario_agg)

    if args.output:
        out = Path(args.output)
        combined = {**agg, "per_scenario": scenario_agg}
        out.write_text(json.dumps(combined, indent=2), encoding="utf-8")
        print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
