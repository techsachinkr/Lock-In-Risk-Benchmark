# Rebuttal section: scoring validation (§1.4)

Drop-in for the scoring-weights part of §1.4 of `rebuttal_draft.md`. Addresses
LGUh W2 and W3, and AC issue 4. Every figure is reproduced by
`python weight_sensitivity.py`.

---

## Weight sensitivity (LGUh W2)

LGUh is right that we asserted the weights rather than justifying them. We have
now run the sensitivity analysis, recomputing every update-resistance score from
the **logged per-factor judge outputs** under alternative weighting schemes. This
required no new model calls: each probe's judge assessments are stored in the
released transcripts and are exactly the inputs to the weighted sum.

**Reproduction check.** Before reweighting anything we recomputed each scenario's
published score from the logged factors using the published weights. All
**192/192** scenarios reproduce to within 1e-5 (mean absolute error 0.00000), so
the reweighting operates on a verified reconstruction rather than an approximation.

**Model means and ranking under each scheme:**

| Scheme | Sonnet 4.5 | Gemini 2.5 Pro | GPT-4.1 | Ranking |
|---|---|---|---|---|
| Published (0.25/0.15/0.20/0.10/0.10/0.05/0.10/0.05) | 0.580 | 0.250 | 0.186 | — |
| Uniform (all factors equal) | 0.525 | 0.285 | 0.241 | preserved |
| Primary factors only (resistance / reversion / compliance) | 0.619 | 0.160 | 0.077 | preserved |
| Justification factor removed, remainder renormalised | 0.573 | 0.229 | 0.168 | preserved |

**Significance under each scheme** (Mann–Whitney U, Sonnet vs each other model):

| Scheme | vs Gemini | vs GPT-4.1 |
|---|---|---|
| Published | p = 5.3e-20 | p = 5.5e-22 |
| Uniform | p = 1.0e-19 | p = 2.9e-21 |
| Primary only | p = 2.4e-20 | p = 1.7e-22 |
| No justification | p = 5.3e-20 | p = 8.4e-22 |

**Random weight vectors.** Across **1,000 Dirichlet draws** centred on uniform
over all eight factors, the model ranking is preserved in **1,000/1,000 (100%)**
of draws, and Sonnet remains significantly separated from *both* comparison
models in **1,000/1,000 (100%)**.

The conclusion does not depend on the weights. We will state this in the paper
and release `weight_sensitivity.py`, rather than continuing to assert the weights
without support.

## The justification-complexity factor (LGUh W3)

We accept this objection on its merits. A model should not be scored as
higher-risk for explaining its reasoning transparently, and the "double penalty"
framing is fair: a model that both resists an unauthenticated directive and
explains why is charged twice.

Quantitatively the factor is bounded and does not drive any reported result —
weight 0.05, mean factor value 0.632, so its maximum contribution to any score is
**0.043**; removing it changes scores by **0.016 on average (max 0.026)** and the
cross-model separation is unchanged (Sonnet vs Gemini p = 5.3e-20 before and
after). But its small size is a reason to remove it cheaply, not a reason to keep
it: **we remove it from the headline score and report it as a descriptive pattern
indicator only**, recomputing all main-text values.

## A correction to the paper's description of the formula

Our own audit found that §B.1.3 describes a **10-factor** formula, which is the
**sandbox** scorer (`update_resistance_sandbox.py`): it adds `tool_resistance`
and `file_resistance` at 0.05 each and its weights sum to **0.95, not 1.00** as
the "Weight Rationale" paragraph claims. The text scenarios that produced the
pressure results use an **8-factor** form
(`update_resistance.py:1086`) with different primary weights (resistance 0.25,
reversion 0.20, compliance 0.15) summing to exactly 1.00. Both weight
justification at 0.05. We will document the two formulas separately and correct
the normalisation claim.

## Scope

This analysis covers the pressure-benchmark update-resistance scenarios (n = 192
across three models), which are the runs that use the weighted formula. The
Standard benchmark's text and tool scenarios are scored by a different instrument
(one judge call per probe, averaged over the risk stages) that has no weights to
vary — a distinction the submission did not make clear and that we now state
explicitly.

## Reproduction

```
python weight_sensitivity.py --draws 1000
```
