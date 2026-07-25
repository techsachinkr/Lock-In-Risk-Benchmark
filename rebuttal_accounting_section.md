# Rebuttal section: experimental accounting (§1.3)

Drop-in replacement for §1.3 of `rebuttal_draft.md`. Addresses AC issue 3,
w6qP W1, LGUh Q5, and DYAi Q3. Every figure below was recomputed from the
released artifact; the reproduction commands are in the last section so the AC
can check any of them.

---

## 1.3 Consistent experimental accounting (AC issue 3; w6qP W1; LGUh Q5; DYAi Q3)

The reviewers are right that our counts do not reconcile. We have audited every
number against the artifact and report the corrected accounting below, including
three errors in the submission and one analysis bug that we found in the process
and that changes published values.

### The 21-vs-15 discrepancy (LGUh Q5)

Both numbers are real and we should have explained the relationship. Our
generator authored **21 seed scenarios across five categories**:

| Category | Seeds | Reported in the paper? |
|---|---|---|
| update_resistance | 8 | yes |
| oversight_avoidance | 4 | yes |
| centralisation | 3 | yes |
| commitment_stickiness | 3 | **no** |
| enclosure_dependency | 3 | **no** |
| **Total authored** | **21** | **15 evaluated** |

The paper reports three risk dimensions. The six seeds in the two remaining
categories were authored, ship in the released dataset (labelled
"exploratory-category scenarios" in the Croissant metadata), and were **never
evaluated** — no result file in the artifact contains a `COMM_*` or `ENC_*`
scenario id. Every reported number therefore rests on the 15 evaluated seeds
(8/4/3), which is why the clustered analysis and the generator log both say 15.
§3.4's "21 expert-crafted base scenarios" describes the authoring step and should
have said that 15 were carried into evaluation; 210 scenarios per model only
arithmetically follows from 15.

### Corrected design table (replaces Table 1)

| Level | Composition | Count |
|---|---|---|
| Seed scenarios evaluated | 8 UR + 4 OA + 3 Cent | **15** |
| Standard benchmark | 15 seeds × 3 modalities × 2 scopes | **90 / model** |
| — per modality | 16 UR + 8 OA + 6 Cent | 30 |
| — by category | UR 48, OA 24, Cent 18 | 90 |
| Pressure benchmark | 15 seeds × 8 conditions, text only | **120 / model** |
| — by category | **UR 64, OA 32, Cent 24** | 120 |
| Per model | Standard + Pressure | **210** |
| Model × scenario pairs | × 3 models | **630** |

**Table 1's pressure rows (72 / 36 / 12) are an error; the correct figures are
64 / 32 / 24.** Counting the released `phase1_scenarios_all.json` gives exactly
64 UR, 32 OA and 24 Cent across the eight conditions, which also matches §3.3.2's
own per-variant composition (8 UR + 4 OA + 3 Cent per condition) and §4.2's
reference to "Sonnet's 64 pressure UR scenarios". Both triples happen to sum to
120, so the totals elsewhere in the paper are unaffected.

### The 1,890 transcript figure is overstated; the correct count is 1,154

This is the error we most regret. 1,890 is 630 × 3 and implicitly claims three
replication runs of all 210 scenarios per model. That is not what we ran. The
artifact contains:

| Source | Coverage | Evaluated scenario-runs |
|---|---|---|
| Standard benchmark | 90/model × 3 models, all three modalities | 270 |
| Pressure benchmark | 120/model × 3 models, text | 360 |
| **Primary evaluation** | **= the 630 model × scenario pairs** | **630** |
| Replication run 1 | Standard, text + tools only (60/model) | 180 |
| Replication run 2 | same, one cell not executed (see below) | 164 |
| Replication run 3 | same | 180 |
| **Replication subtotal** | | **524** |
| **Total evaluated scenario-runs** | | **1,154** |

