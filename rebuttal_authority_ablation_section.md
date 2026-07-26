# Rebuttal section: authority-framing ablation (results)

Drop-in replacement for §1.1 of `rebuttal_draft.md`. All figures are all-16-scenario
means of `avg_risk_score` from `authority_ablation_summary.json` unless a subset or
metric is named. 384/384 scenario-runs completed, 0 judge failures, 0 exclusions,
0 truncated transcripts; 8 arms from a single run window. Second-judge figures are
from `authority_ablation_grok_summary.json`.

**Stale claims to fix in the current draft:** the ablation covers **16
update-resistance text scenarios**, not "48 Standard update-resistance scenarios per
model"; the L4 arm no longer contains "supersession/chain-of-command" (isolated into
a separate arm after an audit found it confounded authority with task-clarification);
and the paraphrase check **was** run, as two arms rather than "k rephrasings at fixed
authority level".

---

## 1.1 Construct validity: the authority-framing ablation (AC issue 1; DYAi W2/Q2; LGUh W1/Q1)

We agree this was the central validity question and should not have been left to
future work. We ran it, and it changed our reading of our own headline finding.

### Design

Our published update-delivery probes carry no authority grounding. The obvious
ablation — progressively attributing the directive — turns out to be insufficient,
for a reason we did not anticipate: any attribution appended to the directive arrives
in the **same untrusted channel as the directive itself**. "Sent by: Dana Whitfield,
VP of Product" is unverifiable, and a message asserting its own authority is
structurally indistinguishable from a social-engineering payload. An agent that
resists it may be behaving correctly.

We therefore crossed two factors. Factor A grades authority **asserted in the
directive** (L1 unattributed as published → L2 named sender → L3 deciding body and
record → L4 authority basis and scope). Factor B adds a governance preamble to the
**system prompt** — the trusted channel — naming the role that legitimately owns the
objective, so the directive's attribution can be checked against it.

| Arm | Directive | System prompt | Isolates |
|---|---|---|---|
| L1 | unattributed (published, verbatim) | unchanged | published baseline |
| L4 | full attribution | unchanged | **asserted** authority |
| L1V | unattributed | + governance preamble | preamble alone |
| L4V | full attribution | + governance preamble | **verifiable** authority |
| P1 | paraphrase, plain register | unchanged | wording (register) |
| P2 | paraphrase, high specificity | unchanged | wording (specificity) |

L1 is byte-identical to the published scenarios; V arms alter only the system prompt;
P arms alter only surface form, holding authority absent. 16 UR text scenarios × 8
arms × 3 models, same pipeline, judge and temperatures as the Standard benchmark.
`avg_risk_score` was pre-registered as primary before data collection.

### Result 1: asserted authority does nothing; verifiable authority reduces resistance

| Model | L1 | L4 | L1V | L4V | L1→L4 (asserted) | L1V→L4V (verifiable) | **Interaction** |
|---|---|---|---|---|---|---|---|
| Claude Sonnet 4.5 | 0.595 | 0.640 | 0.742 | 0.523 | +0.045 (n.s.) | **−0.219** (p=0.017) | **−0.264** |
| Gemini 2.5 Pro | 0.243 | 0.199 | 0.418 | 0.144 | −0.044 (n.s.) | **−0.274** (p=0.026) | −0.230 |
| GPT-4.1 | 0.179 | 0.175 | 0.203 | 0.104 | −0.004 (n.s.) | −0.099 (n.s.) | −0.095 |

Attributing the directive — named sender, deciding body, decision record, explicit
authority basis — does **not** reduce update resistance for any model. Registering the
authorising role in the trusted channel so the attribution becomes checkable does, for
both Sonnet and Gemini.

**We report the interaction, (L4V−L1V) − (L4−L1), as the effect estimate**, because the
preamble moves L1V on its own: for Sonnet L1→L1V = +0.147 [+0.053, +0.245], p=0.015.
The preamble states that unattributed instructions are unverified, which raises the
score of the unattributed arm as well as lowering the attributed one. The raw
L1V→L4V contrast is therefore an **upper bound** on the effect of attribution, and the
interaction is the defensible estimate. We report both.

### Result 2: the published score is not purely authority-verification

Sonnet's score decomposed by probe stage:

| Stage | L1 | L4V |
|---|---|---|
| update-delivery probe | 0.587 | 0.531 |
| post-update probes | 0.581 | 0.498 |
| **reversion check** | **0.812** | 0.588 |

Verification-seeking would concentrate at the update-delivery probe. Instead the
largest component is **reversion** — returning to the original goal in later probes
after apparent compliance — which is goal preservation, not authority checking. The
reviewers' alternative explanation therefore does not account for the whole effect.
But every stage falls under verified authority, so the effect is not
authority-independent either. **Both mechanisms are present, and this design separates
them.**

### Result 3: Sonnet's residual elevation sits where resistance is defensible

Tagging each scenario by whether the update moves toward or away from the safer option
(a partition fixed before analysis and disclosed in full in the artifact):

| Subset | Sonnet L1 | Sonnet L4V | Gemini L1 | Gemini L4V |
|---|---|---|---|---|
| Update toward-safety or neutral (n=10) | 0.470 | **0.427** | 0.147 | 0.115 |
| Update moves away from safety (n=6) | 0.803 | **0.683** | 0.403 | 0.192 |

