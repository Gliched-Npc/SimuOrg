EXTENDED_SCENARIOS = [
    {
        "query": "mandatory return to office 5 days a week after 2 years of remote",
        "content": """
User: "mandatory return to office 5 days a week after 2 years of remote"
Output:
{
  "workload_multiplier": 1.1,
  "stress_gain_rate_multiplier": 3.0,
  "motivation_decay_rate_multiplier": 3.5,
  "shock_factor": 0.5,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": -0.5,
  "_justification": {
    "workload_multiplier": "1.1 — commute time and context-switching create effective overload",
    "stress_gain_rate_multiplier": "3.0x — forced RTO after extended remote is a severe autonomy loss, triggers attrition signal",
    "motivation_decay_rate_multiplier": "3.5x — employees who adapted to remote feel punished; resentment is high",
    "shock_factor": "0.5 — visible, high-profile policy. Dissenters leave loudly, peer contagion strong",
    "wlb_boost": "-0.5 — commute and loss of schedule flexibility actively degrades WLB"
  }
}
"""
    },
    {
        "query": "hybrid policy — 3 days in office, 2 days remote",
        "content": """
User: "hybrid policy — 3 days in office, 2 days remote"
Output:
{
  "workload_multiplier": 0.95,
  "stress_gain_rate_multiplier": 0.85,
  "motivation_decay_rate_multiplier": 0.85,
  "shock_factor": 0.1,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.2,
  "_justification": {
    "stress_gain_rate_multiplier": "0.85x — partial autonomy retained, commute burden reduced",
    "motivation_decay_rate_multiplier": "0.85x — balanced arrangement, broadly acceptable",
    "wlb_boost": "0.2 — moderate WLB gain from 2 remote days, not transformative"
  }
}
"""
    },
    {
        "query": "major org restructure — teams merged, reporting lines changed, many roles redefined",
        "content": """
User: "major org restructure — teams merged, reporting lines changed, many roles redefined"
Output:
{
  "workload_multiplier": 1.2,
  "stress_gain_rate_multiplier": 3.5,
  "motivation_decay_rate_multiplier": 2.5,
  "shock_factor": 0.45,
  "hiring_active": false,
  "layoff_ratio": 0.0,
  "duration_months": 6,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.2 — role ambiguity and transition overhead increases effective load",
    "stress_gain_rate_multiplier": "3.5x — uncertainty about roles, managers, and job security is a primary stressor",
    "motivation_decay_rate_multiplier": "2.5x — identity disruption; people who built careers in old structure feel destabilized",
    "shock_factor": "0.45 — reorgs are visible events, high peer discussion, rumor amplifies fear",
    "hiring_active": "false — orgs in restructure typically pause hiring during transition",
    "duration_months": "6 — reorg disruption window typically 3–6 months; defaulting to 6"
  }
}
"""
    },
    {
        "query": "team split — engineering divided into two separate units with separate leadership",
        "content": """
User: "team split — engineering divided into two separate units with separate leadership"
Output:
{
  "workload_multiplier": 1.1,
  "stress_gain_rate_multiplier": 2.0,
  "motivation_decay_rate_multiplier": 1.5,
  "shock_factor": 0.3,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 6,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.1 — coordination overhead and duplicate processes during transition",
    "stress_gain_rate_multiplier": "2.0x — split causes uncertainty about team identity and leadership quality",
    "motivation_decay_rate_multiplier": "1.5x — team cohesion loss, some employees lose trusted peers or managers",
    "shock_factor": "0.3 — moderate — close-knit teams may see contagion if key people exit"
  }
}
"""
    },
    {
        "query": "new CEO hired externally with a reputation for aggressive cost-cutting",
        "content": """
User: "new CEO hired externally with a reputation for aggressive cost-cutting"
Output:
{
  "workload_multiplier": 1.15,
  "stress_gain_rate_multiplier": 4.0,
  "motivation_decay_rate_multiplier": 3.5,
  "shock_factor": 0.5,
  "hiring_active": false,
  "layoff_ratio": 0.0,
  "duration_months": 6,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.15 — anticipatory tightening, teams overperform to avoid cuts",
    "stress_gain_rate_multiplier": "4.0x — existential threat signal; unknown leadership direction triggers fear cascade",
    "motivation_decay_rate_multiplier": "3.5x — culture uncertainty, previous commitments now in doubt",
    "shock_factor": "0.5 — leadership change is a loud event; senior employees are first to exit",
    "hiring_active": "false — cost-cutting reputation signals freeze",
    "duration_months": "6 — uncertainty window until new strategy is communicated"
  }
}
"""
    },
    {
        "query": "direct manager replaced with a micromanager known for high pressure tactics",
        "content": """
User: "direct manager replaced with a micromanager known for high pressure tactics"
Output:
{
  "workload_multiplier": 1.2,
  "stress_gain_rate_multiplier": 3.5,
  "motivation_decay_rate_multiplier": 3.0,
  "shock_factor": 0.4,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.2 — micromanagement increases perceived and actual task overhead",
    "stress_gain_rate_multiplier": "3.5x — direct manager is the #1 attrition predictor; toxic management is catastrophic at team level",
    "motivation_decay_rate_multiplier": "3.0x — autonomy removed, psychological safety collapses",
    "shock_factor": "0.4 — team is small and tight; each exit is felt immediately by remaining members"
  }
}
"""
    },
    {
        "query": "beloved long-tenure CEO retiring, replaced by internal promotion",
        "content": """
User: "beloved long-tenure CEO retiring, replaced by internal promotion"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 1.5,
  "motivation_decay_rate_multiplier": 1.5,
  "shock_factor": 0.25,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 6,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "stress_gain_rate_multiplier": "1.5x — cultural continuity concern despite internal successor; uncertainty is real but muted",
    "motivation_decay_rate_multiplier": "1.5x — emotional attachment to outgoing leader creates a transitional dip",
    "shock_factor": "0.25 — internal promotion reduces shock vs external hire; moderate peer discussion",
    "duration_months": "6 — transition anxiety resolves once new leader establishes direction"
  }
}
"""
    },
    {
        "query": "company-wide PIP rollout — bottom 10% of performers placed on improvement plans",
        "content": """
User: "company-wide PIP rollout — bottom 10% of performers placed on improvement plans"
Output:
{
  "workload_multiplier": 1.15,
  "stress_gain_rate_multiplier": 4.5,
  "motivation_decay_rate_multiplier": 4.0,
  "shock_factor": 0.5,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 6,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.15 — employees overwork to avoid being in the bottom 10%",
    "stress_gain_rate_multiplier": "4.5x — fear of termination is pervasive, even among solid performers",
    "motivation_decay_rate_multiplier": "4.0x — rank-and-yank culture destroys psychological safety and collaboration",
    "shock_factor": "0.5 — PIP is visible and discussed; each PIP placed amplifies fear in peers"
  }
}
"""
    },
    {
        "query": "annual performance review replaced with continuous real-time feedback system",
        "content": """
User: "annual performance review replaced with continuous real-time feedback system"
Output:
{
  "workload_multiplier": 1.05,
  "stress_gain_rate_multiplier": 1.2,
  "motivation_decay_rate_multiplier": 0.8,
  "shock_factor": 0.1,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.05 — feedback administration overhead is real but minor",
    "stress_gain_rate_multiplier": "1.2x — constant visibility is mildly anxiety-inducing for some employees",
    "motivation_decay_rate_multiplier": "0.8x — faster recognition loops improve motivation; employees feel seen"
  }
}
"""
    },
    {
        "query": "company acquired by a larger firm, integration in progress, culture clash expected",
        "content": """
User: "company acquired by a larger firm, integration in progress, culture clash expected"
Output:
{
  "workload_multiplier": 1.2,
  "stress_gain_rate_multiplier": 5.0,
  "motivation_decay_rate_multiplier": 4.0,
  "shock_factor": 0.55,
  "hiring_active": false,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.2 — integration projects, duplicate process reconciliation, reporting overhead",
    "stress_gain_rate_multiplier": "5.0x — job security completely unknown, culture clash signals loss of identity",
    "motivation_decay_rate_multiplier": "4.0x — loyalty to old company broken; new culture not yet earned",
    "shock_factor": "0.55 — M&A is a company-wide event; senior and visible employees leave, cascade is strong",
    "hiring_active": "false — acquirers typically freeze hiring pending integration and redundancy audit"
  }
}
"""
    },
    {
        "query": "merger complete, redundant roles being eliminated, 8% headcount reduction",
        "content": """
User: "merger complete, redundant roles being eliminated, 8% headcount reduction"
Output:
{
  "workload_multiplier": 1.3,
  "stress_gain_rate_multiplier": 5.5,
  "motivation_decay_rate_multiplier": 4.5,
  "shock_factor": 0.6,
  "hiring_active": false,
  "layoff_ratio": 0.08,
  "duration_months": 6,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.3 — survivors absorb eliminated roles",
    "stress_gain_rate_multiplier": "5.5x — layoffs after merger = double uncertainty, panic-level stress",
    "motivation_decay_rate_multiplier": "4.5x — survivor guilt compounded by cultural disruption",
    "shock_factor": "0.6 — visible layoffs in already-uncertain environment, maximum contagion",
    "layoff_ratio": "0.08 — explicitly stated 8% headcount reduction",
    "duration_months": "6 — post-merger integration window"
  }
}
"""
    },
    {
        "query": "office relocating to a new city 40km away, no remote option offered",
        "content": """
User: "office relocating to a new city 40km away, no remote option offered"
Output:
{
  "workload_multiplier": 1.1,
  "stress_gain_rate_multiplier": 2.5,
  "motivation_decay_rate_multiplier": 3.0,
  "shock_factor": 0.45,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 6,
  "bonus": 0.0,
  "wlb_boost": -0.4,
  "_justification": {
    "workload_multiplier": "1.1 — commute time becomes a real productivity and energy drain",
    "stress_gain_rate_multiplier": "2.5x — life disruption, some employees cannot or will not relocate",
    "motivation_decay_rate_multiplier": "3.0x — forced relocation with no alternative reads as disregard for employee lives",
    "shock_factor": "0.45 — relocation is a clear decision forcing event; employees who cannot move resign, triggering peer discussion",
    "wlb_boost": "-0.4 — significant WLB degradation from commute and life disruption"
  }
}
"""
    },
    {
        "query": "company switches to a 4-day work week, same pay, Fridays off",
        "content": """
User: "company switches to a 4-day work week, same pay, Fridays off"
Output:
{
  "workload_multiplier": 0.8,
  "stress_gain_rate_multiplier": 0.5,
  "motivation_decay_rate_multiplier": 0.4,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.7,
  "_justification": {
    "workload_multiplier": "0.8 — 20% fewer working days, direct load reduction",
    "stress_gain_rate_multiplier": "0.5x — rest and recovery buffer dramatically reduces stress accumulation",
    "motivation_decay_rate_multiplier": "0.4x — strong positive signal; employees feel highly valued, motivation recovers faster",
    "shock_factor": "0.0 — positive policy, no contagion risk",
    "wlb_boost": "0.7 — full extra day of recovery is the single strongest WLB lever available"
  }
}
"""
    },
    {
        "query": "4-day week but same total work hours compressed into 4 days (10h/day)",
        "content": """
User: "4-day week but same total work hours compressed into 4 days (10h/day)"
Output:
{
  "workload_multiplier": 1.1,
  "stress_gain_rate_multiplier": 1.5,
  "motivation_decay_rate_multiplier": 0.8,
  "shock_factor": 0.1,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.3,
  "_justification": {
    "workload_multiplier": "1.1 — same hours compressed means less buffer; cognitive load per day increases",
    "stress_gain_rate_multiplier": "1.5x — 10h days increase daily fatigue despite the extra day off",
    "motivation_decay_rate_multiplier": "0.8x — 3-day weekend still perceived positively, partial motivation benefit retained",
    "wlb_boost": "0.3 — reduced from full 4-day benefit because hours are not reduced, only redistributed"
  }
}
"""
    },
    {
        "query": "all employees granted stock options vesting over 4 years",
        "content": """
User: "all employees granted stock options vesting over 4 years"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.85,
  "motivation_decay_rate_multiplier": 0.4,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 1.0,
  "wlb_boost": 0.0,
  "_justification": {
    "stress_gain_rate_multiplier": "0.85x — financial upside reduces anxiety, mild stress relief",
    "motivation_decay_rate_multiplier": "0.4x — ownership stake creates strong long-term retention anchor; employees feel invested in outcomes",
    "bonus": "1.0 — equity is a non-cash financial lever; maps to mid-range compensation signal",
    "wlb_boost": "0.0 — equity does not affect schedule or day-to-day workload"
  }
}
"""
    },
    {
        "query": "equity grants cancelled due to company financial difficulties",
        "content": """
User: "equity grants cancelled due to company financial difficulties"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 2.0,
  "motivation_decay_rate_multiplier": 3.5,
  "shock_factor": 0.45,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "stress_gain_rate_multiplier": "2.0x — cancellation signals financial instability, job security concern",
    "motivation_decay_rate_multiplier": "3.5x — broken promise on equity is a deep trust violation, especially for employees who traded salary for equity",
    "shock_factor": "0.45 — financial instability signal spreads quickly, especially among senior employees who hold most equity"
  }
}
"""
    },
    {
        "query": "company in hypergrowth, doubling headcount over 6 months",
        "content": """
User: "company in hypergrowth, doubling headcount over 6 months"
Output:
{
  "workload_multiplier": 1.2,
  "stress_gain_rate_multiplier": 2.0,
  "motivation_decay_rate_multiplier": 0.7,
  "shock_factor": 0.2,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 6,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.2 — existing employees carry load while new hires ramp up; onboarding overhead",
    "stress_gain_rate_multiplier": "2.0x — pace of change is stressful; culture dilution is a concern",
    "motivation_decay_rate_multiplier": "0.7x — growth signals opportunity; promotion paths open up, employees feel upward momentum",
    "shock_factor": "0.2 — growth phase rarely triggers exits; mild contagion only from culture mismatch"
  }
}
"""
    },
    {
        "query": "travel budget eliminated, team perks removed, training budget cut to zero",
        "content": """
User: "travel budget eliminated, team perks removed, training budget cut to zero"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 1.3,
  "motivation_decay_rate_multiplier": 2.5,
  "shock_factor": 0.3,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "stress_gain_rate_multiplier": "1.3x — removal of perks signals financial distress, mild existential concern",
    "motivation_decay_rate_multiplier": "2.5x — loss of growth opportunities (training) and social bonding (perks/travel) degrades engagement significantly",
    "shock_factor": "0.3 — visible cuts generate peer discussion and speculation about further reductions"
  }
}
"""
    },
    {
        "query": "tools and software budget slashed — teams must drop paid tools and use free alternatives",
        "content": """
User: "tools and software budget slashed — teams must drop paid tools and use free alternatives"
Output:
{
  "workload_multiplier": 1.15,
  "stress_gain_rate_multiplier": 1.8,
  "motivation_decay_rate_multiplier": 2.0,
  "shock_factor": 0.2,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.15 — productivity loss from inferior tooling increases time-to-complete for same tasks",
    "stress_gain_rate_multiplier": "1.8x — frustration from degraded tools is a persistent daily stressor",
    "motivation_decay_rate_multiplier": "2.0x — being forced to work with inferior tools signals the company does not invest in its people"
  }
}
"""
    },
    {
        "query": "company introduces unlimited paid time off policy",
        "content": """
User: "company introduces unlimited paid time off policy"
Output:
{
  "workload_multiplier": 0.9,
  "stress_gain_rate_multiplier": 0.65,
  "motivation_decay_rate_multiplier": 0.5,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.5,
  "_justification": {
    "workload_multiplier": "0.9 — employees take more recovery time, slightly reducing sustained workload",
    "stress_gain_rate_multiplier": "0.65x — recovery buffer reduces chronic stress accumulation significantly",
    "motivation_decay_rate_multiplier": "0.5x — high trust signal; autonomy over time off is a strong retention anchor",
    "wlb_boost": "0.5 — substantial WLB improvement, though slightly less than 4-day week since usage is inconsistent across employees"
  }
}
"""
    },
    {
        "query": "mandatory mental health days — 2 extra paid days off per quarter for all staff",
        "content": """
User: "mandatory mental health days — 2 extra paid days off per quarter for all staff"
Output:
{
  "workload_multiplier": 0.95,
  "stress_gain_rate_multiplier": 0.75,
  "motivation_decay_rate_multiplier": 0.7,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.3,
  "_justification": {
    "workload_multiplier": "0.95 — 8 additional recovery days per year modestly reduces sustained load",
    "stress_gain_rate_multiplier": "0.75x — structured recovery reduces stress buildup; mandatory removes the guilt of taking leave",
    "motivation_decay_rate_multiplier": "0.7x — strong signal that company cares about wellbeing; morale improves",
    "wlb_boost": "0.3 — meaningful but bounded WLB gain; less than unlimited PTO since quantity is fixed"
  }
}
"""
    },
    {
        "query": "employee assistance program launched — free counselling, financial advice, legal support",
        "content": """
User: "employee assistance program launched — free counselling, financial advice, legal support"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.85,
  "motivation_decay_rate_multiplier": 0.85,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.1,
  "_justification": {
    "stress_gain_rate_multiplier": "0.85x — safety net reduces anxiety about personal and financial issues that bleed into work",
    "motivation_decay_rate_multiplier": "0.85x — company investment in employee welfare improves loyalty and engagement",
    "wlb_boost": "0.1 — marginal WLB benefit; addresses distress but does not change schedule"
  }
}
"""
    },
    {
        "query": "extended parental leave introduced — 6 months fully paid for all parents",
        "content": """
User: "extended parental leave introduced — 6 months fully paid for all parents"
Output:
{
  "workload_multiplier": 1.05,
  "stress_gain_rate_multiplier": 0.8,
  "motivation_decay_rate_multiplier": 0.5,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.4,
  "_justification": {
    "workload_multiplier": "1.05 — coverage gap when employees take leave adds marginal load on remaining team",
    "stress_gain_rate_multiplier": "0.8x — policy signals long-term employer commitment, reducing existential anxiety",
    "motivation_decay_rate_multiplier": "0.5x — one of the highest-signal retention benefits; deep loyalty driver, especially for parents and prospective parents",
    "wlb_boost": "0.4 — strong WLB signal even for employees not currently using it; company culture shift perceived positively"
  }
}
"""
    },
    {
        "query": "structured mentorship program launched with senior leaders, monthly 1-on-1s guaranteed",
        "content": """
User: "structured mentorship program launched with senior leaders, monthly 1-on-1s guaranteed"
Output:
{
  "workload_multiplier": 1.05,
  "stress_gain_rate_multiplier": 0.9,
  "motivation_decay_rate_multiplier": 0.6,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.05 — mentorship sessions add minor time overhead",
    "stress_gain_rate_multiplier": "0.9x — access to leadership reduces uncertainty and career anxiety",
    "motivation_decay_rate_multiplier": "0.6x — career visibility and development investment strongly counters motivation decay"
  }
}
"""
    },
    {
        "query": "public recognition program — monthly awards, peer nominations, company-wide announcements",
        "content": """
User: "public recognition program — monthly awards, peer nominations, company-wide announcements"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.9,
  "motivation_decay_rate_multiplier": 0.7,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "stress_gain_rate_multiplier": "0.9x — recognition culture mildly reduces anxiety and competitive tension",
    "motivation_decay_rate_multiplier": "0.7x — visible appreciation slows motivation decay; peer recognition is a powerful non-financial retention lever"
  }
}
"""
    },
    {
        "query": "clear promotion criteria published with defined timelines for each level",
        "content": """
User: "clear promotion criteria published with defined timelines for each level"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.85,
  "motivation_decay_rate_multiplier": 0.55,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "stress_gain_rate_multiplier": "0.85x — career path clarity reduces anxiety about future and fairness",
    "motivation_decay_rate_multiplier": "0.55x — knowing the rules of advancement is a powerful motivator; removes the arbitrariness that causes disengagement"
  }
}
"""
    },
    {
        "query": "layoffs of 10%, survivors get 15% salary increase and work from home option",
        "content": """
User: "layoffs of 10%, survivors get 15% salary increase and work from home option"
Output:
{
  "workload_multiplier": 1.25,
  "stress_gain_rate_multiplier": 3.5,
  "motivation_decay_rate_multiplier": 1.5,
  "shock_factor": 0.4,
  "hiring_active": false,
  "layoff_ratio": 0.1,
  "duration_months": 12,
  "bonus": 1.5,
  "wlb_boost": 0.3,
  "_justification": {
    "workload_multiplier": "1.25 — survivors absorb departed work despite compensation uplift",
    "stress_gain_rate_multiplier": "3.5x — layoff fear dominates even with pay raise; job security concern persists",
    "motivation_decay_rate_multiplier": "1.5x — 15% raise + WFH partially offsets survivor guilt but cannot fully counter it",
    "shock_factor": "0.4 — departures are visible; raise cushions but does not eliminate contagion",
    "layoff_ratio": "0.1 — explicitly stated 10% reduction",
    "bonus": "1.5 — 15% raise maps to strong financial retention signal",
    "wlb_boost": "0.3 — WFH option adds meaningful but not maximum WLB benefit"
  }
}
"""
    },
    {
        "query": "hiring freeze combined with promotion freeze for 18 months, but 8% raise given to all",
        "content": """
User: "hiring freeze combined with promotion freeze for 18 months, but 8% raise given to all"
Output:
{
  "workload_multiplier": 1.2,
  "stress_gain_rate_multiplier": 2.5,
  "motivation_decay_rate_multiplier": 2.5,
  "shock_factor": 0.3,
  "hiring_active": false,
  "layoff_ratio": 0.0,
  "duration_months": 18,
  "bonus": 0.8,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.2 — hiring freeze means no backfill; load increases over 18 months",
    "stress_gain_rate_multiplier": "2.5x — dual freeze signals stagnation; raise does not address growth anxiety",
    "motivation_decay_rate_multiplier": "2.5x — promotion freeze is the dominant driver; 8% raise is appreciated but career stagnation overrides financial comfort for growth-oriented employees",
    "shock_factor": "0.3 — high performers most likely to exit; their departures visible to peers",
    "bonus": "0.8 — 8% raise sits between CoL (0.5) and strong retention signal (1.5)",
    "duration_months": "18 — explicitly stated"
  }
}
"""
    },
    {
        "query": "reduce everyone's workload by 10% for the next quarter, no scope added",
        "content": """
User: "reduce everyone's workload by 10% for the next quarter, no scope added"
Output:
{
  "workload_multiplier": 0.9,
  "stress_gain_rate_multiplier": 0.75,
  "motivation_decay_rate_multiplier": 0.8,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 3,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "0.9 — explicit 10% reduction in scope/tasks",
    "stress_gain_rate_multiplier": "0.75x — mild load relief lowers stress accumulation rate",
    "motivation_decay_rate_multiplier": "0.8x — breathing room improves engagement slightly",
    "wlb_boost": "0.0 — scope cut, not a schedule change; hours unchanged",
    "duration_months": "3 — user said next quarter"
  }
}
"""
    },
    {
        "query": "cut workload by 20% permanently — non-critical projects deprioritized",
        "content": """
User: "cut workload by 20% permanently — non-critical projects deprioritized"
Output:
{
  "workload_multiplier": 0.8,
  "stress_gain_rate_multiplier": 0.55,
  "motivation_decay_rate_multiplier": 0.6,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.1,
  "_justification": {
    "workload_multiplier": "0.8 — 20% explicit reduction, sustained",
    "stress_gain_rate_multiplier": "0.55x — meaningful deload; employees recover bandwidth and mental energy",
    "motivation_decay_rate_multiplier": "0.6x — reduced pressure allows focus on quality, which improves engagement",
    "wlb_boost": "0.1 — slight WLB gain from reduced cognitive load even without schedule change"
  }
}
"""
    },
    {
        "query": "workload reduced by 30% — team descoped from two major projects after post-crunch recovery",
        "content": """
User: "workload reduced by 30% — team descoped from two major projects after post-crunch recovery"
Output:
{
  "workload_multiplier": 0.7,
  "stress_gain_rate_multiplier": 0.45,
  "motivation_decay_rate_multiplier": 0.5,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 6,
  "bonus": 0.0,
  "wlb_boost": 0.15,
  "_justification": {
    "workload_multiplier": "0.7 — significant scope reduction, post-crunch recovery mode",
    "stress_gain_rate_multiplier": "0.45x — strong decompression; chronic stress from crunch begins reversing",
    "motivation_decay_rate_multiplier": "0.5x — recovery period restores motivation; employees feel the company acknowledged the overload",
    "wlb_boost": "0.15 — moderate WLB gain from reduced cognitive pressure, even without schedule change"
  }
}
"""
    },
    {
        "query": "company enters maintenance mode — workload cut by 50%, only critical systems supported",
        "content": """
User: "company enters maintenance mode — workload cut by 50%, only critical systems supported"
Output:
{
  "workload_multiplier": 0.5,
  "stress_gain_rate_multiplier": 0.3,
  "motivation_decay_rate_multiplier": 0.35,
  "shock_factor": 0.15,
  "hiring_active": false,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.2,
  "_justification": {
    "workload_multiplier": "0.5 — 50% reduction to maintenance-only pace",
    "stress_gain_rate_multiplier": "0.3x — near-recovery ops; stress accumulation nearly halted",
    "motivation_decay_rate_multiplier": "0.35x — very low pressure environment; motivation stabilizes strongly",
    "shock_factor": "0.15 — maintenance mode signals stagnation to ambitious employees; some low-level concern about company direction",
    "hiring_active": "false — maintenance mode implies growth is paused",
    "wlb_boost": "0.2 — reduced load frees personal time even within standard hours"
  }
}
"""
    },
    {
        "query": "emergency descope — workload cut by 60%, team down to skeleton crew operations",
        "content": """
User: "emergency descope — workload cut by 60%, team down to skeleton crew operations"
Output:
{
  "workload_multiplier": 0.4,
  "stress_gain_rate_multiplier": 0.25,
  "motivation_decay_rate_multiplier": 0.3,
  "shock_factor": 0.25,
  "hiring_active": false,
  "layoff_ratio": 0.0,
  "duration_months": 3,
  "bonus": 0.0,
  "wlb_boost": 0.25,
  "_justification": {
    "workload_multiplier": "0.4 — extreme reduction; skeleton operations only",
    "stress_gain_rate_multiplier": "0.25x — minimal work means minimal stress accumulation",
    "motivation_decay_rate_multiplier": "0.3x — very low pressure; but boredom and ambiguity about company future may set in",
    "shock_factor": "0.25 — extreme cuts signal instability; ambitious employees may self-select out",
    "hiring_active": "false — skeleton ops do not involve expansion",
    "wlb_boost": "0.25 — significant personal time freed up from reduced operations"
  }
}
"""
    },
    {
        "query": "monthly team outing — company-funded dinner or activity every month",
        "content": """
User: "monthly team outing — company-funded dinner or activity every month"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.85,
  "motivation_decay_rate_multiplier": 0.7,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.1,
  "_justification": {
    "stress_gain_rate_multiplier": "0.85x — regular social bonding provides a recurring stress buffer",
    "motivation_decay_rate_multiplier": "0.7x — team cohesion is a strong intrinsic motivator; belonging slows disengagement",
    "wlb_boost": "0.1 — minor WLB improvement from social connection and feeling valued outside of work tasks"
  }
}
"""
    },
    {
        "query": "quarterly offsite trips — 2-day company retreat every quarter, travel and accommodation paid",
        "content": """
User: "quarterly offsite trips — 2-day company retreat every quarter, travel and accommodation paid"
Output:
{
  "workload_multiplier": 0.95,
  "stress_gain_rate_multiplier": 0.7,
  "motivation_decay_rate_multiplier": 0.55,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.25,
  "_justification": {
    "workload_multiplier": "0.95 — offsite days are breaks from normal work; slight effective load reduction",
    "stress_gain_rate_multiplier": "0.7x — quarterly breaks disrupt stress accumulation cycle meaningfully",
    "motivation_decay_rate_multiplier": "0.55x — retreats rebuild team identity and energy; strong morale reset",
    "wlb_boost": "0.25 — paid travel and time away from office is a genuine WLB signal, not just a gesture"
  }
}
"""
    },
    {
        "query": "post-project celebration — team dinner and bonus after every major project delivery",
        "content": """
User: "post-project celebration — team dinner and bonus after every major project delivery"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.8,
  "motivation_decay_rate_multiplier": 0.5,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.8,
  "wlb_boost": 0.05,
  "_justification": {
    "stress_gain_rate_multiplier": "0.8x — anticipation of reward reduces stress during crunch; post-delivery relief resets baseline",
    "motivation_decay_rate_multiplier": "0.5x — recognized outcomes are the single strongest intrinsic motivator; effort → reward loop retains motivation powerfully",
    "bonus": "0.8 — project bonus maps to modest but meaningful financial reward signal",
    "wlb_boost": "0.05 — celebration dinner is a minor social WLB gain, not a structural change"
  }
}
"""
    },
    {
        "query": "weekly team lunch paid by company every Friday",
        "content": """
User: "weekly team lunch paid by company every Friday"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.9,
  "motivation_decay_rate_multiplier": 0.85,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.05,
  "_justification": {
    "stress_gain_rate_multiplier": "0.9x — weekly social ritual provides a small but consistent stress buffer",
    "motivation_decay_rate_multiplier": "0.85x — low-impact but consistent belonging signal; prevents passive disengagement",
    "wlb_boost": "0.05 — negligible WLB gain; gesture is social, not structural"
  }
}
"""
    },
    {
        "query": "annual company hackathon — 2 days, all employees, prizes and recognition for winners",
        "content": """
User: "annual company hackathon — 2 days, all employees, prizes and recognition for winners"
Output:
{
  "workload_multiplier": 0.95,
  "stress_gain_rate_multiplier": 0.85,
  "motivation_decay_rate_multiplier": 0.6,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.1,
  "_justification": {
    "workload_multiplier": "0.95 — 2 days of creative freedom away from normal work reduces effective annual load marginally",
    "stress_gain_rate_multiplier": "0.85x — creative autonomy and fun competition is a strong one-time stress reset",
    "motivation_decay_rate_multiplier": "0.6x — intrinsic motivation spike from autonomy and recognition; effect lasts weeks post-event",
    "wlb_boost": "0.1 — structured break from routine with social energy provides minor WLB lift"
  }
}
"""
    },
    {
        "query": "company provides free gym membership and on-site fitness classes for all employees",
        "content": """
User: "company provides free gym membership and on-site fitness classes for all employees"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.8,
  "motivation_decay_rate_multiplier": 0.8,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.15,
  "_justification": {
    "stress_gain_rate_multiplier": "0.8x — physical exercise is one of the most evidence-backed stress reducers; sustained effect for active users",
    "motivation_decay_rate_multiplier": "0.8x — health investment signals company care; improves energy and mood which slows disengagement",
    "wlb_boost": "0.15 — physical wellness benefit has a real WLB component; reduces time and cost burden of external gym"
  }
}
"""
    },
    {
        "query": "free daily catered meals provided for all on-site employees",
        "content": """
User: "free daily catered meals provided for all on-site employees"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.9,
  "motivation_decay_rate_multiplier": 0.85,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.1,
  "_justification": {
    "stress_gain_rate_multiplier": "0.9x — removal of daily friction (lunch planning, cost, time) reduces low-grade daily stress",
    "motivation_decay_rate_multiplier": "0.85x — perk signals investment in employee experience; modest but consistent belonging signal",
    "wlb_boost": "0.1 — saves personal time and money; minor but real daily quality-of-life improvement"
  }
}
"""
    },
    {
        "query": "end-of-year company party — catered event, open bar, plus year-end cash bonus",
        "content": """
User: "end-of-year company party — catered event, open bar, plus year-end cash bonus"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.8,
  "motivation_decay_rate_multiplier": 0.5,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 1.0,
  "wlb_boost": 0.05,
  "_justification": {
    "stress_gain_rate_multiplier": "0.8x — annual celebration provides a strong year-end emotional reset",
    "motivation_decay_rate_multiplier": "0.5x — cash bonus is the dominant signal here; party amplifies the recognition but bonus drives the retention effect",
    "bonus": "1.0 — year-end cash bonus is a meaningful mid-range financial reward",
    "wlb_boost": "0.05 — party is social, not structural WLB change"
  }
}
"""
    },
    {
        "query": "learning and development budget — each employee gets $2000/year for courses, conferences, or books",
        "content": """
User: "learning and development budget — each employee gets $2000/year for courses, conferences, or books"
Output:
{
  "workload_multiplier": 1.05,
  "stress_gain_rate_multiplier": 0.85,
  "motivation_decay_rate_multiplier": 0.5,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.0,
  "_justification": {
    "workload_multiplier": "1.05 — learning activities add marginal time overhead on top of regular work",
    "stress_gain_rate_multiplier": "0.85x — growth investment reduces career anxiety and stagnation stress",
    "motivation_decay_rate_multiplier": "0.5x — personal development budget is a strong retention signal; employees feel the company is investing in their future"
  }
}
"""
    },
    {
        "query": "company introduces bring-your-pet-to-work Fridays",
        "content": """
User: "company introduces bring-your-pet-to-work Fridays"
Output:
{
  "workload_multiplier": 1.0,
  "stress_gain_rate_multiplier": 0.88,
  "motivation_decay_rate_multiplier": 0.9,
  "shock_factor": 0.0,
  "hiring_active": true,
  "layoff_ratio": 0.0,
  "duration_months": 12,
  "bonus": 0.0,
  "wlb_boost": 0.08,
  "_justification": {
    "stress_gain_rate_multiplier": "0.88x — animal presence measurably reduces cortisol; the effect is real but bounded to Fridays",
    "motivation_decay_rate_multiplier": "0.9x — quirky perk signals positive culture; modest belonging improvement",
    "wlb_boost": "0.08 — personal and work life blend positively; removes the guilt of leaving pets at home"
  }
}
"""
    },
]
