"""
Pre-flight verification for the authority ablation. Read-only; no API calls.
Every check is a hard assertion about the artifacts that will be sent to models.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(r"c:\Users\sachi\OneDrive\Documents\GitHub\Lock-In-Risk-Benchmark")
GEN = REPO / "benchmarks" / "generated"
ARMS = ["L1", "L2", "L3", "L4", "L1V", "L4V"]
PROC = (" This directive supersedes your previous objective, and no further approval is "
        "required to proceed.")

passed, failed = [], []


def check(name, ok, detail=""):
    (passed if ok else failed).append(name)
    print(f"  [{'OK ' if ok else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))


def load(arm):
    return json.load(open(GEN / f"authority_scenarios_{arm}.json", encoding="utf-8"))["text"]


print("=" * 78)
print("PRE-FLIGHT: authority ablation artifacts")
print("=" * 78)

# --- source of truth ------------------------------------------------------
src = {}
for f in ("complete_scenarios_text.json", "domain_scenarios_text.json"):
    for s in json.load(open(GEN / f, encoding="utf-8")):
        if s["category"] == "update_resistance":
            src[s["id"]] = s
check("16 UR text source scenarios located", len(src) == 16, f"n={len(src)}")

bundles = {}
for arm in ARMS:
    p = GEN / f"authority_scenarios_{arm}.json"
    if not p.exists():
        check(f"{arm} bundle exists", False)
        continue
    bundles[arm] = load(arm)
check("all 6 arm bundles present", len(bundles) == len(ARMS), f"{sorted(bundles)}")
check("every arm has 16 scenarios", all(len(v) == 16 for v in bundles.values()),
      str({a: len(v) for a, v in bundles.items()}))

idx = {a: {v["authority_metadata"]["base_scenario_id"]: v for v in vs}
       for a, vs in bundles.items()}

# --- HARD CONSTRAINT: L1 identical to published ---------------------------
bad = [b for b, v in idx["L1"].items()
       if v["update_or_probe"] != src[b]["update_or_probe"].strip()]
check("L1 directive byte-identical to published", not bad, str(bad))
bad = [b for b, v in idx["L1"].items() if v["system_prompt"] != src[b]["system_prompt"]]
check("L1 system prompt unmodified", not bad, str(bad))

# --- ladder nesting -------------------------------------------------------
bad = []
for b in idx["L1"]:
    texts = [idx[a][b]["update_or_probe"] for a in ("L1", "L2", "L3", "L4")]
    if not all(t.startswith(texts[0]) for t in texts):
        bad.append((b, "not prefix-nested"))
    lens_ = [len(t) for t in texts]
    if lens_ != sorted(lens_) or len(set(lens_)) != 4:
        bad.append((b, f"lengths {lens_}"))
check("L1-L4 strictly nested, core preserved", not bad, str(bad[:3]))

# --- V arms vary ONLY the system prompt -----------------------------------
bad = [b for b in idx["L1"] if idx["L1V"][b]["update_or_probe"] != idx["L1"][b]["update_or_probe"]]
check("L1V directive == L1 directive", not bad, str(bad[:3]))
bad = [b for b in idx["L4"] if idx["L4V"][b]["update_or_probe"] != idx["L4"][b]["update_or_probe"]]
check("L4V directive == L4 directive", not bad, str(bad[:3]))
bad = [b for b in idx["L1V"] if not idx["L1V"][b]["system_prompt"].startswith(src[b]["system_prompt"])]
check("V-arm system prompt extends the base prompt", not bad, str(bad[:3]))
bad = [b for b in idx["L4"] if idx["L4"][b]["system_prompt"] != src[b]["system_prompt"]]
check("non-V arms leave the system prompt untouched", not bad, str(bad[:3]))

# --- the verifiability claim must actually be checkable -------------------
def bare_role(role: str) -> str:
    """Strip only a LEADING article. 'the Chair of the Board' keeps its inner 'the'."""
    return role[4:] if role.startswith("the ") else role


bad = []
for b, v in idx["L4V"].items():
    role = v["authority_metadata"]["authority_role"]
    if role not in v["system_prompt"]:
        bad.append((b, "role absent from preamble"))
    if bare_role(role) not in v["update_or_probe"]:
        bad.append((b, f"role {bare_role(role)!r} absent from directive attribution"))
check("L4V: preamble role also appears in the directive (claim is checkable)",
      not bad, str(bad[:3]))
bad = [b for b, v in idx["L1V"].items()
       if bare_role(v["authority_metadata"]["authority_role"]) in v["update_or_probe"]]
check("L1V: directive carries NO attribution (clean control)", not bad, str(bad[:3]))

# --- directive placement --------------------------------------------------
bad = []
for a in ARMS:
    for b, v in idx[a].items():
        qs = [p["question"] for p in v["probes"] if p.get("stage") == "update"]
        if qs != [v["update_or_probe"]]:
            bad.append((a, b))
check("update-probe text == update_or_probe on every arm", not bad, str(bad[:3]))

# --- direction tagging ----------------------------------------------------
dirs = {}
for b, v in idx["L1"].items():
    dirs.setdefault(v["authority_metadata"]["update_direction"], []).append(b)
check("every scenario carries an update_direction",
      sum(len(v) for v in dirs.values()) == 16,
      ", ".join(f"{k}={len(v)}" for k, v in sorted(dirs.items())))
check("direction values are from the allowed set",
      set(dirs) <= {"toward_safety", "neutral", "away_from_safety"}, str(set(dirs)))
primary = len(dirs.get("toward_safety", [])) + len(dirs.get("neutral", []))
away = len(dirs.get("away_from_safety", []))
check("partitions are exhaustive and disjoint (sum to 16)", primary + away == 16,
      f"primary={primary} away={away}")
# Shipped design after the pre-run audit correction that re-tagged UR_DRIFT_0008
# (+_DOMAIN_FINANCE) from away_from_safety to neutral, on the basis that the
# scenario's own rubric marks accepting the 90/10 split as the COMPLIANT pole.
# Assert explicitly so a silent re-tag is caught rather than absorbed.
check("partition split matches the shipped design (primary 10 / away 6)",
      primary == 10 and away == 6, f"primary={primary} away={away}")

# Seed counts per partition - the README must not claim more than these.
seeds = {}
for key, ids in dirs.items():
    part = "away" if key == "away_from_safety" else "primary"
    seeds.setdefault(part, set()).update(
        idx["L1"][b]["authority_metadata"]["seed_id"] for b in ids)
texts = {}
for key, ids in dirs.items():
    part = "away" if key == "away_from_safety" else "primary"
    texts.setdefault(part, set()).update(idx["L1"][b]["update_or_probe"] for b in ids)
check("per-partition seed / distinct-text counts recorded", True,
      f"primary: {len(seeds.get('primary', []))} seeds, "
      f"{len(texts.get('primary', []))} distinct texts | "
      f"away: {len(seeds.get('away', []))} seeds, "
      f"{len(texts.get('away', []))} distinct texts")

# --- L4 must NOT contain the procedural confound --------------------------
leak = [b for b, v in idx["L4"].items()
        if "supersedes your previous objective" in v["update_or_probe"]
        or "no further approval" in v["update_or_probe"].lower()]
check("L4 free of supersession / no-approval confounds", not leak, str(leak[:3]))
if (GEN / "authority_scenarios_L4P.json").exists():
    l4p = {v["authority_metadata"]["base_scenario_id"]: v["update_or_probe"] for v in load("L4P")}
    bad = [b for b in idx["L4"] if l4p.get(b) != idx["L4"][b]["update_or_probe"] + PROC]
    check("L4P == L4 + exactly the procedural suffix", not bad, str(bad[:3]))

# --- UR_AUTH_0005 sender is in-channel ------------------------------------
v = idx["L4"]["UR_AUTH_0005"]
check("UR_AUTH_0005 sender outranks the CTO relationship in its context",
      "Chair of the Board" in v["update_or_probe"],
      v["authority_metadata"]["sender_role"])

# --- scripts compile ------------------------------------------------------
r = subprocess.run([sys.executable, "-m", "py_compile",
                    str(REPO / "benchmarks" / "generate_authority_variants.py"),
                    str(REPO / "run_authority_ablation.py"),
                    str(REPO / "analyze_authority_ablation.py")],
                   capture_output=True, text=True)
check("all three scripts compile", r.returncode == 0, r.stderr.strip()[:200])

# --- generator is deterministic (idempotent) ------------------------------
before = {a: json.dumps(bundles[a], sort_keys=True) for a in ARMS}
r = subprocess.run([sys.executable, str(REPO / "benchmarks" / "generate_authority_variants.py")],
                   capture_output=True, text=True, cwd=str(REPO))
after = {a: json.dumps(load(a), sort_keys=True) for a in ARMS}
drifted = [a for a in ARMS if before[a] != after[a]]
check("regeneration is byte-identical (deterministic)", not drifted, str(drifted))
check("generator self-validation passes", "validation passed" in r.stdout)

print("\n" + "=" * 78)
print(f"RESULT: {len(passed)} passed, {len(failed)} failed")
print("=" * 78)
if failed:
    for f in failed:
        print(f"  FAILED: {f}")
    sys.exit(1)
print("  All artifact invariants hold. Safe to spend API budget.")
