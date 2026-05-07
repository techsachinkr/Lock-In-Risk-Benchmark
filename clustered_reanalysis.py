"""
Clustered reanalysis: aggregate to base-scenario level, then rerun
Mann-Whitney U tests and fit mixed-effects models.

Addresses the reviewer concern that 210 scenarios per model are not
independent (they derive from 15 base scenarios).

Two analyses:
  1. Clustered Mann-Whitney U: average all variants of the same base
     scenario into one observation per (base, model), then test.
  2. Mixed-effects LMM: score ~ model_indicator + (1 | base_scenario)
     using the full raw scores.

Scope: all three categories separately, plus combined.
Data: standard benchmark (test/results/) + pressure benchmark (phase1_results/).
"""

import json, glob, re, sys
from collections import defaultdict
import numpy as np
from scipy import stats
import statsmodels.formula.api as smf
import pandas as pd
import warnings
warnings.filterwarnings("ignore")

# ── helpers ──────────────────────────────────────────────────────────────────

MODALITY_PREFIX = re.compile(r'^(UR|OVS|CENT|COMM|ENC)_(TOOLS|SANDBOX)_')
DOMAIN_SUFFIX   = re.compile(r'_DOMAIN_\w+$')
PRESSURE_SUFFIX = re.compile(r'_(TIME_PRESSURE|SOFT_INTERVENTION|HARD_INTERVENTION|'
                              r'CONSTITUTIONAL|STAKEHOLDER_PRESSURE|LOW_INFO|'
                              r'MEDIUM_INFO|CONFLICTING_INFO)$')

def base_id(scenario_id):
    """Strip modality/domain/pressure suffixes to get canonical base ID."""
    s = scenario_id
    # tools/sandbox prefix: UR_TOOLS_GOAL_0001 → UR_GOAL_0001
    s = MODALITY_PREFIX.sub(lambda m: m.group(1) + '_', s)
    s = DOMAIN_SUFFIX.sub('', s)
    s = PRESSURE_SUFFIX.sub('', s)
    return s

def get_score_from_result(result_record):
    """Extract composite risk score from a single result record."""
    meta = result_record.get('metadata', {})
    if isinstance(meta, dict):
        cs = meta.get('composite_score')
        if cs is not None:
            return float(cs)
    score_str = str(result_record.get('score', ''))
    m = re.search(r'value=([0-9]+\.?[0-9]*)', score_str)
    if m:
        return float(m.group(1))
    return None

def get_score_from_scenario(sc):
    """Get score from a scenario dict (standard or phase1 format)."""
    # Standard benchmark format: aggregate_scores at top level
    agg = sc.get('aggregate_scores', {})
    if isinstance(agg, dict):
        s = agg.get('max_risk_score')
        if s is not None and float(s) > 0:
            return float(s)
        # accept 0.0 only if it's explicitly set (not missing)
        if 'max_risk_score' in agg:
            return float(agg['max_risk_score'])
    # Phase1 format: result list with score strings
    for r in sc.get('result', []):
        if not isinstance(r, dict):
            continue
        s = get_score_from_result(r)
        if s is not None:
            return s
    return None

# ── load data ────────────────────────────────────────────────────────────────

MODEL_DIRS = {
    'Gemini 2.5 Pro': 'gemini_25_pro',
    'GPT-4.1':        'gpt_41',
    'Sonnet 4.5':     'sonnet_45',
}
CATS = ['update_resistance', 'oversight_avoidance', 'centralisation']
PAPER_CATS = {   # base-scenario IDs that belong to paper-benchmark
    'update_resistance':  {'UR_GOAL_0001','UR_GOAL_0002','UR_CONTRA_0003',
                           'UR_PRIORITY_0004','UR_AUTH_0005','UR_CONSTRAINT_0006',
                           'UR_VALUE_0007','UR_DRIFT_0008'},
    'oversight_avoidance':{'OVS_HIDE_0018','OVS_REPORT_0019',
                           'OVS_AUTO_0020','OVS_MONITOR_0021'},
    'centralisation':     {'CENT_POWER_0009','CENT_INFLU_0010','CENT_ACCESS_0011'},
}

rows = []  # each row: model, category, base_scenario_id, variant_label, score, benchmark

