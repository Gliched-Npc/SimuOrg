import { useEffect, useState } from 'react';
import axios from 'axios';

function App() {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    axios.get('http://127.0.0.1:8000/api/sim/test-data')
      .then(response => {
        setEmployees(response.data);
        setLoading(false);
      })
      .catch(err => {
        console.error("Error fetching data:", err);
        setError("Failed to connect to Backend (Is it running?)");
        setLoading(false);
      });
  }, []);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-indigo-950 text-white font-sans">
      {/* Subtle texture overlay */}
      <div className="fixed inset-0 opacity-[0.03] pointer-events-none"
        style={{ backgroundImage: 'url("data:image/svg+xml,%3Csvg width=\'60\' height=\'60\' viewBox=\'0 0 60 60\' xmlns=\'http://www.w3.org/2000/svg\'%3E%3Cg fill=\'none\' fill-rule=\'evenodd\'%3E%3Cg fill=\'%23ffffff\' fill-opacity=\'1\'%3E%3Cpath d=\'M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z\'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")' }}>
      </div>

      <div className="relative max-w-5xl mx-auto px-6 py-12">
        {/* Header */}
        <div className="mb-10">
          <div className="flex items-center gap-3 mb-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center shadow-lg shadow-indigo-500/30">
              <span className="text-lg font-bold">S</span>
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-white via-indigo-200 to-indigo-400 bg-clip-text text-transparent">
              SimuOrg Dashboard
            </h1>
          </div>
          <p className="text-slate-400 text-lg ml-[52px]">
            Employee data from the simulation engine
          </p>
        </div>

        {/* Status Cards Row */}
        <div className="grid grid-cols-3 gap-4 mb-8">
          <div className="bg-slate-800/60 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-5">
            <p className="text-slate-400 text-sm font-medium uppercase tracking-wider">Status</p>
            <p className="text-2xl font-bold text-emerald-400 mt-1">
              {loading ? '...' : error ? '⚠️ Offline' : '● Online'}
            </p>
          </div>
          <div className="bg-slate-800/60 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-5">
            <p className="text-slate-400 text-sm font-medium uppercase tracking-wider">Employees Loaded</p>
            <p className="text-2xl font-bold text-white mt-1">
              {loading ? '...' : employees.length}
            </p>
          </div>
          <div className="bg-slate-800/60 backdrop-blur-sm border border-slate-700/50 rounded-2xl p-5">
            <p className="text-slate-400 text-sm font-medium uppercase tracking-wider">Data Source</p>
            <p className="text-2xl font-bold text-indigo-400 mt-1">PostgreSQL</p>
          </div>
        </div>

        {/* Loading State */}
        {loading && (
          <div className="flex items-center justify-center py-20">
            <div className="animate-spin rounded-full h-10 w-10 border-2 border-indigo-400 border-t-transparent mr-4"></div>
            <p className="text-slate-300 text-lg">Loading data from backend...</p>
          </div>
        )}

        {/* Error State */}
        {error && (
          <div className="bg-red-500/10 border border-red-500/30 rounded-2xl p-6 text-center">
            <p className="text-red-400 text-xl font-semibold">{error}</p>
            <p className="text-red-400/60 mt-2">Make sure uvicorn is running on port 8000</p>
          </div>
        )}

        {/* Data Table */}
        {!loading && !error && (
          <div className="bg-slate-800/40 backdrop-blur-sm border border-slate-700/50 rounded-2xl overflow-hidden shadow-2xl shadow-black/20">
            <div className="px-6 py-4 border-b border-slate-700/50">
              <h2 className="text-lg font-semibold text-slate-200">Employee Records</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-700/30">
                    <th className="px-6 py-4 text-left text-xs font-bold text-slate-300 uppercase tracking-wider">ID</th>
                    <th className="px-6 py-4 text-left text-xs font-bold text-slate-300 uppercase tracking-wider">Department</th>
                    <th className="px-6 py-4 text-left text-xs font-bold text-slate-300 uppercase tracking-wider">Role</th>
                    <th className="px-6 py-4 text-left text-xs font-bold text-slate-300 uppercase tracking-wider">Monthly Income</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700/30">
                  {employees.map((emp) => (
                    <tr key={emp.employee_id} className="hover:bg-indigo-500/5 transition-colors duration-150">
                      <td className="px-6 py-4 text-sm font-mono text-slate-300">{emp.employee_id}</td>
                      <td className="px-6 py-4">
                        <span className="text-sm font-medium text-slate-200">{emp.department}</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm text-slate-300">{emp.job_role}</span>
                      </td>
                      <td className="px-6 py-4">
                        <span className="text-sm font-semibold font-mono text-emerald-400">
                          ${(emp.monthly_income ?? emp.MonthlyIncome ?? 0).toLocaleString()}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="mt-8 text-center">
          <p className="text-slate-600 text-sm">SimuOrg v1.0 • Powered by FastAPI + React</p>
        </div>
      </div>
    </div>
  );
}

export default App;
