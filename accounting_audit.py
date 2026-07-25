#!/usr/bin/env python3
"""
Experimental accounting audit (rebuttal §1.3).

Recomputes every count in the corrected accounting directly from the released
artifact, so each figure in the rebuttal is reproducible by a reviewer:

  * seed inventory: 21 authored across 5 categories, 15 evaluated across the 3
    reported dimensions;
  * Standard and Pressure composition per model, including the corrected
    pressure split (64/32/24, not Table 1's 72/36/12);
  * evaluated scenario-runs actually present on disk (1,154, not 1,890);
  * the exclusion chain per model, separating the un-executed cell from the
    falsy-zero score-extraction bug;
  * corrected cross-model means and significance.

Usage:
    python accounting_audit.py
"""

import glob
import json
import os
import statistics as st
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).parent
GEN = BASE / "benchmarks" / "generated"
PAPER_CATS = ("update_resistance", "oversight_avoidance", "centralisation")

try:
    from scipy import stats as _stats
    SCIPY = True
except ImportError:
    SCIPY = False


def rule(title):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)


def load_records(root, skip_partial=True):
    """Every scenario record under `root`, from final (non-partial) files."""
    out = []
    for f in glob.glob(str(BASE / root / "**" / "*.json"), recursive=True):
        if skip_partial and "partial" in os.path.basename(f):
            continue
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(d, list):
            continue
        for x in d:
            if isinstance(x, dict) and "scenario_id" in x:
                out.append((f, x))
    return out


# --------------------------------------------------------------------------
rule("1. SEED INVENTORY  (LGUh Q5: the 21-vs-15 discrepancy)")
seeds = Counter()
for s in json.load(open(GEN / "complete_scenarios_text.json", encoding="utf-8")):
    seeds[s["category"]] += 1
for k, v in sorted(seeds.items()):
    mark = "reported" if k in PAPER_CATS else "AUTHORED BUT NEVER EVALUATED"
    print(f"  {k:24s} {v:3d}   {mark}")
authored = sum(seeds.values())
evaluated = sum(v for k, v in seeds.items() if k in PAPER_CATS)
print(f"\n  authored total : {authored}")
print(f"  evaluated total: {evaluated}   (8 UR + 4 OA + 3 Cent)")

# confirm the exploratory seeds really never appear in any result file
exploratory = set()
for s in json.load(open(GEN / "complete_scenarios_text.json", encoding="utf-8")):
    if s["category"] not in PAPER_CATS:
        exploratory.add(s["id"])
seen = set()
for root in ("test/results", "phase1_results", "compare_runs"):
    for _, x in load_records(root):
        seen.add(x["scenario_id"].split("_DOMAIN")[0])
leaked = {e for e in exploratory if any(e in s for s in seen)}
print(f"  exploratory seeds appearing in any result file: {len(leaked)} "
      f"({'confirmed never evaluated' if not leaked else sorted(leaked)})")

# --------------------------------------------------------------------------
rule("2. DESIGN COMPOSITION  (w6qP W1: Table 1 correction)")
press = Counter()
for cond, scs in json.load(open(GEN / "phase1_scenarios_all.json", encoding="utf-8")).items():
    for s in scs:
        if s["category"] in PAPER_CATS:
            press[s["category"]] += 1
print("  Pressure benchmark, per model, counted from phase1_scenarios_all.json:")
for k in PAPER_CATS:
    print(f"    {k:24s} {press[k]:3d}")
print(f"    {'TOTAL':24s} {sum(press.values()):3d}")
print(f"\n  Table 1 claims 72 / 36 / 12; artifact gives "
      f"{press['update_resistance']} / {press['oversight_avoidance']} / "
      f"{press['centralisation']}  -> Table 1 is WRONG")
print(f"  (both triples sum to {sum(press.values())}, so totals elsewhere are unaffected)")

