import Navbar from '../components/Navbar';

function SimulationResults() {
    return (
        <div className="sim-results-page">
            <Navbar />
            <h1>Simulation Results</h1>
            <p>Run a simulation and view attrition predictions here.</p>

            {/* TODO: Add simulation controls and result charts */}
            <div className="placeholder-card">
                <p>Simulation controls and visualization charts will appear here.</p>
            </div>
        </div>
    );
}

export default SimulationResults;