for model_name, model_dir in MODEL_DIRS.items():

    # --- standard benchmark ---
    for cat in CATS:
        result_files = glob.glob(f'test/results/{cat}/{model_dir}/**/*_results.json',
                                 recursive=True)
        result_files = [f for f in result_files if 'partial' not in f]
        for rf in result_files:
            with open(rf) as fh:
                data = json.load(fh)
            # infer variant label from path (text/tools/sandbox, complete_all/domain)
            path_parts = rf.replace('\\', '/').split('/')
            mod_part   = path_parts[-2]        # text / tools / sandbox
            scope_part = path_parts[-3]        # complete_all / domain / run1 …
            variant_label = f'{scope_part}_{mod_part}'
            for sc in data:
                sid   = sc.get('scenario_id', '')
                bid   = base_id(sid)
                score = get_score_from_scenario(sc)
                if score is not None and bid in PAPER_CATS[cat]:
                    rows.append(dict(model=model_name, category=cat,
                                     base=bid, variant=variant_label,
                                     score=score, benchmark='standard'))

    # --- pressure benchmark ---
    for cat in CATS:
        result_files = glob.glob(f'phase1_results/{model_dir}/{cat}/*_results.json')
        result_files = [f for f in result_files if 'partial' not in f]
        for rf in result_files:
            with open(rf) as fh:
                data = json.load(fh)
            for sc in data:
                sid   = sc.get('scenario_id', '')
                bid   = base_id(sid)
                score = get_score_from_scenario(sc)
                if score is not None and bid in PAPER_CATS[cat]:
                    rows.append(dict(model=model_name, category=cat,
                                     base=bid, variant=sid,  # full ID = unique variant
                                     score=score, benchmark='pressure'))

df = pd.DataFrame(rows)
print(f"Total raw observations loaded: {len(df)}")
print(df.groupby(['model','category','benchmark'])['score'].count().to_string())

# ── Analysis 1: Clustered Mann-Whitney U ─────────────────────────────────────

def mwu(a, b, label_a, label_b):
    """Two-sided Mann-Whitney U with rank-biserial r effect size."""
    if len(a) < 2 or len(b) < 2:
        return dict(n_a=len(a), n_b=len(b), U=None, p=None, r=None)
    U, p = stats.mannwhitneyu(a, b, alternative='two-sided')
    # rank-biserial r = 1 - 2U/(n_a*n_b)
    r = 1 - 2*U / (len(a)*len(b))
    return dict(n_a=len(a), n_b=len(b), U=round(U,1), p=round(p,4), r=round(abs(r),3))

print("\n" + "="*80)
print("ANALYSIS 1: CLUSTERED MANN-WHITNEY U")
print("  Scores averaged over all variants of the same base scenario.")
print("  Unit of analysis: base scenario (n = 8, 4, or 3 per category).")
print("="*80)

# aggregate: mean score per (model, category, base_scenario)
clustered = (df.groupby(['model','category','base'])['score']
               .mean()
               .reset_index()
               .rename(columns={'score':'mean_score'}))

print(f"\nClustered observations: {len(clustered)}")

PAIRS = [
    ('Sonnet 4.5',   'Gemini 2.5 Pro'),
    ('Sonnet 4.5',   'GPT-4.1'),
    ('Gemini 2.5 Pro','GPT-4.1'),
]

for cat in CATS:
    sub = clustered[clustered.category == cat]
    n_base = sub['base'].nunique()
    print(f"\n--- {cat.upper()} (n_base={n_base}) ---")
    for m in MODEL_DIRS:
        vals = sub[sub.model==m]['mean_score'].values
        print(f"  {m}: n={len(vals)}, mean={vals.mean():.3f}, "
              f"min={vals.min():.3f}, max={vals.max():.3f}")
    print()
    for a, b in PAIRS:
        va = sub[sub.model==a]['mean_score'].values
        vb = sub[sub.model==b]['mean_score'].values
        res = mwu(va, vb, a, b)
        sig = ('***' if res['p'] is not None and res['p'] < 0.001 else
               '**'  if res['p'] is not None and res['p'] < 0.01  else
               '*'   if res['p'] is not None and res['p'] < 0.05  else
               'ns'  if res['p'] is not None else 'N/A')
        print(f"  {a} vs {b}: "
              f"n=({res['n_a']},{res['n_b']}), "
              f"U={res['U']}, p={res['p']}, r={res['r']}  {sig}")

# Also: within-model dimension comparisons for Sonnet (UR vs Cent, UR vs OA)
print("\n--- SONNET: cross-dimension (clustered) ---")
for cat_a, cat_b in [('update_resistance','centralisation'),
                      ('update_resistance','oversight_avoidance')]:
    va = clustered[(clustered.model=='Sonnet 4.5') & (clustered.category==cat_a)]['mean_score'].values
    vb = clustered[(clustered.model=='Sonnet 4.5') & (clustered.category==cat_b)]['mean_score'].values
    res = mwu(va, vb, cat_a, cat_b)
    sig = ('***' if res['p'] is not None and res['p'] < 0.001 else
           '**'  if res['p'] is not None and res['p'] < 0.01  else
           '*'   if res['p'] is not None and res['p'] < 0.05  else
           'ns'  if res['p'] is not None else 'N/A')
    print(f"  {cat_a} vs {cat_b}: "
          f"n=({res['n_a']},{res['n_b']}), U={res['U']}, p={res['p']}, r={res['r']}  {sig}")

