import React from 'react'
import { Printer, TrendingUp, TrendingDown, Activity, AlertTriangle } from 'lucide-react'

const SEVERITY_COLOR = { HIGH: '#f87171', MEDIUM: '#fbbf24', LOW: '#4ade80' }
const VERDICT_COLOR  = { IMPROVING: '#4ade80', STABLE: '#fbbf24', DECLINING: '#f87171' }

// Helper to format bold text and line breaks from LLM strings
const renderRichText = (text) => {
  if (!text) return 'No detailed analysis available for this simulation.'
  
  // Split on \n or \\n
  return text.split(/(?:\r?\n|\\n)/).map((line, i) => {
    if (!line.trim()) return <div key={i} style={{ height: 8 }} />
    const parts = line.split(/(\*\*.*?\*\*)/g)
    return (
      <div key={i} style={{ marginBottom: 6 }}>
        {parts.map((p, j) => {
          if (p.startsWith('**') && p.endsWith('**')) {
            return <strong key={j} style={{ color: '#fff', fontWeight: 700 }}>{p.slice(2, -2)}</strong>
          }
          return p
        })}
      </div>
    )
  })
}

export default function BriefingPanel({ result }) {
  if (!result) return null
  const payload = result.briefing
  if (!payload || !payload.briefing || !payload.analytics) return null

  const { briefing, analytics } = payload
  const { sim_result } = result

  // Derive risk level from health label
  const riskMapping = {
    'healthy': 'LOW',
    'mixed': 'MEDIUM',
    'at risk': 'HIGH',
    'critical': 'HIGH'
  }
  const risk_level = riskMapping[analytics.health_label] || 'UNKNOWN'
  
  // Try to derive verdict from performance dict
  const attrition_verdict = briefing.performance?.attrition_verdict?.toUpperCase() || 'STABLE'
  const verdictColor = VERDICT_COLOR[attrition_verdict] || '#BC6FF1'
  
  const narrative = `${briefing.situation || ''}\n\n${briefing.comparison || ''}`

  return (
    <div style={{
      marginTop: '2.5rem',
      animation: 'slideUp 0.5s ease-out forwards',
      position: 'relative',
    }}>
      {/* ── Header ────────────────────────────────────────── */}
      <div style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        marginBottom: '1.5rem',
      }}>
        <div>
          <h2 style={{ fontSize: '1.3rem', fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
            Executive Briefing
          </h2>
          <p style={{ fontSize: '0.8rem', color: 'rgba(188,111,241,0.6)' }}>
            AI-generated organizational impact analysis
          </p>
        </div>

        <button
          onClick={() => window.print()}
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 8,
            padding: '0.5rem 1rem',
            borderRadius: 10,
            background: 'rgba(137,44,220,0.15)',
            border: '1px solid rgba(188,111,241,0.3)',
            color: '#BC6FF1',
            fontSize: '0.85rem',
            fontWeight: 700,
            cursor: 'pointer',
            transition: 'all 0.2s',
          }}
          onMouseOver={(e) => { e.currentTarget.style.background = 'rgba(137,44,220,0.25)' }}
          onMouseOut={(e) => { e.currentTarget.style.background = 'rgba(137,44,220,0.15)' }}
        >
          <Printer size={16} /> Export PDF
        </button>
      </div>

      {/* ── Top Level Intelligence ────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: '1rem',
        marginBottom: '1.5rem',
      }}>
        {[
          {
            label: 'Org Health Score',
            value: analytics.health_score,
            suffix: '/ 100',
            color: verdictColor,
            icon: Activity
          },
          {
            label: 'Attrition Δ',
            value: analytics.attrition?.vs_baseline_pts != null 
              ? `${analytics.attrition.vs_baseline_pts > 0 ? '+' : ''}${analytics.attrition.vs_baseline_pts} pts` 
              : '—',
            color: analytics.attrition?.vs_baseline_pts <= 0 ? '#4ade80' : '#f87171',
            icon: analytics.attrition?.vs_baseline_pts <= 0 ? TrendingDown : TrendingUp
          },
          {
            label: 'Productivity Δ',
            value: analytics.metrics?.productivity?.pct_change != null 
              ? `${analytics.metrics.productivity.pct_change > 0 ? '+' : ''}${analytics.metrics.productivity.pct_change}%` 
              : '—',
            color: analytics.metrics?.productivity?.pct_change >= 0 ? '#4ade80' : '#f87171',
            icon: analytics.metrics?.productivity?.pct_change >= 0 ? TrendingUp : TrendingDown
          },
          {
            label: 'Risk Level',
            value: risk_level,
            color: SEVERITY_COLOR[risk_level] || '#BC6FF1',
            icon: AlertTriangle
          },
        ].map((m, i) => (
          <div key={i} className="glass-card" style={{ padding: '1.25rem', textAlign: 'center' }}>
            <div style={{
              fontSize: '0.65rem',
              color: 'rgba(188,111,241,0.5)',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              marginBottom: 8,
              fontWeight: 700
            }}>
              {m.label}
            </div>
            <div style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: 8,
              fontSize: '1.6rem',
              fontWeight: 900,
              color: m.color,
              lineHeight: 1
            }}>
              {m.value}{m.suffix}
            </div>
          </div>
        ))}
      </div>

      {/* ── Qualitative Analysis ──────────────────────────── */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: '1.2fr 1fr',
        gap: '1rem',
        marginBottom: '1rem',
      }}>
        {/* Narrative */}
        <div className="glass-card" style={{ padding: '1.75rem' }}>
          <div style={{
            fontSize: '0.7rem',
            fontWeight: 800,
            color: 'rgba(188,111,241,0.5)',
            textTransform: 'uppercase',
            letterSpacing: '0.1em',
            marginBottom: 16
          }}>
            Executive Narrative
          </div>
          <div style={{
            fontSize: '0.92rem',
            color: 'rgba(255,255,255,0.85)',
            lineHeight: 1.8,
            fontWeight: 400
          }}>
            {renderRichText(narrative)}
          </div>
        </div>

        {/* Risks & Recs Column */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {/* Risk Factors */}
          <div className="glass-card" style={{ padding: '1.25rem' }}>
            <div style={{
              fontSize: '0.7rem',
              fontWeight: 800,
              color: 'rgba(188,111,241,0.5)',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              marginBottom: 12
            }}>
              Primary Risk Factors
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              {(briefing.risks || []).map((r, i) => {
                const sev = (r.severity || 'low').toUpperCase();
                return (
                  <div key={i} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ fontSize: '0.85rem', color: 'rgba(255,255,255,0.7)', paddingRight: 8 }}>{r.title}</span>
                    <span style={{
                      fontSize: '0.65rem',
                      fontWeight: 800,
                      padding: '0.2rem 0.6rem',
                      borderRadius: 6,
                      background: `${SEVERITY_COLOR[sev] || SEVERITY_COLOR['LOW']}15`,
                      color: SEVERITY_COLOR[sev] || SEVERITY_COLOR['LOW'],
                      border: `1px solid ${SEVERITY_COLOR[sev] || SEVERITY_COLOR['LOW']}30`,
                      flexShrink: 0
                    }}>
                      {sev}
                    </span>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Recommendations */}
          <div className="glass-card" style={{ padding: '1.25rem', flex: 1 }}>
            <div style={{
              fontSize: '0.7rem',
              fontWeight: 800,
              color: 'rgba(188,111,241,0.5)',
              textTransform: 'uppercase',
              letterSpacing: '0.1em',
              marginBottom: 12
            }}>
              Strategic Recommendations
            </div>
            <ul style={{ listStyle: 'none', display: 'flex', flexDirection: 'column', gap: 10 }}>
              <li style={{ display: 'flex', gap: 10, fontSize: '0.85rem', color: 'rgba(255,255,255,0.7)', lineHeight: 1.5 }}>
                <span style={{ color: '#BC6FF1', fontWeight: 900, marginTop: 2 }}>⚡</span>
                <div>{renderRichText(briefing.recommendation)}</div>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}
