import { useState, useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { Zap, AlertCircle, RefreshCw } from 'lucide-react'
import StatusStepper from '../components/StatusStepper'
import BriefingPanel from '../components/BriefingPanel'
import { orchestrateAndPoll, getOrchestrateStatus } from '../services/api'

const EXAMPLE_PROMPTS = [
  'Reduce overtime by 20% and increase base salary by 10% for all departments',
  'Introduce flexible work-from-home policy 3 days a week for all staff',
  'Add mandatory leadership training and promote 15% of mid-level employees',
  'Cut headcount in Sales by 8% and redistribute workload to remaining staff',
]

export default function Simulate() {
  const [prompt,  setPrompt]  = useState('')
  const [status,  setStatus]  = useState(null)
  const [result,  setResult]  = useState(null)
  const [error,   setError]   = useState(null)
  const [loading, setLoading] = useState(false)
  const textareaRef = useRef(null)
  const location = useLocation()

  // ── Session Restore ─────────────────────────────────────
  useEffect(() => {
    let targetPrompt = localStorage.getItem('simuorg_last_prompt')
    let targetJobId  = localStorage.getItem('simuorg_last_job_id')

    if (location.state?.jobId) {
      targetJobId = location.state.jobId
      targetPrompt = location.state.prompt
      localStorage.setItem('simuorg_last_job_id', targetJobId)
      if (targetPrompt) localStorage.setItem('simuorg_last_prompt', targetPrompt)
    }

    if (targetPrompt) setPrompt(targetPrompt)
    if (targetJobId) {
      getOrchestrateStatus(targetJobId)
        .then(({ data }) => {
          if (data.status === 'completed' && data.result) {
            setResult(data.result)
            setStatus('completed')
          } else if (data.status === 'running' || data.status === 'queued') {
            // Resume polling
            setStatus(data.status)
            setLoading(true)
            resumePoll(targetJobId)
          } else if (data.status === 'failed') {
            setStatus('failed')
            setError(data.error || 'Orchestration failed')
          }
        })
        .catch(() => {}) // silently ignore stale job_id
    }
  }, [location.state])

  const resumePoll = (jobId) => {
    const poll = setInterval(async () => {
      try {
        const { data } = await getOrchestrateStatus(jobId)
        setStatus(data.status)
        if (data.status === 'completed') {
          clearInterval(poll)
          setResult(data.result)
          setLoading(false)
        } else if (data.status === 'failed') {
          clearInterval(poll)
          setError(data.error || 'Orchestration failed')
          setLoading(false)
        }
      } catch {
        clearInterval(poll)
        setLoading(false)
      }
    }, 2500)
  }

  // ── Run Handler ─────────────────────────────────────────
  const handleRun = async () => {
    if (!prompt.trim() || loading) return
    setLoading(true)
    setResult(null)
    setError(null)
    setStatus('queued')
    localStorage.setItem('simuorg_last_prompt', prompt)

    try {
      const { result: res, job_id } = await orchestrateAndPoll(prompt, setStatus)
      setResult(res)
      setStatus('completed')

      // Persist to job history
      const history = JSON.parse(localStorage.getItem('simuorg_job_history') || '[]')
      history.unshift({ job_id, prompt: prompt.slice(0, 120), timestamp: Date.now() })
      localStorage.setItem('simuorg_job_history', JSON.stringify(history.slice(0, 10)))
    } catch (err) {
      setStatus('failed')
      setError(err.message || 'Something went wrong. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleReset = () => {
    setStatus(null)
    setResult(null)
    setError(null)
    setPrompt('')
    localStorage.removeItem('simuorg_last_job_id')
    localStorage.removeItem('simuorg_last_prompt')
    textareaRef.current?.focus()
  }

  const handleKeyDown = (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') handleRun()
  }

  return (
    <div style={{ animation: 'fadeIn 0.4s ease', maxWidth: 900, margin: '0 auto' }}>
      {/* ── Page Header ────────────────────────────────────── */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h1 className="page-title">Policy Simulation</h1>
        <p className="page-sub">
          Describe an HR policy in plain English — the AI pipeline handles the rest.
        </p>
      </div>

      {/* ── Input Panel ─────────────────────────────────────── */}
      <div className="glass-card" style={{ padding: '2rem', marginBottom: '1.5rem' }}>
        <label style={{
          display: 'block',
          fontSize: '0.72rem', fontWeight: 700,
          color: 'rgba(188,111,241,0.6)',
          textTransform: 'uppercase', letterSpacing: '0.1em',
          marginBottom: '0.75rem',
        }}>
          Policy Prompt
        </label>

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          placeholder='e.g. "Reduce overtime by 20% and increase base salary by 10% for all staff"'
          rows={4}
          style={{
            width: '100%',
            padding: '1rem 1.25rem',
            borderRadius: '0.75rem',
            background: 'rgba(82,5,123,0.15)',
            border: '1px solid rgba(188,111,241,0.25)',
            color: '#fff',
            fontSize: '0.95rem',
            fontFamily: 'Inter, sans-serif',
            lineHeight: 1.6,
            resize: 'vertical',
            outline: 'none',
            transition: 'border-color 0.2s, box-shadow 0.2s',
            opacity: loading ? 0.6 : 1,
          }}
          onFocus={(e) => {
            e.target.style.borderColor = '#892CDC'
            e.target.style.boxShadow = '0 0 0 3px rgba(137,44,220,0.18)'
          }}
          onBlur={(e) => {
            e.target.style.borderColor = 'rgba(188,111,241,0.25)'
            e.target.style.boxShadow = 'none'
          }}
        />

        {/* Example pills */}
        <div style={{ marginTop: '0.75rem', marginBottom: '1.5rem' }}>
          <div style={{ fontSize: '0.72rem', color: 'rgba(188,111,241,0.45)', marginBottom: 6 }}>
            EXAMPLES — click to use
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
            {EXAMPLE_PROMPTS.map((p, i) => (
              <button
                key={i}
                onClick={() => setPrompt(p)}
                disabled={loading}
                style={{
                  padding: '0.3rem 0.75rem',
                  borderRadius: 999,
                  background: 'rgba(137,44,220,0.1)',
                  border: '1px solid rgba(188,111,241,0.18)',
                  color: 'rgba(188,111,241,0.8)',
                  fontSize: '0.75rem',
                  cursor: 'pointer',
                  transition: 'all 0.15s',
                  fontFamily: 'Inter, sans-serif',
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.background = 'rgba(137,44,220,0.2)'
                  e.currentTarget.style.color = '#BC6FF1'
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.background = 'rgba(137,44,220,0.1)'
                  e.currentTarget.style.color = 'rgba(188,111,241,0.8)'
                }}
              >
                {p.slice(0, 40)}…
              </button>
            ))}
          </div>
        </div>

        {/* Action Row */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'rgba(188,111,241,0.35)' }}>
            ⌘ + Enter to run
          </span>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            {result && (
              <button
                onClick={handleReset}
                style={{
                  display: 'flex', alignItems: 'center', gap: 6,
                  padding: '0.65rem 1.25rem', borderRadius: 10,
                  background: 'transparent',
                  border: '1px solid rgba(188,111,241,0.2)',
                  color: 'rgba(188,111,241,0.6)',
                  fontSize: '0.875rem', fontWeight: 600, cursor: 'pointer',
                  transition: 'all 0.18s',
                }}
              >
                <RefreshCw size={15} /> New Policy
              </button>
            )}
            <button
              onClick={handleRun}
              disabled={loading || !prompt.trim()}
              style={{
                display: 'flex', alignItems: 'center', gap: 8,
                padding: '0.7rem 1.75rem', borderRadius: 10,
                background: loading || !prompt.trim()
                  ? 'rgba(137,44,220,0.2)'
                  : 'linear-gradient(135deg, #892CDC, #52057B)',
                border: '1px solid rgba(188,111,241,0.3)',
                color: '#fff', fontSize: '0.9rem', fontWeight: 700,
                cursor: loading || !prompt.trim() ? 'not-allowed' : 'pointer',
                opacity: !prompt.trim() ? 0.5 : 1,
                transition: 'all 0.18s',
                boxShadow: !loading && prompt.trim() ? '0 4px 24px rgba(137,44,220,0.45)' : 'none',
              }}
              onMouseOver={(e) => {
                if (!loading && prompt.trim()) e.currentTarget.style.transform = 'translateY(-1px)'
              }}
              onMouseOut={(e) => { e.currentTarget.style.transform = 'none' }}
            >
              <Zap size={17} />
              {loading ? 'Running…' : 'Run Simulation'}
            </button>
          </div>
        </div>
      </div>

      {/* ── Progress Stepper ─────────────────────────────────── */}
      {status && (
        <div className="glass-card" style={{ padding: '1.5rem 2rem', marginBottom: '1.5rem' }}>
          <div style={{
            fontSize: '0.72rem', fontWeight: 700,
            color: 'rgba(188,111,241,0.5)',
            textTransform: 'uppercase', letterSpacing: '0.1em',
            marginBottom: '0.5rem',
          }}>
            Pipeline Progress
          </div>
          <StatusStepper status={status} />
        </div>
      )}

      {/* ── Error Banner ─────────────────────────────────────── */}
      {error && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 12,
          padding: '1.25rem 1.5rem', borderRadius: 12,
          background: 'rgba(248,113,113,0.1)',
          border: '1px solid rgba(248,113,113,0.25)',
          marginBottom: '1.5rem',
          animation: 'slideUp 0.3s ease',
        }}>
          <AlertCircle size={20} color="#f87171" style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <div style={{ fontWeight: 700, color: '#f87171', fontSize: '0.9rem', marginBottom: 4 }}>
              Simulation Failed
            </div>
            <div style={{ color: 'rgba(248,113,113,0.8)', fontSize: '0.85rem' }}>{error}</div>
          </div>
        </div>
      )}

      {/* ── Chat/Clarification Response ─────────────────────── */}
      {result && result.type === 'chat' && status === 'completed' && (
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 16,
          padding: '1.5rem 2rem', borderRadius: 12,
          background: 'rgba(137,44,220,0.1)',
          border: '1px solid rgba(137,44,220,0.25)',
          marginBottom: '1.5rem',
          animation: 'slideUp 0.3s ease',
        }}>
          <div style={{
            background: 'linear-gradient(135deg, #892CDC, #52057B)',
            padding: 8, borderRadius: 10, flexShrink: 0
          }}>
            <Zap size={20} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 700, color: '#fff', fontSize: '1rem', marginBottom: 6 }}>
              SimuOrg AI
            </div>
            <div style={{ color: 'rgba(255,255,255,0.85)', fontSize: '0.95rem', lineHeight: 1.6 }}>
              {result.response}
            </div>
          </div>
        </div>
      )}

      {/* ── Executive Briefing ─────────────────────────────── */}
      {result && result.type !== 'chat' && status === 'completed' && (
        <BriefingPanel result={result} />
      )}
    </div>
  )
}
