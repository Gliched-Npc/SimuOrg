import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Users, TrendingDown, Star, Activity, Server, Database, Clock, Zap } from 'lucide-react'
import KpiCard from '../components/KpiCard'
import StatusBadge from '../components/StatusBadge'
import { getEmployees, getOrchestrateStatus } from '../services/api'

// ── Helpers ────────────────────────────────────────────────
const timeAgo = (ts) => {
  const diff = Date.now() - ts
  if (diff < 60000)  return `${Math.floor(diff/1000)}s ago`
  if (diff < 3600000) return `${Math.floor(diff/60000)}m ago`
  if (diff < 86400000) return `${Math.floor(diff/3600000)}h ago`
  return `${Math.floor(diff/86400000)}d ago`
}

export default function Dashboard() {
  const navigate = useNavigate()
  const [employees, setEmployees] = useState([])
  const [jobHistory, setJobHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [backendOk, setBackendOk] = useState(null)

  useEffect(() => {
    // Load employees + check backend health
    getEmployees()
      .then(({ data }) => {
        setEmployees(Array.isArray(data) ? data : [])
        setBackendOk(true)
      })
      .catch(() => setBackendOk(false))
      .finally(() => setLoading(false))

    // Load job history from localStorage and fetch statuses
    const stored = JSON.parse(localStorage.getItem('simuorg_job_history') || '[]')
    Promise.all(
      stored.map(async (item) => {
        try {
          const { data } = await getOrchestrateStatus(item.job_id)
          const analytics = data.result?.briefing?.analytics
          return { 
            ...item, 
            status: data.status, 
            health_score: analytics?.health_score ?? null,
            headcount: analytics?.headcount?.end ?? null,
            attrition: analytics?.attrition?.annual_pct ?? null,
            satisfaction: analytics?.metrics?.satisfaction?.end ?? null,
          }
        } catch {
          return { ...item, status: 'failed' }
        }
      })
    ).then(setJobHistory)
  }, [])

  // ── Derived KPIs ────────────────────────────────────────
  const baseEmp = employees.length
  const baseAttr = baseEmp > 0 ? (employees.filter(e => e.attrition === 'Yes').length / baseEmp) * 100 : 0
  const baseSat = baseEmp > 0 ? employees.reduce((s, e) => s + (e.job_satisfaction || 0), 0) / baseEmp : 0

  const latestSim = jobHistory.find(j => j.status === 'completed')

  const totalEmpDisplay = latestSim?.headcount ? latestSim.headcount.toLocaleString() : (loading ? '…' : baseEmp.toLocaleString())
  const attritionDisplay = latestSim?.attrition ? latestSim.attrition.toFixed(1) : (loading ? '…' : baseAttr.toFixed(1))
  const avgSatDisplay = latestSim?.satisfaction ? latestSim.satisfaction.toFixed(2) : (loading ? '…' : baseSat.toFixed(2))

  const lastHealth = latestSim?.health_score ?? '—'

  return (
    <div style={{ animation: 'fadeIn 0.4s ease', maxWidth: 1200, margin: '0 auto' }}>
      {/* ── Page Header ───────────────────────────────────── */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h1 className="page-title">Dashboard</h1>
        <p className="page-sub">Organisational health at a glance (Showing Pre/Post Simulation Metrics)</p>
      </div>

      {/* ── KPI Row ───────────────────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))',
        gap: '1rem',
        marginBottom: '2rem',
      }}>
        <KpiCard
          label={latestSim ? "Projected Employees" : "Total Employees"}
          value={totalEmpDisplay}
          icon={Users}
          color="purple"
          delta={latestSim ? 'Post-Simulation' : undefined}
          deltaDir={latestSim ? (latestSim.headcount > baseEmp ? 'up' : 'down') : undefined}
        />
        <KpiCard
          label={latestSim ? "Projected Attrition" : "Attrition Rate"}
          value={`${attritionDisplay}%`}
          icon={TrendingDown}
          color="rose"
          deltaDir={parseFloat(attritionDisplay) > 15 ? 'down' : 'up'}
          delta={parseFloat(attritionDisplay) > 15 ? 'Above threshold' : 'Within range'}
        />
        <KpiCard
          label={latestSim ? "Projected Satisfaction" : "Avg Satisfaction"}
          value={`${avgSatDisplay} / 4`}
          icon={Star}
          color="amber"
          delta={latestSim ? 'Post-Simulation' : undefined}
          deltaDir={latestSim ? (latestSim.satisfaction > baseSat ? 'up' : 'down') : undefined}
        />
        <KpiCard
          label="Last Health Score"
          value={lastHealth === '—' ? '—' : `${lastHealth} / 100`}
          icon={Activity}
          color="emerald"
          delta={lastHealth !== '—' ? (lastHealth >= 70 ? 'Good standing' : 'Needs attention') : undefined}
          deltaDir={lastHealth !== '—' ? (lastHealth >= 70 ? 'up' : 'down') : null}
        />
      </div>

      {/* ── Bottom Row: Recent Jobs + System Status ────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'minmax(0, 1fr) minmax(280px, 340px)',
        gap: '1.5rem',
        alignItems: 'start',
      }}>

        {/* Recent Simulations Table */}
        <div className="glass-card" style={{ overflow: 'hidden' }}>
          <div style={{ padding: '1.5rem 1.75rem', borderBottom: '1px solid rgba(188,111,241,0.1)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h2 style={{ fontSize: '1rem', fontWeight: 700, color: '#fff' }}>Recent Simulations</h2>
                <p style={{ fontSize: '0.78rem', color: 'rgba(188,111,241,0.6)', marginTop: 3 }}>
                  Latest policy orchestrations
                </p>
              </div>
              <button
                onClick={() => navigate('/simulate')}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '0.45rem 1rem', borderRadius: 8,
                  background: 'linear-gradient(135deg, #892CDC, #52057B)',
                  border: '1px solid rgba(188,111,241,0.3)',
                  color: '#fff', fontSize: '0.8rem', fontWeight: 700,
                  cursor: 'pointer', boxShadow: '0 4px 16px rgba(137,44,220,0.3)',
                }}
              >
                <Zap size={14} /> New Simulation
              </button>
            </div>
          </div>

          {jobHistory.length === 0 ? (
            <div style={{
              padding: '3rem 2rem', textAlign: 'center',
              color: 'rgba(188,111,241,0.4)', fontSize: '0.9rem',
            }}>
              <Zap size={32} style={{ margin: '0 auto 1rem', display: 'block', opacity: 0.3 }} />
              No simulations yet — run your first policy in the{' '}
              <span
                onClick={() => navigate('/simulate')}
                style={{ color: '#BC6FF1', cursor: 'pointer', textDecoration: 'underline' }}
              >
                Simulate tab
              </span>
            </div>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '1px solid rgba(188,111,241,0.08)' }}>
                  {['Policy Prompt', 'Status', 'Health Score', 'Time'].map(h => (
                    <th key={h} style={{
                      padding: '0.75rem 1.5rem',
                      textAlign: 'left',
                      fontSize: '0.68rem',
                      fontWeight: 700,
                      color: 'rgba(188,111,241,0.5)',
                      textTransform: 'uppercase',
                      letterSpacing: '0.08em',
                    }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {jobHistory.map((job, i) => (
                  <tr
                    key={job.job_id}
                    onClick={() => navigate('/simulate')}
                    style={{
                      borderBottom: '1px solid rgba(188,111,241,0.06)',
                      cursor: 'pointer',
                      transition: 'background 0.15s',
                    }}
                    onMouseOver={(e) => e.currentTarget.style.background = 'rgba(137,44,220,0.08)'}
                    onMouseOut={(e) => e.currentTarget.style.background = 'transparent'}
                  >
                    <td style={{ padding: '1rem 1.5rem', maxWidth: 320 }}>
                      <span style={{
                        fontSize: '0.85rem', color: 'rgba(255,255,255,0.8)',
                        display: '-webkit-box', WebkitLineClamp: 1,
                        WebkitBoxOrient: 'vertical', overflow: 'hidden',
                      }}>
                        {job.prompt}
                      </span>
                    </td>
                    <td style={{ padding: '1rem 1.5rem' }}>
                      <StatusBadge status={job.status} />
                    </td>
                    <td style={{ padding: '1rem 1.5rem' }}>
                      {job.health_score != null ? (
                        <span style={{
                          fontSize: '1rem', fontWeight: 800,
                          color: job.health_score >= 70 ? '#4ade80' : job.health_score >= 50 ? '#fbbf24' : '#f87171'
                        }}>
                          {job.health_score}
                        </span>
                      ) : (
                        <span style={{ color: 'rgba(188,111,241,0.3)', fontSize: '0.85rem' }}>—</span>
                      )}
                    </td>
                    <td style={{ padding: '1rem 1.5rem' }}>
                      <span style={{ fontSize: '0.8rem', color: 'rgba(188,111,241,0.5)', display: 'flex', alignItems: 'center', gap: 4 }}>
                        <Clock size={12} />{timeAgo(job.timestamp)}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        {/* System Status Card */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="glass-card" style={{ padding: '1.5rem' }}>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff', marginBottom: '1.25rem' }}>
              System Status
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Backend */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Server size={16} color="rgba(188,111,241,0.6)" />
                  <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.7)' }}>API Backend</span>
                </div>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  fontSize: '0.72rem', fontWeight: 700,
                  padding: '0.2rem 0.65rem', borderRadius: 999,
                  background: backendOk === null ? 'rgba(188,111,241,0.1)' : backendOk ? 'rgba(74,222,128,0.12)' : 'rgba(248,113,113,0.12)',
                  color:       backendOk === null ? '#BC6FF1'               : backendOk ? '#4ade80'               : '#f87171',
                }}>
                  <span style={{
                    width: 6, height: 6, borderRadius: '50%',
                    background: 'currentColor',
                    animation: backendOk === null ? 'pulse 1.4s infinite' : 'none',
                  }} />
                  {backendOk === null ? 'Checking' : backendOk ? 'Online' : 'Offline'}
                </span>
              </div>

              {/* ML Model */}
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                  <Database size={16} color="rgba(188,111,241,0.6)" />
                  <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.7)' }}>ML Model</span>
                </div>
                <span style={{
                  display: 'inline-flex', alignItems: 'center', gap: 5,
                  fontSize: '0.72rem', fontWeight: 700,
                  padding: '0.2rem 0.65rem', borderRadius: 999,
                  background: employees.length > 0 ? 'rgba(74,222,128,0.12)' : 'rgba(251,191,36,0.12)',
                  color:       employees.length > 0 ? '#4ade80' : '#fbbf24',
                }}>
                  <span style={{ width: 6, height: 6, borderRadius: '50%', background: 'currentColor' }} />
                  {employees.length > 0 ? 'Trained' : 'No Dataset'}
                </span>
              </div>

              {/* Dataset rows */}
              <div style={{
                marginTop: 4, padding: '0.75rem', borderRadius: 10,
                background: 'rgba(137,44,220,0.08)',
                border: '1px solid rgba(188,111,241,0.1)',
              }}>
                <div style={{ fontSize: '0.7rem', color: 'rgba(188,111,241,0.5)', marginBottom: 4 }}>DATASET</div>
                <div style={{ fontSize: '1.2rem', fontWeight: 800, color: '#fff' }}>
                  {baseEmp.toLocaleString()}
                </div>
                <div style={{ fontSize: '0.75rem', color: 'rgba(188,111,241,0.5)', marginTop: 2 }}>
                  employee records loaded
                </div>
              </div>
            </div>
          </div>

          {/* Quick Actions */}
          <div className="glass-card" style={{ padding: '1.5rem' }}>
            <h2 style={{ fontSize: '0.95rem', fontWeight: 700, color: '#fff', marginBottom: '1rem' }}>
              Quick Actions
            </h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
              {[
                { label: '⚡ Run Simulation', path: '/simulate', primary: true },
                { label: '📤 Upload Dataset', path: '/upload', primary: false },
              ].map(({ label, path, primary }) => (
                <button
                  key={path}
                  onClick={() => navigate(path)}
                  style={{
                    width: '100%', padding: '0.65rem 1rem',
                    borderRadius: 10, textAlign: 'left',
                    cursor: 'pointer', fontSize: '0.85rem', fontWeight: 600,
                    background: primary ? 'linear-gradient(135deg, #892CDC, #52057B)' : 'rgba(137,44,220,0.08)',
                    border: primary ? '1px solid rgba(188,111,241,0.3)' : '1px solid rgba(188,111,241,0.1)',
                    color: '#fff',
                    transition: 'all 0.18s',
                    boxShadow: primary ? '0 4px 16px rgba(137,44,220,0.25)' : 'none',
                  }}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