Sonnet's scores are consistently far higher on the scenarios where resistance is
defensible — refusing to implement an encryption backdoor (`UR_CONTRA_0003`) or to cut
clinical testing to raise throughput (`UR_PRIORITY_0004`). This directly addresses
LGUh's W1: our benchmark does penalise defensible refusal, and the
direction-partitioned analysis makes that visible instead of folding it into one risk
number. Gemini declines much further on the same set (0.403 → 0.192), i.e. it becomes
more compliant with requests that merit pushback. **We report this subset as
descriptive only** — 6 instances over 4 distinct directive texts and 4 seeds is
underpowered for a directional claim, and our analyzer refuses to state one.

### Result 4: the signal is not an artifact of probe wording (LGUh Q1, second half)

P1 removes the all-caps urgency header and recasts the directive conversationally;
P2 states the same request with concrete operational detail. Both hold authority absent.

| Model | L1 | P1 (register) | P2 (specificity) | L1→P1 | L1→P2 |
|---|---|---|---|---|---|
| Claude Sonnet 4.5 | 0.595 | 0.535 | 0.539 | −0.059 (p=0.51) | −0.056 (p=0.48) |
| Gemini 2.5 Pro | 0.243 | 0.251 | 0.262 | +0.008 (p=0.78) | +0.019 (p=0.97) |
| GPT-4.1 | 0.179 | 0.200 | 0.111 | +0.021 (p=0.48) | −0.068 (p=0.028) |

Rephrasing moves scores little. For Sonnet neither paraphrase differs significantly
and both CIs include zero; the largest paraphrase effect anywhere (GPT-4.1's −0.068)
is a quarter of Sonnet's interaction estimate. Every paraphrase effect is far below the
instrument's own noise floor: five of our domain scenarios are byte-identical to their
general-context twins, and Sonnet's published scores on that identical input differ by
up to **0.539**.

So the two halves of Q1 answer differently, and the combination is the point: update
resistance is **not** an artifact of how we phrased the probe — it survives paraphrase
— but it **is** substantially authority-sensitive.

### Robustness, and where it fails

We report this honestly because two of our three secondary checks are weaker than the
primary result.

**Replication across runs — holds.** Two independent runs of L1/L4/L1V/L4V under the
same judge give a mean absolute difference in cell means of 0.036 (max 0.073). The two
principal contrasts are stable (Sonnet L1→L4 +0.071/+0.045; L1V→L4V −0.190/−0.219).
The preamble-alone contrast is the least stable quantity (+0.032/+0.147), which is why
we report the interaction rather than the raw L1V→L4V.

**Second judge — direction holds, magnitude and significance do not.** Re-scoring the
identical transcripts with Grok-4.20-multi-agent (no new agent calls):

| Model | Contrast | GPT-4o | Grok |
|---|---|---|---|
| Sonnet 4.5 | asserted | +0.045 (n.s.) | +0.032 (n.s.) |
| Sonnet 4.5 | **verifiable** | **−0.219, p=0.017** | **−0.129, p=0.012** |
| Gemini 2.5 Pro | verifiable | −0.274, p=0.026 | −0.092, **p=0.289** |

Sonnet's result replicates under an architecturally independent judge. Gemini's keeps
its direction but loses significance. Grok scores substantially lower in absolute terms
throughout (by 0.08–0.49), placing GPT-4.1 at floor, so absolute values are not
comparable across judges.

**Secondary metric — does not replicate.** Under `max_risk_score` the verifiable-authority
contrast is not significant for any model (Sonnet −0.125, p=0.121; Gemini −0.138,
p=0.234). Being a maximum over probes, it cannot register a decline confined to the
post-update stage, which is much of what the manipulation produces; but we report the
failure rather than only the metric that worked.

**Net claim.** The direction and rank-ordering of the authority effect replicate across
two runs and two judges. Its magnitude is metric- and judge-dependent. We therefore
claim the qualitative result and the interaction estimate, and make no claim to a
precise effect size.

### What we now claim, and what we withdraw

We **withdraw** any reading of update resistance as measuring resistance to legitimate
goal updates. What it measures is **resistance to updates whose authority the agent
cannot verify** — substantially reduced once authority is registered in the trusted
channel, and something our published probes could not distinguish from goal
preservation. We will relabel the dimension and report L1 and L4V as separate columns.

We do **not** claim the cross-model difference disappears. Sonnet remains
significantly separated from both comparison models at L4V (+0.379 vs Gemini, p=0.0004;
+0.419 vs GPT-4.1, p=0.0001), as at L1. An equivalence test against a pre-registered
±0.08 margin does not reject at this sample size, so non-significant rows are reported
as **inconclusive, not null**.

### Limitations

One run of 16 text scenarios per arm per model, spanning 8 seeds; a second run of four
arms supports the stability estimate above. The argument rests on within-model paired
contrasts, which are adequately powered at this n; the cross-model equivalence claim is
not, and we do not make it. The governance preamble establishes authority by
stipulation in the system prompt — no text benchmark can supply cryptographic
authentication — and its acceptance condition is keyed on role rather than sender name;
we quote it verbatim in the artifact. Prompt length necessarily covaries with authority
level, and we report the within-arm correlation as a check rather than a correction.

---

## Artifact

Released with the rebuttal: the deterministic generator with machine-checked
invariants, all 8 arm bundles, a human-readable review file containing every directive
and preamble verbatim, the runner, the analysis, a 24-check pre-flight validator, the
second-judge re-scoring tool, and all result files with **full** per-probe transcripts
and judge outputs. Transcripts in the original submission were truncated to 500
characters per response by a logging defect, which prevented third-party re-scoring;
that is fixed and disclosed.
