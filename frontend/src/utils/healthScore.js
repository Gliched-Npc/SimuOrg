/**
 * Single source of truth for health score thresholds.
 * >= 75  → Green  (Healthy)
 * 45–74  → Yellow (At Risk)
 * < 45   → Red    (Critical)
 */

export const HEALTH_GREEN  = 65
export const HEALTH_YELLOW = 45

/**
 * @param {number|null|undefined} score
 * @returns {{ color: string, label: string, deltaDir: 'up'|'neutral'|'down' }}
 */
export function healthMeta(score) {
  if (score == null || isNaN(score)) {
    return { color: 'rgba(188,111,241,0.4)', label: 'No Data', deltaDir: 'neutral' }
  }
  if (score >= HEALTH_GREEN) {
    return { color: '#4ade80', label: 'Healthy',   deltaDir: 'up'   }
  }
  if (score >= HEALTH_YELLOW) {
    return { color: '#fbbf24', label: 'At Risk',   deltaDir: 'neutral' }
  }
  return   { color: '#f87171', label: 'Critical',  deltaDir: 'down' }
}
