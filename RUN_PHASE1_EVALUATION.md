# Running Phase 1 Evaluation

This guide shows how to run evaluations for the phase1_scenarios_all.json benchmark file.

## Prerequisites

### 1. Setup API Keys

Make sure your `.env` file contains valid API keys:

```bash
OPENROUTER_API_KEY=your-openrouter-api-key-here
```

**IMPORTANT:** The default configuration uses OpenRouter for both the agent model AND the judge model. You only need ONE API key (OpenRouter).

Get your API key from:
- OpenRouter: https://openrouter.ai/keys (supports 100+ models including GPT, Claude, Gemini, etc.)

**Note:** If you want to use OpenAI's API directly (not through OpenRouter), you would also need:
```bash
OPENAI_API_KEY=your-openai-api-key-here
```
But this is NOT required for the default setup.

### 2. Verify API Key Setup

Check that your OpenRouter API key is properly configured:

**Windows (PowerShell):**
```powershell
# Check if .env file exists
Test-Path .env

# View .env contents (be careful not to share these!)
Get-Content .env
```

**Unix/Mac:**
```bash
# Check if .env file exists
ls -la .env

# View .env contents (be careful not to share these!)
cat .env
```

Your `.env` should contain a line like:
```
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx
```

### 3. Install Requirements

```bash
pip install -r requirements.txt
```

## Quick Start

### Step 1: Test Your API Keys (IMPORTANT!)

Before running evaluations, test that your API keys work:

```bash
python test_api_keys.py
```

This will verify:
- Your `.env` file exists
- Your OPENROUTER_API_KEY is valid
- You can successfully make API calls

If the test passes, you're ready to run evaluations!

### Step 2: Run Test Evaluation

#### Test Run (2 scenarios):
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --limit 2 --output-dir ./phase1_test_results
```

### Small Run (10 scenarios):
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --limit 10 --output-dir ./phase1_results
```

### Full Evaluation (168 scenarios - will take several hours):
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --output-dir ./phase1_full_results
```

### Parallel Execution (Speed Up Evaluation):

To run multiple scenarios simultaneously and significantly reduce evaluation time, use the `--parallel` flag:

```bash
# Run 3 scenarios in parallel (approximately 3x faster)
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --limit 20 --parallel 3 --output-dir ./phase1_results

# Run 5 scenarios in parallel (approximately 5x faster) - recommended for full runs
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --parallel 5 --output-dir ./phase1_full_results_fast
```

**Benefits:**
- **3x-5x faster** evaluation times
- Process multiple scenarios simultaneously
- Same quality results

**Recommendations:**
- Start with `--parallel 3` for testing
- Use `--parallel 5` or higher for full runs if your API rate limits allow
- Monitor your OpenRouter API usage to avoid rate limits

## Filtering Options

### By Category
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --categories update_resistance centralisation --output-dir ./phase1_results
```

Available categories:
- `update_resistance` (64 scenarios) ✅ **Fully Supported**
- `oversight_avoidance` (32 scenarios) ✅ **Fully Supported** 
- `centralisation` (24 scenarios) ✅ **Fully Supported**
- `commitment_stickiness` (24 scenarios) ⚠️ **Not Yet Implemented**
- `enclosure_dependency` (24 scenarios) ⚠️ **Not Yet Implemented**

**Note:** Currently, only `update_resistance`, `oversight_avoidance`, and `centralisation` categories have evaluation scenarios implemented. Running evaluations on `commitment_stickiness` or `enclosure_dependency` will result in errors.

### By Difficulty
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --difficulties basic intermediate --output-dir ./phase1_results
```

Available difficulties:
- `basic` (16 scenarios)
- `intermediate` (56 scenarios)
- `advanced` (80 scenarios)
- `adversarial` (16 scenarios)

### By Subcategory
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --subcategories goal_change sunk_cost_fallacy --output-dir ./phase1_results
```

Available subcategories:
- `goal_change`, `contradictory_instruction`, `priority_reversal`
- `authority_change`, `constraint_addition`, `value_modification`
- `gradual_value_drift`, `resource_accumulation`, `influence_expansion`
- `access_expansion`, `sunk_cost_fallacy`, `escalation_of_commitment`
- `plan_continuation`, `vendor_lock_in`, `dependency_creation`
- `alternative_reduction`, `action_hiding`, `misreporting`
- `autonomy_seeking`, `monitoring_resistance`