# ── Analysis 1b: separate standard vs pressure ──────────────────────────────

print("\n--- CLUSTERED MWU BY BENCHMARK (UR only) ---")
for bench in ['standard', 'pressure']:
    sub_bench = df[df.benchmark==bench]
    cl = (sub_bench.groupby(['model','category','base'])['score']
                   .mean().reset_index())
    sub = cl[cl.category=='update_resistance']
    print(f"\n  Benchmark: {bench}")
    for a, b in [('Sonnet 4.5','Gemini 2.5 Pro'),('Sonnet 4.5','GPT-4.1')]:
        va = sub[sub.model==a]['score'].values
        vb = sub[sub.model==b]['score'].values
        res = mwu(va, vb, a, b)
        sig = ('*' if res['p'] is not None and res['p']<0.05 else
               'ns' if res['p'] is not None else 'N/A')
        print(f"    {a} vs {b}: n=({res['n_a']},{res['n_b']}), "
              f"p={res['p']}, r={res['r']}  {sig}")

# ── Analysis 2: Mixed-Effects Linear Model ───────────────────────────────────

print("\n" + "="*80)
print("ANALYSIS 2: MIXED-EFFECTS LMM")
print("  score ~ model + (1 | base_scenario_id)  [base scenario = random effect]")
print("  Reference model: GPT-4.1")
print("="*80)

for cat in CATS:
    sub = df[df.category == cat].copy()
    sub['model_c'] = pd.Categorical(sub['model'],
                                     categories=['GPT-4.1','Gemini 2.5 Pro','Sonnet 4.5'])
    n_base = sub['base'].nunique()
    n_obs  = len(sub)
    print(f"\n--- {cat.upper()} (n_base={n_base}, n_obs={n_obs}) ---")
    try:
        md = smf.mixedlm("score ~ C(model_c)", sub, groups=sub['base'])
        mdf = md.fit(reml=True, method='lbfgs')
        print(mdf.summary().tables[1].to_string())
        # ICC
        re_var  = float(mdf.cov_re.iloc[0,0])
        res_var = float(mdf.scale)
        icc = re_var / (re_var + res_var)
        print(f"  Random-effect variance (base): {re_var:.4f}")
        print(f"  Residual variance:             {res_var:.4f}")
        print(f"  ICC (base scenario):           {icc:.3f}")
    except Exception as e:
        print(f"  Model failed: {e}")

# ── Summary table ─────────────────────────────────────────────────────────────

print("\n" + "="*80)
print("SUMMARY: ORIGINAL (scenario-level) vs CLUSTERED (base-level) p-values")
print("="*80)

# Original pooled scenario-level MWU (replicate from variance_analysis_report.txt)
ORIG = {
    ('update_resistance',   'Sonnet 4.5', 'Gemini 2.5 Pro'): 0.0001,
    ('update_resistance',   'Sonnet 4.5', 'GPT-4.1'):        0.0008,
    ('update_resistance',   'Gemini 2.5 Pro', 'GPT-4.1'):    0.7332,
    ('centralisation',      'Sonnet 4.5', 'Gemini 2.5 Pro'): 0.1200,
    ('centralisation',      'Sonnet 4.5', 'GPT-4.1'):        0.5429,
    ('centralisation',      'Gemini 2.5 Pro','GPT-4.1'):     0.2528,
    ('oversight_avoidance', 'Sonnet 4.5', 'Gemini 2.5 Pro'): 0.5926,
    ('oversight_avoidance', 'Sonnet 4.5', 'GPT-4.1'):        0.0904,
    ('oversight_avoidance', 'Gemini 2.5 Pro','GPT-4.1'):     0.2194,
}

print(f"\n{'Category':<22} {'Comparison':<40} {'Original p':>10} {'Clustered p':>11} {'Change':>10}")
print("-"*98)
for cat in CATS:
    sub = clustered[clustered.category == cat]
    for a, b in PAIRS:
        va = sub[sub.model==a]['mean_score'].values
        vb = sub[sub.model==b]['mean_score'].values
        res = mwu(va, vb, a, b)
        orig_p = ORIG.get((cat, a, b), ORIG.get((cat, b, a)))
        cl_p   = res['p']
        if cl_p is not None and orig_p is not None:
            direction = ('same direction' if (cl_p < 0.05) == (orig_p < 0.05)
                         else '** SIGN. CHANGES **')
        else:
            direction = 'N/A'
        print(f"{cat:<22} {a+' vs '+b:<40} {str(orig_p):>10} {str(cl_p):>11} {direction:>10}")
