# LLM Policy Generation — Technical Documentation

## What this is

A system that takes plain English HR policy descriptions from users and converts them into valid `SimulationConfig` objects for the attrition simulation engine. The LLM handles translation from natural language to structured parameters. Your existing `run_simulation()` code is unchanged.

---

## How it works — the short version

```
User text → LLM picks ratios → your code multiplies by calibration anchors → Pydantic clamps → SimulationConfig → run_simulation()
```

The LLM never writes to `calibration.json`. It never generates absolute values. It picks multipliers. Your code does the math.

---

## Architecture

```
calibration.json  (read-only, never modified by LLM)
      |
      | extract 6 anchor values
      v
build_context(calib)
      |
      +--------------------+
      |                    |
      v                    v
  calib anchors       user intent (confirmed)
      |                    |
      +--------------------+
      |
      v
LLM call
  - system prompt: param semantics + severity guide + few-shot examples
  - forced JSON output: all 9 fields + _justification
      |
      v
build_config_from_llm_output(llm_json, calib)
  - multiplier fields: ratio × calib anchor = absolute value
  - direct fields: pass through as-is
  - all fields: clamped by PARAM_BOUNDS
      |
      v
show user config + justification
      |
      v (user confirms)
run_simulation(config)
```

---

## The two types of fields

### Direct fields — LLM sets these straight from user intent

| Field | How LLM sets it | Example |
|---|---|---|
| `layoff_ratio` | User stated it explicitly | "15% layoffs" → `0.15` |
| `hiring_active` | Intent extraction | layoff scenario → `False` |
| `duration_months` | Time extraction | "next quarter" → `3` |
| `workload_multiplier` | Semantic scale | "survivors absorb work" → `1.3` |
| `overtime_bonus` | Pay mention detection | "no extra pay" → `0.0` |
| `wlb_boost` | Policy type detection | "flexible hours" → `0.6` |
| `shock_factor` | Severity + contagion reasoning | layoff → `0.6` |

### Multiplier fields — LLM picks a ratio, your code computes the absolute

| Field | Calibration anchor | Example |
|---|---|---|
| `stress_gain_rate` | `behavior_stress_gain_rate` | `5.5 × 0.01 = 0.055` |
| `motivation_decay_rate` | `motivation_recovery_rate` | `4.5 × 0.0079 = 0.03555` |

---

## Calibration context — what the LLM sees

```python
def build_context(calib: dict) -> dict:
    return {
        "annual_attrition_rate":     calib["annual_attrition_rate"],
        "behavior_stress_gain_rate": calib["behavior_stress_gain_rate"],
        "motivation_recovery_rate":  calib["motivation_recovery_rate"],
        "avg_burnout_limit":         calib["avg_burnout_limit"],
        "calib_quality":             calib["calib_quality"],
        "calib_attrition_std":       calib["calib_attrition_std"],
    }
```

That is the complete context. Nothing else from `calibration.json` goes to the LLM.

---

## Parameter bounds — clamp values here, not in calibration

```python
def get_param_bounds(calib: dict) -> dict:
    sgr = calib["behavior_stress_gain_rate"]
    mdr = calib["motivation_recovery_rate"]
    return {
        "workload_multiplier":   (0.5, 1.6),
        "stress_gain_rate":      (0.4 * sgr, 9.0 * sgr),
        "motivation_decay_rate": (0.3 * mdr, 10.0 * mdr),
        "shock_factor":          (0.0, 0.7),
        "layoff_ratio":          (0.0, 0.3),
        "overtime_bonus":        (0.0, 5.0),
        "wlb_boost":             (0.0, 1.0),
        "duration_months":       (1, 36),
    }
```

Bounds for `stress_gain_rate` and `motivation_decay_rate` are derived from calibration anchors so they shift automatically per dataset. A company with `behavior_stress_gain_rate = 0.007` gets tighter bounds than one with `0.01`.

---

## Multiplier semantic scales

These go in your system prompt. They tell the LLM what ratios mean for each company.

### stress_gain_rate multiplier
```
0.5x  = calm environment, remote/flexible work
0.8x  = mild pressure
1.0x  = normal operations
2.0x  = elevated pressure, KPI crunch
3.5x  = high pressure, understaffed
5.5x  = layoff panic, hiring freeze
8.0x  = extreme — use only for catastrophic scenarios
```

### motivation_decay_rate multiplier
```
0.3x  = highly rewarding, strong recognition
0.5x  = good environment, overtime paid
1.0x  = normal
3.0x  = stagnation, no growth
4.5x  = layoff survivors, active fear
8.0x  = promotion freeze + overwork + no pay
```

### shock_factor (direct, no multiplier)
```
0.0  = no contagion (baseline)
0.1  = low — remote culture, weak peer bonds
0.3  = moderate — normal office environment
0.5  = high — tight teams, visible departures
0.6  = very high — layoffs, mass exits
```

