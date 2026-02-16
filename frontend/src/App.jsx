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

  const deptColor = (dept) => {
    const colors = {
      'Sales': 'bg-blue-500/15 text-blue-300 ring-blue-500/20',
      'Research & Development': 'bg-violet-500/15 text-violet-300 ring-violet-500/20',
      'Human Resources': 'bg-amber-500/15 text-amber-300 ring-amber-500/20',
    };
    return colors[dept] || 'bg-slate-500/15 text-slate-300 ring-slate-500/20';
  };

  return (
    <div className="min-h-screen bg-[#0a0e1a] text-white font-sans antialiased">
      {/* Ambient glow */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-indigo-600/8 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="fixed bottom-0 right-0 w-[400px] h-[400px] bg-purple-600/6 rounded-full blur-[100px] pointer-events-none"></div>

      <div className="relative max-w-5xl mx-auto px-8 py-14">

        {/* ─── Header ─── */}
        <header className="mb-12 text-center">
          <div className="flex items-center justify-center gap-4 mb-3">
            <div className="w-11 h-11 rounded-2xl bg-gradient-to-br from-indigo-500 to-purple-500 flex items-center justify-center shadow-lg shadow-indigo-500/25">
              <span className="text-base font-bold tracking-tight">SO</span>
            </div>
            <div>
              <h1 className="text-3xl font-bold tracking-tight text-white leading-none">
                SimuOrg
              </h1>
              <p className="text-[13px] text-slate-500 font-medium tracking-wide mt-0.5">
                EMPLOYEE INTELLIGENCE DASHBOARD
              </p>
            </div>
          </div>
        </header>

        {/* ─── Metric Cards ─── */}
        <div className="grid grid-cols-3 gap-5 mb-10">
          <div className="group bg-white/[0.04] hover:bg-white/[0.06] border border-white/[0.06] rounded-2xl p-6 transition-all duration-300 flex flex-col items-center justify-center">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.1em] mb-3">Engine Status</p>
            <div className="flex items-center justify-center gap-2.5">
              <span className={`inline-block w-2.5 h-2.5 rounded-full ${loading ? 'bg-amber-400 animate-pulse' : error ? 'bg-red-400' : 'bg-emerald-400'} shadow-lg ${!loading && !error ? 'shadow-emerald-400/40' : ''}`}></span>
              <span className="text-xl font-semibold text-white leading-none">
                {loading ? 'Connecting' : error ? 'Offline' : 'Online'}
              </span>
            </div>
          </div>
          <div className="group bg-white/[0.04] hover:bg-white/[0.06] border border-white/[0.06] rounded-2xl p-6 transition-all duration-300 flex flex-col items-center justify-center">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.1em] mb-3">Records Loaded</p>
            <span className="text-xl font-semibold text-white leading-none">
              {loading ? '—' : employees.length}
            </span>
          </div>
          <div className="group bg-white/[0.04] hover:bg-white/[0.06] border border-white/[0.06] rounded-2xl p-6 transition-all duration-300 flex flex-col items-center justify-center">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-[0.1em] mb-3">Data Source</p>
            <span className="text-xl font-semibold text-white leading-none">PostgreSQL</span>
          </div>
        </div>

        {/* ─── Loading ─── */}
        {loading && (
          <div className="flex flex-col items-center justify-center py-24 gap-4">
            <div className="w-8 h-8 border-2 border-indigo-500/30 border-t-indigo-400 rounded-full animate-spin"></div>
            <p className="text-sm text-slate-500 font-medium">Fetching employee records...</p>
          </div>
        )}

        {/* ─── Error ─── */}
        {error && (
          <div className="bg-red-500/[0.07] border border-red-500/20 rounded-2xl px-8 py-6 text-center">
            <p className="text-red-300 text-base font-semibold mb-1">{error}</p>
            <p className="text-red-400/50 text-sm">Ensure <code className="font-mono text-red-300/60 bg-red-500/10 px-1.5 py-0.5 rounded text-xs">uvicorn</code> is running on port 8000</p>
          </div>
        )}

        {/* ─── Data Table ─── */}
        {!loading && !error && (
          <div className="bg-white/[0.03] border border-white/[0.06] rounded-2xl overflow-hidden">
            {/* Table Header Bar */}
            <div className="flex items-center justify-between px-7 py-5 border-b border-white/[0.06]">
              <h2 className="text-base font-semibold text-slate-200 tracking-tight text-center">Employee Records</h2>
              <span className="text-xs font-medium text-slate-500 bg-white/[0.05] px-3 py-1 rounded-full">
                {employees.length} results
              </span>
            </div>

            {/* Table */}
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/[0.04]">
                  <th className="px-7 py-4 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-[0.08em]">ID</th>
                  <th className="px-7 py-4 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-[0.08em]">Department</th>
                  <th className="px-7 py-4 text-left text-[11px] font-semibold text-slate-500 uppercase tracking-[0.08em]">Role</th>
                  <th className="px-7 py-4 text-right text-[11px] font-semibold text-slate-500 uppercase tracking-[0.08em]">Monthly Income</th>
                </tr>
              </thead>
              <tbody>
                {employees.map((emp, i) => (
                  <tr
                    key={emp.employee_id}
                    className={`group hover:bg-indigo-500/[0.04] transition-colors duration-200 ${i !== employees.length - 1 ? 'border-b border-white/[0.03]' : ''
                      }`}
                  >
                    <td className="px-7 py-4">
                      <span className="text-sm font-mono font-medium text-slate-400">
                        #{String(emp.employee_id).padStart(4, '0')}
                      </span>
                    </td>
                    <td className="px-7 py-4">
                      <span className={`inline-flex items-center text-xs font-semibold px-2.5 py-1 rounded-full ring-1 ring-inset ${deptColor(emp.department)}`}>
                        {emp.department}
                      </span>
                    </td>
                    <td className="px-7 py-4">
                      <span className="text-sm text-slate-300 font-medium">{emp.job_role}</span>
                    </td>
                    <td className="px-7 py-4 text-right">
                      <span className="text-sm font-mono font-semibold text-emerald-400">
                        ${(emp.monthly_income ?? emp.MonthlyIncome ?? 0).toLocaleString()}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* ─── Footer ─── */}
        <footer className="mt-10 text-center">
          <p className="text-xs text-slate-600 font-medium tracking-wide">
            SimuOrg v1.0 &nbsp;·&nbsp; FastAPI &nbsp;·&nbsp; React &nbsp;·&nbsp; PostgreSQL
          </p>
        </footer>
      </div>
    </div>
  );
}

export default App;