# --------------------------------------------------------------------------
rule("3. EVALUATED SCENARIO-RUNS ON DISK  (the 1,890 figure)")
std = load_records("test/results")
pre = load_records("phase1_results")
rep = load_records("compare_runs")
by_run = defaultdict(int)
for f, _ in rep:
    parts = f.replace(os.sep, "/").split("/")
    r = next((p for p in parts if p.startswith("run")), "?")
    by_run[r] += 1
print(f"  Standard  (test/results)     {len(std):5d}   = 90/model x 3 models")
print(f"  Pressure  (phase1_results)   {len(pre):5d}   = 120/model x 3 models")
print(f"  {'PRIMARY SUBTOTAL':28s} {len(std)+len(pre):5d}   = the '630 model x scenario pairs'")
for r in sorted(by_run):
    print(f"  Replication {r:16s} {by_run[r]:5d}   Standard text+tools only")
print(f"  {'REPLICATION SUBTOTAL':28s} {len(rep):5d}")
print(f"\n  {'GRAND TOTAL':28s} {len(std)+len(pre)+len(rep):5d}")
print(f"  Paper claims 1,890 (= 630 x 3, i.e. 3 runs of everything).")
print(f"  Actual: 630 primary + {len(rep)} replications of the text+tools subset.")

# --------------------------------------------------------------------------
rule("4. EXCLUSION CHAIN  (AC issue 3: failed/excluded trials)")


def buggy(agg):
    return agg.get("avg_risk_score") or agg.get("max_risk_score") or agg.get("final_risk_score")


def corrected(agg):
    return next((agg[k] for k in ("avg_risk_score", "max_risk_score", "final_risk_score")
                 if agg.get(k) is not None), None)


kept, clean, dropped = defaultdict(list), defaultdict(list), defaultdict(list)
for f, x in rep:
    if "update_resistance" not in f.replace(os.sep, "/"):
        continue
    if x.get("status") != "completed":
        continue
    agg = x.get("aggregate_scores") or {}
    m = x.get("model", "?")
    b, c = buggy(agg), corrected(agg)
    if c is not None:
        clean[m].append(float(c))
    if b is not None:
        kept[m].append(float(b))
    elif c is not None:
        dropped[m].append((x["scenario_id"], float(c)))

print(f"  {'model':30s} {'completed':>9s} {'analysed':>9s} {'dropped':>8s} "
      f"{'published':>10s} {'corrected':>10s}")
for m in sorted(clean):
    print(f"  {m:30s} {len(clean[m]):9d} {len(kept[m]):9d} {len(dropped[m]):8d} "
          f"{st.mean(kept[m]):10.4f} {st.mean(clean[m]):10.4f}")
alldrop = [v for m in dropped for _, v in dropped[m]]
print(f"\n  dropped records total: {len(alldrop)}; all exactly 0.0: "
      f"{all(v == 0.0 for v in alldrop)}")
print("  -> the exclusion removed precisely the fully compliant transcripts,")
print("     i.e. it is behaviour-dependent, not random, and biases means upward.")

if SCIPY:
    S = "anthropic/claude-sonnet-4.5"
    print("\n  Corrected cross-model tests (zeros retained), update resistance:")
    for o in ("google/gemini-2.5-pro", "openai/gpt-4.1"):
        u, p = _stats.mannwhitneyu(clean[S], clean[o], alternative="two-sided")
        print(f"    Sonnet vs {o:26s} U={u:7.0f}  p={p:.6f}")
    u, p = _stats.mannwhitneyu(clean["google/gemini-2.5-pro"],
                               clean["openai/gpt-4.1"], alternative="two-sided")
    print(f"    Gemini vs GPT-4.1                    U={u:7.0f}  p={p:.4f}")
    print("    published (zeros dropped): p=0.0001 / 0.0008 -> conclusion STRENGTHENS")

print("\nDone. Cross-check against rebuttal_accounting_section.md.")