### workload_multiplier (direct, no multiplier)
```
0.8  = reduced workload (4-day week, reduced output)
0.85 = flexible work, compressed
1.0  = normal
1.2  = elevated, KPI pressure
1.3  = high, survivors absorbing departed work
1.45 = intensive overtime
1.6  = extreme crunch (max)
```

---

## Attrition severity guide — goes in system prompt

```
annual_attrition_rate < 5%:
  Very stable, senior workforce. Employees are resilient.
  Use conservative multipliers (2x–4x max for stress/motivation).
  Policies have gradual effects. Recovery is slow.

annual_attrition_rate 5%–15%:
  Moderate churn. Standard sensitivity.
  Full multiplier ranges apply.

annual_attrition_rate > 15%:
  Fragile workforce already under pressure.
  Policies hit hard and cascade quickly.
  A bad policy on top of existing churn can cause runaway attrition.
```

---

## LLM output format

Force the LLM to return exactly this JSON structure. No preamble, no markdown, no explanation outside the JSON.

```json
{
  "workload_multiplier": 1.3,
  "motivation_decay_rate_multiplier": 4.5,
  "shock_factor": 0.6,
  "hiring_active": false,
  "layoff_ratio": 0.15,
  "stress_gain_rate_multiplier": 5.5,
  "duration_months": 3,
  "overtime_bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "survivors absorb work from 15% reduction",
    "stress_gain_rate": "5.5x baseline — layoff panic, job insecurity cascade",
    "motivation_decay_rate": "4.5x baseline — survivor guilt, fear of next round",
    "shock_factor": "0.6 — each departure triggers visible fear in remaining staff",
    "hiring_active": "frozen — layoff scenario, no backfill",
    "duration_months": "3 — user said next quarter"
  }
}
```

Note: `stress_gain_rate` and `motivation_decay_rate` are suffixed `_multiplier` in the LLM output. Your conversion function strips the suffix and computes the absolute.

---

## Conversion function

```python
from dataclasses import dataclass
from backend.core.simulation.policies import SimulationConfig

def clamp(val, lo, hi):
    return max(lo, min(hi, val))

def build_config_from_llm_output(llm_json: dict, calib: dict) -> SimulationConfig:
    bounds = get_param_bounds(calib)
    sgr    = calib["behavior_stress_gain_rate"]
    mdr    = calib["motivation_recovery_rate"]

    stress_gain_rate    = llm_json["stress_gain_rate_multiplier"] * sgr
    motivation_decay    = llm_json["motivation_decay_rate_multiplier"] * mdr

    return SimulationConfig(
        workload_multiplier   = clamp(llm_json["workload_multiplier"],
                                      *bounds["workload_multiplier"]),
        motivation_decay_rate = clamp(motivation_decay,
                                      *bounds["motivation_decay_rate"]),
        shock_factor          = clamp(llm_json["shock_factor"],
                                      *bounds["shock_factor"]),
        hiring_active         = bool(llm_json["hiring_active"]),
        layoff_ratio          = clamp(llm_json["layoff_ratio"],
                                      *bounds["layoff_ratio"]),
        stress_gain_rate      = clamp(stress_gain_rate,
                                      *bounds["stress_gain_rate"]),
        duration_months       = clamp(int(llm_json["duration_months"]),
                                      *bounds["duration_months"]),
        overtime_bonus        = clamp(llm_json["overtime_bonus"],
                                      *bounds["overtime_bonus"]),
        wlb_boost             = clamp(llm_json["wlb_boost"],
                                      *bounds["wlb_boost"]),
    )
```

---

## Few-shot examples for system prompt

Include all of these. They teach the LLM to reason about every field, not just the obvious ones.

### Layoff
```
User: "15% staff reduction next quarter, no backfill"
Output:
  workload_multiplier:          1.3   (survivors absorb work)
  stress_gain_rate_multiplier:  5.5x  (panic)
  motivation_decay_multiplier:  4.5x  (survivor guilt)
  shock_factor:                 0.6   (high contagion)
  hiring_active:                false
  layoff_ratio:                 0.15
  duration_months:              3
  overtime_bonus:               0.0
  wlb_boost:                    0.0
```

### Hiring freeze
```
User: "hiring freeze for the year"
Output:
  workload_multiplier:          1.25  (work falls on survivors)
  stress_gain_rate_multiplier:  2.8x  (overburden)
  motivation_decay_multiplier:  3.0x  (no growth, overloaded)
  shock_factor:                 0.25
  hiring_active:                false
  layoff_ratio:                 0.0
  duration_months:              12
  overtime_bonus:               0.0
  wlb_boost:                    0.0
```

### Remote work
```
User: "full remote work policy"
Output:
  workload_multiplier:          0.9
  stress_gain_rate_multiplier:  0.6x  (commute relief)
  motivation_decay_multiplier:  0.8x  (slight isolation effect)
  shock_factor:                 0.15
  hiring_active:                true
  layoff_ratio:                 0.0
  duration_months:              12
  overtime_bonus:               0.0
  wlb_boost:                    0.4
```

