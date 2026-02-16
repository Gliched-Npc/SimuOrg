import { useState, useEffect } from 'react';
import { fetchTestData } from '../services/api';
import Navbar from '../components/Navbar';

function Dashboard() {
    const [employees, setEmployees] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState('');

    useEffect(() => {
        const loadData = async () => {
            try {
                const res = await fetchTestData();
                setEmployees(res.data);
            } catch (err) {
                setError('Failed to load employee data.');
            } finally {
                setLoading(false);
            }
        };
        loadData();
    }, []);

    return (
        <div className="dashboard-page">
            <Navbar />
            <h1>Dashboard</h1>

            {loading && <p>Loading data...</p>}
            {error && <p className="error-msg">{error}</p>}

            {!loading && !error && (
                <div className="data-grid">
                    <h2>Sample Employees</h2>
                    <table>
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Name</th>
                                <th>Department</th>
                                <th>Satisfaction</th>
                            </tr>
                        </thead>
                        <tbody>
                            {employees.map((emp) => (
                                <tr key={emp.id}>
                                    <td>{emp.id}</td>
                                    <td>{emp.name || 'N/A'}</td>
                                    <td>{emp.department || 'N/A'}</td>
                                    <td>{emp.satisfaction_score ?? 'N/A'}</td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

export default Dashboard;
