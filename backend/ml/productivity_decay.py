# backend/ml/productivity_model.py

def productivity_decay(stress: float, fatigue: float, 
                       job_satisfaction: float, work_life_balance: float,
                       workload_multiplier: float = 1.0) -> float:
    """
    Returns a productivity score. Includes 'Crunch Culture' mechanics.
    - High workload temporarily boosts productivity if fatigue is low (hero effort).
    - As fatigue rises, the crunch collapses into severe productivity decay.
    """
    
    # Base productivity component
    base_score = 1.0
    base_score -= stress * 0.30
    base_score += (job_satisfaction - 3) * 0.10
    base_score += (work_life_balance - 3) * 0.05
    
    # Crunch Culture Mechanic
    if workload_multiplier > 1.0:
        # Boost productivity based on workload pressure
        crunch_boost = (workload_multiplier - 1.0) * 0.8 
        
        # But fatigue aggressively destroys the crunch effort
        # A fresh employee thrives on crunch, a tired employee crashes.
        fatigue_penalty = fatigue * (workload_multiplier * 1.5) 
        
        score = base_score + crunch_boost - fatigue_penalty
    else:
        # Normal operations
        score = base_score - (fatigue * 0.20)

    # Allow temporary spikes up to 1.5x, floor at 0.1x
    return max(0.1, min(1.5, score))