### Flexible hours
```
User: "flexible working hours, employees choose schedule"
Output:
  workload_multiplier:          0.85
  stress_gain_rate_multiplier:  0.7x
  motivation_decay_multiplier:  0.5x  (high autonomy)
  shock_factor:                 0.1
  hiring_active:                true
  layoff_ratio:                 0.0
  duration_months:              12
  overtime_bonus:               0.0
  wlb_boost:                    0.6   (schedule autonomy = highest WLB driver)
```

### Paid overtime
```
User: "mandatory overtime, 1.5x pay"
Output:
  workload_multiplier:          1.45
  stress_gain_rate_multiplier:  1.8x  (high hours)
  motivation_decay_multiplier:  0.4x  (pay compensates burden)
  shock_factor:                 0.3
  hiring_active:                true
  layoff_ratio:                 0.0
  duration_months:              12
  overtime_bonus:               2.5
  wlb_boost:                    0.0
```

### Unpaid overtime
```
User: "mandatory overtime, no extra pay"
Output:
  workload_multiplier:          1.45
  stress_gain_rate_multiplier:  2.5x  (overwork with no compensation)
  motivation_decay_multiplier:  3.5x  (unpaid overwork destroys morale)
  shock_factor:                 0.4
  hiring_active:                true
  layoff_ratio:                 0.0
  duration_months:              12
  overtime_bonus:               0.0   (explicitly no pay)
  wlb_boost:                    0.0
```

### Promotion freeze
```
User: "promotion freeze, no raises this year"
Output:
  workload_multiplier:          1.0   (workload unchanged)
  stress_gain_rate_multiplier:  1.0x  (stress normal, morale is the problem)
  motivation_decay_multiplier:  4.0x  (stagnation devastates identity/future)
  shock_factor:                 0.3   (frustrated employees quit, affecting peers)
  hiring_active:                true
  layoff_ratio:                 0.0
  duration_months:              12
  overtime_bonus:               0.0
  wlb_boost:                    0.0
```

### KPI pressure
```
User: "aggressive KPI targets, performance reviews monthly"
Output:
  workload_multiplier:          1.2
  stress_gain_rate_multiplier:  2.0x
  motivation_decay_multiplier:  1.0x  (normal, some are motivated by targets)
  shock_factor:                 0.1
  hiring_active:                true
  layoff_ratio:                 0.0
  duration_months:              12
  overtime_bonus:               0.0
  wlb_boost:                    0.0
```

---

## Disambiguation — ask before translating

If the user's intent is ambiguous on any of these points, ask before generating config:

- "Same workload compressed, or genuinely less work?"
- "Is overtime paid or unpaid?"
- "Temporary policy or permanent?"
- "Does the policy affect the whole company or one department?"

Never silently assume. Wrong assumptions produce wrong configs and wrong simulation results with no visible error.

---

## What the user sees before the simulation runs

Show this confirmation screen before calling `run_simulation()`:

```
Policy: "15% layoffs next quarter"

Generated configuration:
  Layoff ratio:        15% of workforce
  Hiring:              Frozen
  Duration:            3 months
  Workload:            1.3x normal (survivors absorb departed work)
  Stress accumulation: 5.5x baseline rate (panic-level)
  Motivation decay:    4.5x baseline rate (survivor guilt)
  Contagion factor:    0.6 (high — each departure affects peers)

Confidence: stable calibration (std=0.0068)

Run simulation?  [Yes] [Adjust]
```

The `_justification` field from the LLM populates the plain-language descriptions. The `calib_attrition_std` and `calib_quality` drive the confidence line.

---

## Cross-dataset behaviour

The multiplier approach works automatically across different company datasets because:

- `behavior_stress_gain_rate` differs per dataset (0.01 vs 0.007)
- All multiplier-field bounds are derived from calibration anchors
- LLM adjusts severity reasoning based on `annual_attrition_rate`
- The same "5.5x stress" prompt produces `0.055` for one company and `0.0385` for another

No prompt changes needed when switching datasets. The context dict carries all dataset-specific information.

---

## What not to do

- Do not pass the full `calibration.json` to the LLM — only the 6 anchor values
- Do not let the LLM output absolute values for `stress_gain_rate` or `motivation_decay_rate`
- Do not skip the user confirmation step — silent wrong configs are worse than visible errors
- Do not modify `calibration.json` in the LLM pipeline — it is read-only
- Do not fine-tune the model — prompt engineering + validation handles this use case
- Do not run simulation without clamping — unclamped LLM output can blow up the physics

---

## Files involved

```
backend/
  core/
    simulation/
      policies.py          ← SimulationConfig dataclass lives here
      time_engine.py       ← run_simulation() — unchanged
      behavior_engine.py   ← simulation physics — unchanged
  ml/
    exports/
      calibration.json     ← read-only input to LLM context builder

  llm/                     ← new, you build this
    context_builder.py     ← build_context(calib)
    prompt_builder.py      ← system prompt with semantics + few-shots
    translator.py          ← LLM call + build_config_from_llm_output()
    bounds.py              ← get_param_bounds(calib)
```
