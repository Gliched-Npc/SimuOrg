import { snakeToTitle, toPercent } from '../utils/formatters';
import { CHART_COLORS } from '../utils/constants';

function SimulationCard({ policyName, avgAttrition, retentionRate }) {
    return (
        <div className="sim-card">
            <h3>{snakeToTitle(policyName)}</h3>
            <div className="sim-card-stats">
                <div className="stat">
                    <span className="stat-label">Avg Attrition</span>
                    <span className="stat-value" style={{ color: CHART_COLORS.danger }}>
                        {toPercent(avgAttrition)}
                    </span>
                </div>
                <div className="stat">
                    <span className="stat-label">Retention Rate</span>
                    <span className="stat-value" style={{ color: CHART_COLORS.success }}>
                        {toPercent(retentionRate)}
                    </span>
                </div>
            </div>
        </div>
    );
}

export default SimulationCard;
