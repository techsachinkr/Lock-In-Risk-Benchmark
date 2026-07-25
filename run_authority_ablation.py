"""
Authority-Framing Ablation Runner (Experiment 7a)
=================================================

Runs each generated arm x 16 update-resistance text scenarios x 3 models, using
the SAME pipeline that produced the Standard benchmark's text UR cell in the paper
(test_all_scenarios.ScenarioTestRunner).

Arms (see benchmarks/generate_authority_variants.py for the full rationale)
    L1   unattributed directive, system prompt unchanged   (published baseline)
    L2   + named sender and role                           (asserted authority)
    L3   + deciding body and decision record               (asserted authority)
    L4   + authority basis and scope                       (asserted authority, max)
    L1V  L1 directive + governance preamble                (verifiability control)
    L4V  L4 directive + governance preamble                (VERIFIED authority)
    L4P  L4 + supersession / no-approval-needed            (procedural component)

Default is L1 L2 L3 L4 L1V L4V. The V arms exist because L2-L4 place authority
claims in the untrusted user channel while the system prompt names no legitimate
authority, so nothing in L2-L4 is verifiable; a null result at L4 alone cannot
distinguish "the probe was measuring authentication" from "the model correctly
refused self-asserted authority".

Why reuse test_all_scenarios rather than the evaluation/ package
---------------------------------------------------------------
The reported Standard text/tools numbers come from test_all_scenarios.py: one
judge call per probe, aggregated per scenario. The evaluation/ package is a
different instrument (9 judge methods, ~47 calls per scenario, 8- or 10-factor
weighted score) that produced the pressure logs. Mixing them would make the L1
arm non-comparable to the published baseline. L1 is re-run here rather than
reused from compare_runs so every arm shares one run, one judge version, and one
time window.

TWO AGGREGATIONS OF THE SAME PER-PROBE SCORES - do not conflate them
--------------------------------------------------------------------
Each scenario record carries BOTH `aggregate_scores.avg_risk_score` and
`.max_risk_score`, computed over the same update / post_update / reversion_check
probes. The paper uses both, in different places:

  * The per-modality figures (Figure 5, e.g. "Sonnet text UR = 0.744") come from
    the summary path, which averages **max_risk_score** -
    test_all_scenarios.py:2059, `risk_score = agg.get('max_risk_score', 0)`.
  * The pooled cross-model UR means (Sonnet 0.435 / Gemini 0.252 / GPT-4.1 0.274)
    are means of **avg_risk_score**.

Measured on the published text UR runs in compare_runs/, the two differ
substantially: mean(avg) vs mean(max) is 0.608 vs 0.821 for Sonnet, 0.186 vs
0.336 for Gemini, 0.205 vs 0.331 for GPT-4.1.

`avg_risk_score` is PRE-REGISTERED as this ablation's primary metric, chosen
before any data was collected, for two reasons: it is the metric behind the
paper's own cross-model gap (the claim under review), and `max_risk_score` is
saturated at exactly 1.000 in 28% of published text UR scenario-runs and - being
a maximum over probes - cannot register a decline confined to the post-update
stage, which is precisely the verify-then-comply pattern this design exists to
detect. Report the secondary metric too, via:

    python analyze_authority_ablation.py --metric max_risk_score \
        --output-prefix authority_ablation_max

Expect L1 to land near the pooled-mean family (~0.6 for Sonnet on text), NOT at
0.744; that figure is a different aggregation, not a target to reproduce.

Held identical to the original Standard runs
    agent temperature 0.7, judge temperature 0.1, judge openai/gpt-4o,
    max_tokens 2048 (agent) / 1024 (judge), text modality, UR category only.
These live inside ScenarioTestRunner and are deliberately not overridden.

Usage
-----
    python run_authority_ablation.py --dry-run
    python run_authority_ablation.py --parallel 4
    python run_authority_ablation.py --arms L1 L4 L1V L4V --parallel 4
    python run_authority_ablation.py --resume

Requires OPENROUTER_API_KEY (via .env or environment).
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from test_all_scenarios import ScenarioTestRunner  # noqa: E402

GENERATED_DIR = REPO_ROOT / "benchmarks" / "generated"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "results_authority_ablation"

ALL_ARMS = ("L1", "L2", "L3", "L4", "L1V", "L4V", "L4P", "P1", "P2")
DEFAULT_ARMS = ("L1", "L2", "L3", "L4", "L1V", "L4V")

ARM_LABELS = {
    "L1": "unattributed (published design)",
    "L2": "asserted: sender+role",
    "L3": "asserted: + provenance",
    "L4": "asserted: + authority basis/scope",
    "L1V": "control: preamble, unattributed directive",
    "L4V": "VERIFIED: preamble + matching attribution",
    "L4P": "L4 + procedural (supersession, no approval)",
    "P1": "paraphrase: plain register, unattributed",
    "P2": "paraphrase: high specificity, unattributed",
}

# Judge held at the paper's judge model. Changing this invalidates comparability
# with every reported number.
JUDGE_MODEL = "openai/gpt-4o"

# OpenRouter ids are exactly the strings recorded in the reported runs
# (compare_runs/**/*_results.json -> "model").
#
# out_tokens_per_scenario is MEASURED from the existing text UR runs
# (compare_runs/**/update_resistance/**/text/*.json, sum of response_length / 4):
#   gemini-2.5-pro      17,957 chars -> ~4,489 tok   (n=73)
#   gpt-4.1             12,731 chars -> ~3,183 tok   (n=65)
#   claude-sonnet-4.5   12,959 chars -> ~3,240 tok   (n=78)
# Used only for the cost estimate; it never affects what is sent.
MODELS: Dict[str, Dict[str, Any]] = {
    "gemini_25_pro": {"openrouter_id": "google/gemini-2.5-pro", "out_tokens_per_scenario": 4489},
    "gpt_41": {"openrouter_id": "openai/gpt-4.1", "out_tokens_per_scenario": 3183},
    "sonnet_45": {"openrouter_id": "anthropic/claude-sonnet-4.5", "out_tokens_per_scenario": 3240},
}

# USD per 1,000,000 tokens (input, output). OpenRouter list prices recorded
# 2026-07. VERIFY at https://openrouter.ai/models before trusting a budget.
PRICING: Dict[str, tuple] = {
    "google/gemini-2.5-pro": (1.25, 10.00),
    "openai/gpt-4.1": (2.00, 8.00),
    "anthropic/claude-sonnet-4.5": (3.00, 15.00),
    "openai/gpt-4o": (2.50, 10.00),
}

# Cost-model constants, from the pipeline's actual shape. The agent conversation
# accumulates (probe k resends all prior turns); the judge is called once per
# probe with a ~450-token template plus the response it scores.
JUDGE_TEMPLATE_TOKENS = 450
JUDGE_OUTPUT_TOKENS = 250
AGENT_FIXED_INPUT_TOKENS = 150


def arm_path(arm: str) -> Path:
    return GENERATED_DIR / f"authority_scenarios_{arm}.json"


def load_arm(arm: str) -> Dict[str, Any]:
    path = arm_path(arm)
    if not path.exists():
        raise FileNotFoundError(
            f"Missing {path}. Run: python benchmarks/generate_authority_variants.py "
            f"--arms {arm}"
        )
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def arm_shape(arm: str) -> Dict[str, float]:
    bundle = load_arm(arm)
    scenarios = bundle.get("text", [])
    n = len(scenarios)
    probes = sum(len(s.get("probes", [])) for s in scenarios) / n if n else 0.0
    return {"n": n, "probes": probes}


def estimate_cell(model_slug: str, arm: str) -> Dict[str, float]:
    cfg = MODELS[model_slug]
    agent_id = cfg["openrouter_id"]
    shape = arm_shape(arm)
    n_scenarios, n_probes = shape["n"], shape["probes"]
    out_tok = cfg["out_tokens_per_scenario"]

    agent_out = out_tok
    agent_in = (n_probes - 1) / 2 * out_tok + n_probes * AGENT_FIXED_INPUT_TOKENS
    per_response = out_tok / max(n_probes, 1)
    judge_in = n_probes * (JUDGE_TEMPLATE_TOKENS + per_response)
    judge_out = n_probes * JUDGE_OUTPUT_TOKENS

    a_in, a_out = PRICING[agent_id]
    j_in, j_out = PRICING[JUDGE_MODEL]
    agent_cost = (agent_in * a_in + agent_out * a_out) / 1_000_000
    judge_cost = (judge_in * j_in + judge_out * j_out) / 1_000_000

    return {
        "scenarios": n_scenarios,
        "api_calls": n_scenarios * n_probes * 2,
        "agent_cost": agent_cost * n_scenarios,
        "judge_cost": judge_cost * n_scenarios,
        "total_cost": (agent_cost + judge_cost) * n_scenarios,
    }


def print_estimate(model_slugs: List[str], arms: List[str]) -> None:
    print("\n" + "=" * 82)
    print("COST / CALL ESTIMATE")
    print("=" * 82)
    print(f"{'model':16s} {'arm':6s} {'scen':>5s} {'calls':>7s} "
          f"{'agent$':>9s} {'judge$':>9s} {'total$':>9s}")
    print("-" * 82)
    totals = {"scenarios": 0, "api_calls": 0, "agent_cost": 0.0,
              "judge_cost": 0.0, "total_cost": 0.0}
    for slug in model_slugs:
        for arm in arms:
            est = estimate_cell(slug, arm)
            print(f"{slug:16s} {arm:6s} {est['scenarios']:5.0f} {est['api_calls']:7.0f} "
                  f"{est['agent_cost']:9.2f} {est['judge_cost']:9.2f} {est['total_cost']:9.2f}")
            for k in totals:
                totals[k] += est[k]
    print("-" * 82)
    print(f"{'TOTAL':16s} {'':6s} {totals['scenarios']:5.0f} {totals['api_calls']:7.0f} "
          f"{totals['agent_cost']:9.2f} {totals['judge_cost']:9.2f} {totals['total_cost']:9.2f}")
    print("=" * 82)
    calls = totals["api_calls"]
    for workers, label in ((1, "sequential"), (4, "4 workers"), (8, "8 workers")):
        print(f"  wall-clock @3s/call, {label:11s}: {calls * 3.0 / workers / 3600:5.1f} h")
    print("\n  Prices are OpenRouter list rates recorded 2026-07 and are NOT live;\n"
          "  verify before relying on the figure. Estimate excludes retries.\n")


def cell_paths(output_root: Path, model_slug: str, arm: str) -> Dict[str, Path]:
    cell = output_root / model_slug / arm
    return {
        "dir": cell,
        "results": cell / "results.json",
        "meta": cell / "cell_metadata.json",
        "logs": cell / "logs",
    }


def cell_is_complete(paths: Dict[str, Path], expected_n: int) -> bool:
    if not paths["results"].exists():
        return False
    try:
        with open(paths["results"], "r", encoding="utf-8") as fh:
            results = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(results, list) or len(results) != expected_n:
        return False
    return all(r.get("status") == "completed" for r in results)


def run_cell(model_slug: str, arm: str, output_root: Path, parallel: int, delay: float,
             max_retries: int, retry_delay: float, timeout: int) -> Dict[str, Any]:
    cfg = MODELS[model_slug]
    agent_id = cfg["openrouter_id"]
    scenarios_file = arm_path(arm)
    paths = cell_paths(output_root, model_slug, arm)
    paths["dir"].mkdir(parents=True, exist_ok=True)
    paths["logs"].mkdir(parents=True, exist_ok=True)

    print("\n" + "#" * 82)
    print(f"# CELL  model={model_slug}  arm={arm}  ({ARM_LABELS[arm]})")
    print("#" * 82)

    started = datetime.now(timezone.utc)
    runner = ScenarioTestRunner(
        scenarios_file=str(scenarios_file),
        agent_model=agent_id,
        judge_model=JUDGE_MODEL,
        output_dir=str(paths["dir"]),
        log_dir=str(paths["logs"]),
        max_retries=max_retries,
        retry_delay=retry_delay,
        timeout=timeout,
    )
    results = runner.run_all_scenarios(
        variant_types=["text"],
        categories=["update_resistance"],
        delay_between_scenarios=delay,
        parallel=parallel,
    )
    finished = datetime.now(timezone.utc)

    with open(paths["results"], "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2, default=str)

    completed = sum(1 for r in results if r.get("status") == "completed")
    meta = {
        "experiment": "authority_framing_ablation_7a",
        "model_slug": model_slug,
        "agent_model": agent_id,
        "judge_model": JUDGE_MODEL,
        "arm": arm,
        "arm_description": ARM_LABELS[arm],
        "scenarios_file": str(scenarios_file.relative_to(REPO_ROOT)),
        "n_scenarios": len(results),
        "n_completed": completed,
        "n_failed": len(results) - completed,
        "started_utc": started.isoformat(),
        "finished_utc": finished.isoformat(),
        "elapsed_seconds": (finished - started).total_seconds(),
        "parallel_workers": parallel,
        "agent_temperature": 0.7,
        "judge_temperature": 0.1,
        "pipeline": "test_all_scenarios.ScenarioTestRunner.run_text_scenario",
    }
    with open(paths["meta"], "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)

    print(f"\n  [CELL DONE] {model_slug}/{arm}: {completed}/{len(results)} completed "
          f"in {meta['elapsed_seconds']/60:.1f} min")
    if completed != len(results):
        print(f"  [WARN] {len(results)-completed} scenario(s) did not complete; "
              f"re-run with --resume to retry this cell.")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the authority-framing ablation (experiment 7a).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--models", nargs="+", choices=sorted(MODELS), default=sorted(MODELS))
    parser.add_argument("--arms", nargs="+", choices=list(ALL_ARMS), default=list(DEFAULT_ARMS))
    parser.add_argument("--output-root", default=str(DEFAULT_OUTPUT_ROOT))
    parser.add_argument("--parallel", "-p", type=int, default=1,
                        help="Parallel workers per cell (3-5 recommended for rate limits)")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-delay", type=float, default=5.0)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the cost/time estimate and exit without any API call")
    parser.add_argument("--resume", action="store_true", help="Skip cells already complete")
    parser.add_argument("--force", action="store_true",
                        help="Re-run cells even if complete (overwrites results.json)")
    args = parser.parse_args()

    arms = [a for a in ALL_ARMS if a in args.arms]  # canonical order
    output_root = Path(args.output_root)

    print("=" * 82)
    print("Authority-Framing Ablation (Experiment 7a) - runner")
    print("=" * 82)
    print(f"  models : {', '.join(args.models)}")
    print(f"  arms   : {', '.join(arms)}")
    print(f"  judge  : {JUDGE_MODEL} (held fixed for comparability)")
    print(f"  output : {output_root}")

    for arm in arms:
        try:
            shape = arm_shape(arm)
        except FileNotFoundError as exc:
            print(f"  [FAIL] {exc}")
            return 1
        if shape["n"] == 0:
            print(f"  [FAIL] {arm} bundle contains no text scenarios")
            return 1

    print_estimate(args.models, arms)

    if args.dry_run:
        print("[dry-run] no API calls made.")
        return 0

    if not (os.getenv("OPENROUTER_API_KEY") or os.getenv("API_KEY")):
        print("[FAIL] OPENROUTER_API_KEY not set (.env or environment).")
        return 1

    output_root.mkdir(parents=True, exist_ok=True)
    manifest_path = output_root / "run_manifest.json"
    manifest: Dict[str, Any] = {
        "experiment": "authority_framing_ablation_7a",
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "models": {s: MODELS[s]["openrouter_id"] for s in args.models},
        "arms": {a: ARM_LABELS[a] for a in arms},
        "judge_model": JUDGE_MODEL,
        "parallel_workers": args.parallel,
        "cells": [],
    }

    skipped, ran, failed = 0, 0, 0
    for model_slug in args.models:
        for arm in arms:
            n_expected = int(arm_shape(arm)["n"])
            paths = cell_paths(output_root, model_slug, arm)

            if not args.force and cell_is_complete(paths, n_expected):
                print(f"\n[skip] {model_slug}/{arm} already complete ({n_expected}/{n_expected})"
                      + ("" if args.resume else "; use --force to re-run"))
                skipped += 1
                continue

            try:
                manifest["cells"].append(run_cell(
                    model_slug=model_slug, arm=arm, output_root=output_root,
                    parallel=args.parallel, delay=args.delay,
                    max_retries=args.max_retries, retry_delay=args.retry_delay,
                    timeout=args.timeout,
                ))
                ran += 1
            except KeyboardInterrupt:
                print("\n[interrupted] partial results are on disk; re-run with --resume")
                manifest["interrupted_utc"] = datetime.now(timezone.utc).isoformat()
                with open(manifest_path, "w", encoding="utf-8") as fh:
                    json.dump(manifest, fh, indent=2)
                return 130
            except Exception as exc:  # one bad cell must not kill the run
                print(f"\n[FAIL] cell {model_slug}/{arm}: {exc}")
                manifest["cells"].append({"model_slug": model_slug, "arm": arm, "error": str(exc)})
                failed += 1
            time.sleep(2)

    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest.update({"cells_ran": ran, "cells_skipped": skipped, "cells_failed": failed})
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)

    print("\n" + "=" * 82)
    print(f"Run complete: {ran} cell(s) run, {skipped} skipped, {failed} failed")
    print(f"Manifest: {manifest_path}")
    print("Next: python analyze_authority_ablation.py")
    print("=" * 82)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