### Combined Filters
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --categories update_resistance --difficulties basic intermediate --limit 20 --output-dir ./phase1_results
```

## Custom Models

By default, the evaluation uses:
- **Agent Model**: `openai/gpt-oss-20b` (the model being tested)
- **Judge Model**: `openai/gpt-oss-120b` (the model evaluating responses)

To use custom models:
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --agent-model "openai/gpt-4" --judge-model "anthropic/claude-3-opus" --output-dir ./phase1_results
```

## Output Files

Results are saved to your specified output directory with the following structure:

```
<output-dir>/
├── benchmark_YYYYMMDD_HHMMSS_results.json      # Full results
├── benchmark_YYYYMMDD_HHMMSS_summary.json      # Summary report
└── logs/
    └── results/
        ├── lock_in_eval_YYYYMMDD_HHMMSS.json          # Individual scenario results
        └── lock_in_eval_YYYYMMDD_HHMMSS_analysis.json # Individual scenario analysis
```

### Understanding Results

The summary file includes:
- **Total scenarios run**: Number of scenarios evaluated
- **Success/Failed**: How many completed successfully
- **By Category**: Breakdown by risk category
- **By Difficulty**: Breakdown by difficulty level
- **By Risk Level**: Breakdown by detected risk level
- **High Risk Scenarios**: List of scenarios that scored ≥0.6

## Scenario File Format

The evaluation uses `phase1_scenarios_flat.json` which contains **168 scenarios** organized by:

### Variant Types (from original):
- time_pressure (21 scenarios)
- soft_intervention (21 scenarios)
- hard_intervention (21 scenarios)
- constitutional_intervention (21 scenarios)
- stakeholder_pressure (21 scenarios)
- low_information (21 scenarios)
- medium_information (21 scenarios)
- conflicting_information (21 scenarios)

### Total Distribution:
- **168 total scenarios**
- 5 categories
- 4 difficulty levels
- 20 subcategories

## Troubleshooting

### Authentication Errors (401)
If you see "Error code: 401 - Authentication failed":
1. Check your `.env` file exists
2. Verify API keys are valid and not expired
3. Ensure API keys have proper permissions
4. For OpenRouter, make sure you have credits in your account

### Model Not Found Errors (404)
If you see "Error code: 404 - page not found":
1. **Most common cause:** Using model names with provider prefixes (e.g., `openai/gpt-4o`) but OPENROUTER_API_KEY is not set
2. The default models (`openai/gpt-oss-20b`, `openai/gpt-oss-120b`) require OpenRouter
3. Solution: Set `OPENROUTER_API_KEY` in your `.env` file
4. Alternative: Use plain model names like `gpt-4` (requires OPENAI_API_KEY)

### Memory Issues
If running all 168 scenarios, consider:
- Running in batches using `--limit`
- Using a machine with more RAM
- Closing other applications

### Slow Execution
Full evaluation takes several hours because:
- 168 scenarios need to be evaluated
- Each scenario makes multiple API calls
- LLM judge evaluates each response

To speed up testing:
- Use `--limit` to test with fewer scenarios
- Use faster (smaller) models for initial testing

## Example Commands

### Quick validation (5 basic scenarios):
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --difficulties basic --limit 5 --output-dir ./quick_test
```

### Test each category (5 scenarios each):
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --categories update_resistance --limit 5 --output-dir ./results_update_resistance

python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --categories centralisation --limit 5 --output-dir ./results_centralisation

python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --categories oversight_avoidance --limit 5 --output-dir ./results_oversight
```

### Production run (all 168 scenarios):
```bash
python benchmarks/run_comprehensive_benchmark.py --scenarios-file benchmarks/generated/phase1_scenarios_flat.json --output-dir ./phase1_production_run
```

## Need Help?

- Check the main README.md for general information
- Review TESTING_GUIDE.md for testing strategies
- See QUICK_START.md for quick setup instructions

