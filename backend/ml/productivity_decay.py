# backend/ml/productivity_model.py

def productivity_decay(stress: float, fatigue: float, 
                       job_satisfaction: float, work_life_balance: float) -> float:
    """
    Returns a productivity score between 0.0 and 1.0
    Higher stress and fatigue = lower productivity
    Higher satisfaction and work life balance = higher productivity
    """
    score = 1.0

    score -= stress * 0.30
    score -= fatigue * 0.20
    score += (job_satisfaction - 3) * 0.10
    score += (work_life_balance - 3) * 0.05

    # Keep it between 0 and 1
    return max(0.0, min(1.0, score))