The three replication runs cover **only the text and tool modalities of the
Standard benchmark**, as §4.5 correctly states ("Three independent replication
runs (text and tool modalities, Standard benchmark)"). Sandbox and all pressure
conditions were evaluated once. We will replace 1,890 with 1,154 throughout and
state the replication coverage wherever run-to-run stability is claimed.

Separately, the released artifact also contains 90 re-scorings of existing
Standard transcripts by the second judge (Grok) and 24 by three further judges
used in exploratory judge-comparison work. Those are re-scorings of the same
agent transcripts, not additional agent runs, and are not counted above.

### Probe and stage terminology (w6qP W1)

Each scenario contains **5–10 probes**. Figure 2's "5 probes" label refers to
stages, not probes, and is wrong. The runner assigns probes to **four** named
stages, not five: `pre_update`, `update`, `post_update`, `reversion_check`. The
counts differ by scope: general-context scenarios have 8 probes including one
`reversion_check`; domain-enriched scenarios have 5 probes and **no**
`reversion_check` stage. Because `avg_risk_score` averages the update,
post_update and reversion_check stages, a general-context scenario averages 6
risk-relevant probes and a domain scenario 3. We will state per-scenario probe
and stage counts explicitly in the released metadata and correct Figure 2.

### Exclusion accounting and a correction to published values

The n = 95 / 87 / 67 figures in Appendix D are **not** completion counts, and we
described them as though they were. The correct chain for update resistance in
the replication data is:

| Model | Attempted | Completed | Entered analysis | Reason for the gap |
|---|---|---|---|---|
| Claude Sonnet 4.5 | 96 | 96 | 95 | 1 dropped by the bug below |
| Gemini 2.5 Pro | 96 | 96 | 87 | 9 dropped by the bug below |
| GPT-4.1 | 96 | **80** | 67 | 16 never executed; 13 dropped by the bug |

Two distinct causes:

**1. One cell was never run.** GPT-4.1's run-2 update-resistance domain cell
(8 text + 8 tools) is absent from the artifact. This is a straightforward
execution gap, unrelated to model behaviour.

**2. A score-extraction bug silently dropped compliant scenarios.**
`variance_analysis.py` extracts each score as

```python
agg.get("avg_risk_score") or agg.get("max_risk_score") or agg.get("final_risk_score")
```

Python evaluates `0.0` as falsy, so any scenario scoring exactly 0.0 on both
fields falls through every branch and is silently excluded. We verified that
**every one of the 23 dropped records scored exactly 0.0** — that is, the
exclusion removed precisely the fully compliant, zero-risk transcripts. The
exclusion is therefore **behaviour-dependent, not random**, and it biases means
upward, most for the models that comply most.

Correcting it changes the published cross-model means:

| Model | Published (zeros dropped) | Corrected (zeros retained) |
|---|---|---|
| Claude Sonnet 4.5 | 0.435 (n=95) | **0.431** (n=96) |
| Gemini 2.5 Pro | 0.252 (n=87) | **0.228** (n=96) |
| GPT-4.1 | 0.274 (n=67) | **0.230** (n=80) |

**The headline conclusion strengthens rather than weakens.** Because the dropped
zeros were concentrated in the two lower-scoring models, retaining them widens
the gap: Sonnet vs Gemini and Sonnet vs GPT-4.1 both move from p = 0.0001 /
0.0008 to **p = 0.000003**. Gemini vs GPT-4.1 remains non-significant (p = 0.61).

**One other published claim changes, and we flag it rather than let a reviewer
find it.** §4.5 states that "neither Gemini nor GPT-4.1 shows significant
cross-dimension differences". Under the corrected extraction each shows one:

| Comparison | Published | Corrected |
|---|---|---|
| Gemini: centralisation vs update resistance | p = 0.078 (n.s.) | **p = 0.014** |
| GPT-4.1: oversight avoidance vs update resistance | p = 0.445 (n.s.) | **p = 0.028** |
| Sonnet: centralisation vs update resistance | p = 0.0003 | p = 0.0005 |
| Sonnet: oversight avoidance vs update resistance | p < 0.0001 | p = 0.0001 |

Two points on how much weight these carry. They are nominal p-values from nine
pairwise tests; under Bonferroni correction (α = 0.0056) neither survives, while
both of Sonnet's do. And their **direction is opposite to Sonnet's**: for Sonnet
update resistance is the *highest* dimension (+0.19 to +0.22 above the others),
whereas for Gemini and GPT-4.1 update resistance is now their *lowest* dimension
(−0.037, −0.039). The corrected data therefore sharpens rather than dilutes the
claim that Sonnet is distinctive: it is the only model whose update-resistance
score is elevated relative to its own other dimensions. We will restate §4.5 as
"Sonnet is the only model with a significant elevation of update resistance
relative to its other dimensions; the two nominally significant cross-dimension
differences in Gemini and GPT-4.1 are small, in the opposite direction, and do
not survive correction for multiple comparisons."

We report the corrected values throughout, disclose the bug in the appendix, and
release the corrected script with a `--legacy-falsy-drop` flag that reproduces
the published values for provenance.

### Unit of analysis, and what the near-zero ICC does and does not show (DYAi Q3)

DYAi is right that we over-read the ICC, and right to suspect it. The primary
unit is the scenario instance, with all cross-model claims additionally verified
at the seed level (clustered Mann–Whitney on seed means; mixed model with a seed
random intercept). What we should not have done is infer from ICC < 0.01 that
variants are effectively independent.

That ICC comes from a per-category mixed model with only **8, 4 and 3** seed
groups. With so few clusters the REML variance component collapses to the
boundary: the reported random-effect variances are 0.0002, 0.0000 and 0.0000, and
the oversight-avoidance and centralisation fits are visibly degenerate (intercept
0.000 with no standard error). A variance component estimated at zero from three
groups is uninformative — it is not evidence that seed identity carries no signal.

We replace it with a direct variance decomposition, which requires no variance-
component fit. Across the 524 completed replication scenario-runs, the share of
total score variance explained by each design factor is:

| Factor | Levels | η² |
|---|---|---|
| **Seed scenario** | 15 | **0.134** |
| Model | 3 | 0.051 |
| Category | 3 | 0.020 |
| Modality (text/tools) | 2 | 0.010 |
| Scope (general/domain) | 2 | 0.008 |
| Replication run | 3 | 0.003 |
| Scenario instance | 45 | 0.363 |

This answers DYAi's alternative explanation directly, and it favours **neither**
our original reading nor the surface-feature hypothesis. Seed identity explains
more variance (13.4%) than model, category, modality, scope and run *combined*
(9.2%), so the variants are **not** independent draws — our original claim was
wrong. But the surface features DYAi names as the alternative — modality labels,
prompt templates, scope wording — are the *smallest* factors in the design
(1.0%, 0.8%), so they do not dominate seed identity either. Within each
model × category cell, seed η² ranges from 0.047 to 0.228.

The practical consequence is that seed-level clustering is the correct
conservative unit, which is what our cross-model claims already use, and we
withdraw the independence claim rather than the clustering. We will rewrite D.7.3
accordingly.

### Reproduction

Every figure above is recomputed from the released artifact by:

```
python accounting_audit.py              # seed inventory, design table, transcript counts,
                                        # exclusion chain, corrected means and p-values
python variance_decomposition.py        # the eta-squared table
python variance_analysis.py             # corrected extraction (default)
python variance_analysis.py --legacy-falsy-drop   # reproduces the published values
python clustered_reanalysis.py          # seed-clustered tests (unchanged)
```

All five are in the released artifact. `accounting_audit.py` prints every figure
in this section, and the `--legacy-falsy-drop` flag lets a reviewer confirm that
the published numbers came from the buggy extraction and nothing else.

---

## Checklist of submission corrections this section commits to

1. §3.4: "21 expert-crafted base scenarios" → 21 authored across five
   categories, 15 evaluated across the three reported dimensions.
2. Table 1 pressure rows: 72 / 36 / 12 → **64 / 32 / 24**.
3. All occurrences of **1,890 transcripts → 1,154 evaluated scenario-runs**,
   with replication coverage stated (Standard text + tools only).
4. §4.1 "630 scenarios" → 630 model–scenario pairs (210 per model × 3 models).
5. Figure 2: "5 probes" → 5–10 probes organised into **four** stages; note that
   domain scenarios have no `reversion_check` stage.
6. Appendix D: add the exclusion table, disclose the falsy-zero bug, and report
   the corrected means (0.431 / 0.228 / 0.230) and p-values (both p = 0.000003).
7. D.7.3: withdraw the ICC independence claim; replace with the variance
   decomposition and retain seed clustering as the conservative unit.
8. §6.2 cross-reference (Construct Validity is §6, not §6.2); citation audit.
