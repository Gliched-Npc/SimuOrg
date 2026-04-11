# SimuOrg Frontend — Complete Implementation Spec

> **Purpose:** This document is the single source of truth for building the SimuOrg React frontend. It is written to be handed off to a new session. Follow it precisely.

---

## Visual Reference

### ⭐ Final Design — Glassmorphism + Deep Plum
![Final Design](C:\Users\LENOVO\.gemini\antigravity\brain\c1f79b3b-e518-43fe-99a6-899ba8ca17da\simuorg_glass_purple_mockup_1775922011679.png)

### Dashboard Tab
![Dashboard Mockup](C:\Users\LENOVO\.gemini\antigravity\brain\c1f79b3b-e518-43fe-99a6-899ba8ca17da\simuorg_frontend_mockup_1775909522165.png)

### Simulate Tab (Policy Input + Briefing)
![Simulate Tab Mockup](C:\Users\LENOVO\.gemini\antigravity\brain\c1f79b3b-e518-43fe-99a6-899ba8ca17da\simuorg_simulate_tab_1775910612032.png)

### Analytics Tab
![Analytics Tab Mockup](C:\Users\LENOVO\.gemini\antigravity\brain\c1f79b3b-e518-43fe-99a6-899ba8ca17da\simuorg_analytics_tab_1775910632095.png)

---

## Project Context

**SimuOrg** is an AI-powered HR organizational simulation platform. The **two manual user actions** are:
1. Upload a CSV dataset → backend validates, ingests, trains ML model automatically
2. Type a policy in plain English → full pipeline runs automatically (intent parse → Monte Carlo simulation → LLM reasoning chain → executive briefing)

Everything else is automated via Celery workers + FastAPI backend.

---

## Stack

| Part | Tech |
|------|------|
| Framework | React 19 + Vite |
| Routing | `react-router-dom` v7 (already installed) |
| Charts | `recharts` v3 (already installed) |
| Icons | `lucide-react` (already installed) |
| HTTP | `axios` (already installed) |
| Styling | Tailwind CSS v4 + custom CSS variables |
| State | React `useState` / `useEffect` — no Redux needed |
| Persistence | `localStorage` for session restore |

> ⚠️ **Do NOT add new npm dependencies.** All required packages are already in `package.json`.

---

## Final Tab Structure

| # | Tab Label | Route | Icon (lucide-react) |
|---|-----------|-------|---------------------|
| 1 | Dashboard | `/` | `LayoutDashboard` |
| 2 | Upload | `/upload` | `Upload` |
| 3 | Simulate | `/simulate` | `Zap` |
| 4 | Analytics | `/analytics` | `BarChart2` |

---

## File Map — What to Create / Modify

```
frontend/src/
├── index.css                          MODIFY  (design system)
├── main.jsx                           MODIFY  (add BrowserRouter)
├── App.jsx                            MODIFY  (sidebar layout + routes)
│
├── components/
│   ├── Sidebar.jsx                    CREATE  (replaces Navbar.jsx)
│   ├── KpiCard.jsx                    CREATE
│   ├── StatusStepper.jsx              CREATE
│   ├── BriefingPanel.jsx              CREATE
│   └── StatusBadge.jsx                CREATE
│
├── pages/
│   ├── Dashboard.jsx                  MODIFY  (full redesign)
│   ├── UploadData.jsx                 MODIFY  (full redesign)
│   ├── Simulate.jsx                   CREATE  (replaces SimulationResults.jsx)
│   └── Analytics.jsx                  CREATE
│
└── services/
    └── api.js                         MODIFY  (add missing wrappers)
```

---

## 1. `frontend/src/index.css` — Design System

> **Final Palette — Glassmorphism + Deep Plum:**
> - Background: deep plum radial gradient (`#1a0f35` → `#0e0818`) — NOT pure black, rich and warm
> - Sidebar: frosted glass (`rgba(82,5,123,0.45)` + `backdrop-filter: blur(24px)`)
> - Cards: glass panels (`rgba(137,44,220,0.1)` + `backdrop-filter: blur(18px)`)
> - Brand: `#52057B` deep violet · `#892CDC` medium purple · `#BC6FF1` lavender
> - Status: `#4ade80` green · `#fbbf24` amber · `#f87171` red

**Completely replace** the file with:

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
@import "tailwindcss";

@theme {
  --font-sans: 'Inter', system-ui, sans-serif;
}

:root {
  /* ── Brand Palette ── */
  --bg-from:      #1a0f35;   /* deep plum — gradient start (centre) */
  --bg-to:        #0e0818;   /* darker edge */
  --bg-surface:   rgba(137,44,220,0.10); /* glass card surface */
  --bg-elevated:  rgba(82,5,123,0.20);   /* slightly more opaque elevated glass */

  --sidebar-glass: rgba(82,5,123,0.48);  /* sidebar frosted glass */
  --sidebar-border: rgba(188,111,241,0.22);

  --accent:       #892CDC;   /* primary purple */
  --accent-light: #BC6FF1;   /* lavender */
  --accent-dark:  #52057B;   /* deep violet */
  --accent-dim:   rgba(137,44,220,0.15);
  --accent-glow:  rgba(137,44,220,0.4);

  --border:       rgba(188,111,241,0.14);
  --border-hover: rgba(188,111,241,0.38);

  /* ── Status ── */
  --success:  #4ade80;
  --warning:  #fbbf24;
  --danger:   #f87171;
  --info:     #38bdf8;

  /* ── Text ── */
  --text-1:   #ffffff;
  --text-2:   #BC6FF1;           /* lavender secondary */
  --text-3:   rgba(188,111,241,0.45); /* muted */

  --sidebar-w: 220px;
  --radius:    1.25rem;
  --radius-sm: 0.75rem;
}

*, *::before, *::after { margin:0; padding:0; box-sizing:border-box; }
html { scroll-behavior: smooth; }

body {
  /* Deep plum radial gradient — warm, luxurious, not flat black */
  background:
    radial-gradient(ellipse at 40% 0%, rgba(137,44,220,0.18) 0%, transparent 60%),
    radial-gradient(ellipse at 80% 80%, rgba(82,5,123,0.22) 0%, transparent 55%),
    linear-gradient(160deg, #1a0f35 0%, #110920 45%, #0e0818 100%);
  background-attachment: fixed;
  color: var(--text-1);
  font-family: 'Inter', system-ui, sans-serif;
  -webkit-font-smoothing: antialiased;
  min-height: 100vh;
}

/* Scrollbar */
::-webkit-scrollbar { width: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: rgba(137,44,220,0.45); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(188,111,241,0.65); }

/* App Shell */
.app-shell { display: flex; min-height: 100vh; }
.main-content {
  flex: 1;
  margin-left: var(--sidebar-w);
  padding: 2rem 2.5rem;
  min-height: 100vh;
  position: relative;
}

/* ── Glass Card ──────────────────────────────────────── */
/* The core glassmorphism unit used everywhere */
.glass-card {
  background: rgba(137,44,220,0.10);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  transition: border-color 0.25s, box-shadow 0.25s, background 0.25s;
}
.glass-card:hover {
  background: rgba(137,44,220,0.15);
  border-color: rgba(188,111,241,0.32);
  box-shadow:
    0 0 0 1px rgba(137,44,220,0.08),
    0 8px 40px rgba(82,5,123,0.5),
    inset 0 1px 0 rgba(188,111,241,0.1);
}

/* Page header */
.page-title { font-size:1.6rem; font-weight:700; letter-spacing:-0.02em; color:#fff; }
.page-sub   { font-size:0.85rem; color:var(--text-2); margin-top:0.25rem; }

/* ── Ambient Glow Blobs ──────────────────────────────── */
/* These sit behind everything and make the bg feel alive */
.glow-1 {
  position:fixed; pointer-events:none; z-index:0;
  top:-180px; left:15%; width:900px; height:700px; border-radius:50%;
  background: radial-gradient(ellipse, rgba(137,44,220,0.14) 0%, transparent 68%);
  filter: blur(80px);
}
.glow-2 {
  position:fixed; pointer-events:none; z-index:0;
  bottom:-140px; right:-80px; width:700px; height:600px; border-radius:50%;
  background: radial-gradient(ellipse, rgba(82,5,123,0.22) 0%, transparent 65%);
  filter: blur(100px);
}
.glow-3 {
  position:fixed; pointer-events:none; z-index:0;
  top:50%; left:60%; width:500px; height:500px; border-radius:50%;
  background: radial-gradient(ellipse, rgba(188,111,241,0.05) 0%, transparent 70%);
  filter: blur(60px);
}

/* ── Animations ──────────────────────────────────────── */
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.3; }
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
@keyframes slideUp {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}
@keyframes fadeIn {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes glowPulse {
  0%, 100% { box-shadow: 0 0 20px rgba(137,44,220,0.3); }
  50%       { box-shadow: 0 0 40px rgba(137,44,220,0.6); }
}

/* ── Print / PDF Export ──────────────────────────────── */
@media print {
  .app-shell > aside { display: none !important; }
  .main-content { margin-left: 0 !important; }
  body { background: white !important; }
  .glass-card {
    border: 1px solid #ccc !important;
    background: #f9f9f9 !important;
    backdrop-filter: none !important;
    color: #111 !important;
  }
}
```
```

---

## 2. `frontend/src/main.jsx`

```jsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import './index.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </StrictMode>
)
```

---

## 3. `frontend/src/App.jsx`

```jsx
import { Routes, Route } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import UploadData from './pages/UploadData'
import Simulate from './pages/Simulate'
import Analytics from './pages/Analytics'

export default function App() {
  return (
    <div className="app-shell">
      {/* Ambient glow blobs — 3 layered for depth */}
      <div className="glow-1" />
      <div className="glow-2" />
      <div className="glow-3" />

      <Sidebar />

      <main className="main-content" style={{ position: 'relative', zIndex: 1 }}>
        <Routes>
          <Route path="/"          element={<Dashboard />} />
          <Route path="/upload"    element={<UploadData />} />
          <Route path="/simulate"  element={<Simulate />} />
          <Route path="/analytics" element={<Analytics />} />
          {/* Fallback */}
          <Route path="*"          element={<Dashboard />} />
        </Routes>
      </main>
    </div>
  )
}
```

---

## 4. `frontend/src/components/Sidebar.jsx`

**Full specification:**
- Fixed left sidebar, `width: 220px`, `height: 100vh`, `position: fixed`
- Background: **frosted glass** — `background: rgba(82,5,123,0.48)`, `backdropFilter: 'blur(24px)'`, `-webkitBackdropFilter: 'blur(24px)'`
- Border-right: `1px solid rgba(188,111,241,0.22)`
- Logo: "SO" in white on `#3d0460` circle, glow `box-shadow: 0 4px 20px rgba(137,44,220,0.55)`
- Active nav: `background: rgba(0,0,0,0.3)`, `borderLeft: 3px solid #BC6FF1`, `color: #ffffff`
- Inactive nav: `color: rgba(255,255,255,0.6)`
- Hover nav: `background: rgba(0,0,0,0.15)`

```jsx
import { NavLink } from 'react-router-dom'
import { LayoutDashboard, Upload, Zap, BarChart2 } from 'lucide-react'

const links = [
  { to: '/',          label: 'Dashboard', icon: LayoutDashboard },
  { to: '/upload',    label: 'Upload',    icon: Upload },
  { to: '/simulate',  label: 'Simulate',  icon: Zap },
  { to: '/analytics', label: 'Analytics', icon: BarChart2 },
]

export default function Sidebar() {
  return (
    <aside style={{
      position: 'fixed', top: 0, left: 0,
      width: '220px', height: '100vh',
      background: 'rgba(82,5,123,0.48)',         /* frosted glass — NOT solid */
      backdropFilter: 'blur(24px)',
      WebkitBackdropFilter: 'blur(24px)',
      borderRight: '1px solid rgba(188,111,241,0.22)',
      display: 'flex', flexDirection: 'column',
      zIndex: 50,
    }}>
      {/* Logo */}
      <div style={{ padding: '1.75rem 1.25rem 1rem' }}>
        <div style={{
          width: 46, height: 46, borderRadius: 14,
          background: '#3d0460',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontWeight: 800, fontSize: 16, color: '#fff',
          boxShadow: '0 4px 20px rgba(137,44,220,0.5)',
          marginBottom: 12, letterSpacing: '-0.02em',
        }}>SO</div>
        <div style={{ fontWeight: 700, fontSize: '1rem', color: '#ffffff' }}>SimuOrg</div>
        <div style={{ fontSize: '0.63rem', color: 'rgba(188,111,241,0.7)', letterSpacing: '0.12em', textTransform: 'uppercase', marginTop: 3 }}>Intelligence Platform</div>
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: 'rgba(188,111,241,0.15)', margin: '0 1rem 1rem' }} />

      {/* Nav links */}
      <nav style={{ flex: 1, padding: '0 0.6rem' }}>
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            style={({ isActive }) => ({
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '0.65rem 1rem', borderRadius: '0.6rem',
              margin: '0.2rem 0', textDecoration: 'none',
              fontSize: '0.875rem', fontWeight: isActive ? 600 : 500,
              color: isActive ? '#ffffff' : 'rgba(255,255,255,0.65)',
              background: isActive ? 'rgba(0,0,0,0.28)' : 'transparent',
              borderLeft: isActive ? '3px solid #BC6FF1' : '3px solid transparent',
              transition: 'all 0.18s',
            })}
          >
            <Icon size={17} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div style={{ padding: '1rem 1.25rem', fontSize: '0.68rem', color: 'rgba(188,111,241,0.45)' }}>
        SimuOrg v1.0 · FastAPI · React
      </div>
    </aside>
  )
}
```

---

## 5. `frontend/src/components/KpiCard.jsx`

**Props:** `label` (string), `value` (string|number), `delta` (string, optional e.g. "+4.2%"), `deltaDir` ("up"|"down"|null), `icon` (lucide component), `color` ("indigo"|"emerald"|"amber"|"rose")

**Behavior:**
- Animated count-up using `useEffect` + `requestAnimationFrame` if `value` is numeric
- Glass card with top gradient accent line (2px, color-matched to `color` prop)
- Delta badge: green (▲) for up, red (▼) for down
- Hover: subtle border glow in accent color

```jsx
import { useEffect, useRef, useState } from 'react'

const COLORS = {
  purple:  { grad: '#892CDC', glow: 'rgba(137,44,220,0.25)' },  /* primary */
  lavender:{ grad: '#BC6FF1', glow: 'rgba(188,111,241,0.2)'  },  /* secondary */
  emerald: { grad: '#4ade80', glow: 'rgba(74,222,128,0.2)'   },  /* success  */
  amber:   { grad: '#fbbf24', glow: 'rgba(251,191,36,0.2)'   },  /* warning  */
  rose:    { grad: '#f87171', glow: 'rgba(248,113,113,0.2)'  },  /* danger   */
}

export default function KpiCard({ label, value, delta, deltaDir, icon: Icon, color = 'purple' }) {
  const { grad, glow } = COLORS[color] || COLORS.purple

  return (
    <div className="glass-card" style={{
      padding: '1.25rem 1.5rem',
      borderTop: `2px solid ${grad}`,
      position: 'relative', overflow: 'hidden',
    }}>
      {/* Header row */}
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'flex-start', marginBottom: 12 }}>
        <span style={{ fontSize:'0.72rem', fontWeight:600, color:'#475569', textTransform:'uppercase', letterSpacing:'0.08em' }}>
          {label}
        </span>
        {Icon && (
          <div style={{
            background: `${glow}`,
            borderRadius: 8, padding: 6,
          }}>
            <Icon size={15} color={grad} />
          </div>
        )}
      </div>

      {/* Value */}
      <div style={{ fontSize: '1.9rem', fontWeight: 800, color: '#f1f5f9', letterSpacing: '-0.03em', lineHeight: 1 }}>
        {value}
      </div>

      {/* Delta */}
      {delta && (
        <div style={{
          marginTop: 8, fontSize: '0.75rem', fontWeight: 600,
          color: deltaDir === 'up' ? '#10b981' : deltaDir === 'down' ? '#f43f5e' : '#94a3b8'
        }}>
          {deltaDir === 'up' ? '▲' : deltaDir === 'down' ? '▼' : '·'} {delta}
        </div>
      )}
    </div>
  )
}
```

---

## 6. `frontend/src/components/StatusBadge.jsx`

**Props:** `status` — one of `"queued" | "running" | "completed" | "failed"`

```jsx
const CONFIG = {
  queued:    { color: '#BC6FF1', bg: 'rgba(188,111,241,0.1)', label: 'Queued'    },
  running:   { color: '#892CDC', bg: 'rgba(137,44,220,0.15)', label: 'Running'   },
  completed: { color: '#4ade80', bg: 'rgba(74,222,128,0.1)',  label: 'Completed' },
  failed:    { color: '#f87171', bg: 'rgba(248,113,113,0.1)', label: 'Failed'    },
}

export default function StatusBadge({ status }) {
  const c = CONFIG[status] || CONFIG.queued
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '0.2rem 0.65rem', borderRadius: '999px',
      background: c.bg, color: c.color,
      fontSize: '0.72rem', fontWeight: 600,
    }}>
      <span style={{
        width: 6, height: 6, borderRadius: '50%',
        background: c.color,
        animation: status === 'running' ? 'pulse 1.4s ease-in-out infinite' : 'none',
      }} />
      {c.label}
    </span>
  )
}
```

Add a `@keyframes pulse` in `index.css`: `0%,100%{opacity:1} 50%{opacity:0.3}`

---

## 7. `frontend/src/components/StatusStepper.jsx`

**Props:** `status` — `"queued" | "running" | "completed" | "failed"`

**3 steps:**
1. `Intent Parsed` — complete when status is `running`, `completed`
2. `Simulation Running` — active (spinning) when status is `running`; complete when `completed`
3. `Briefing Ready` — complete when status is `completed`

```jsx
import { Check, Clock, Loader } from 'lucide-react'

export default function StatusStepper({ status }) {
  const steps = [
    { label: 'Intent Parsed',      done: ['running','completed','failed'].includes(status) },
    { label: 'Simulation Running', done: ['completed','failed'].includes(status), active: status === 'running' },
    { label: 'Briefing Ready',     done: status === 'completed' },
  ]

  return (
    <div style={{ display:'flex', alignItems:'center', gap:0, margin:'1.5rem 0' }}>
      {steps.map((step, i) => (
        <React.Fragment key={i}>
          <div style={{ display:'flex', flexDirection:'column', alignItems:'center', gap:6 }}>
            {/* Circle */}
            <div style={{
              width: 36, height: 36, borderRadius: '50%',
              display: 'flex', alignItems:'center', justifyContent:'center',
              background: step.done ? 'rgba(74,222,128,0.15)' : step.active ? 'rgba(137,44,220,0.2)' : 'rgba(188,111,241,0.06)',
              border: `2px solid ${step.done ? '#4ade80' : step.active ? '#892CDC' : 'rgba(188,111,241,0.2)'}`,
            }}>
              {step.done
                ? <Check size={16} color="#4ade80" />
                : step.active
                  ? <Loader size={16} color="#BC6FF1" style={{ animation:'spin 1s linear infinite' }} />
                  : <Clock size={16} color="rgba(188,111,241,0.4)" />
              }
            </div>
            <span style={{ fontSize:'0.7rem', fontWeight:600, color: step.done ? '#4ade80' : step.active ? '#BC6FF1' : 'rgba(188,111,241,0.4)', whiteSpace:'nowrap' }}>
              {step.label}
            </span>
          </div>
          {/* Connector line */}
          {i < steps.length - 1 && (
            <div style={{
              flex:1, height:2, margin:'0 8px', marginBottom:22,
              background: steps[i+1].done || step.done ? 'linear-gradient(90deg,#4ade80,#892CDC)' : 'rgba(188,111,241,0.1)',
              transition:'background 0.4s',
            }} />
          )}
        </React.Fragment>
      ))}
    </div>
  )
}
```

Add `@keyframes spin { to { transform: rotate(360deg); } }` in `index.css`.

---

## 8. `frontend/src/components/BriefingPanel.jsx`

**Props:** `result` (the full orchestration result object from backend)

**The `result` object shape from backend** (from `orchestrate_task` → `orchestrate_user_request()`):
```json
{
  "sim_result": {
    "mean_attrition_rate": 0.142,
    "attrition_delta": -0.023,
    "productivity_delta": 0.041,
    "headcount_trajectory": [...],
    "monthly_metrics": [...]
  },
  "briefing": {
    "health_score": 74,
    "verdict": "IMPROVING",
    "dominant_risk": "Workload",
    "risk_level": "MODERATE",
    "executive_narrative": "The proposed policy of reducing overtime...",
    "risk_factors": [
      {"factor": "Workload", "severity": "HIGH"},
      {"factor": "Satisfaction", "severity": "MEDIUM"}
    ],
    "recommendations": [
      "Phase overtime reduction over 3 months",
      "Monitor Sales department attrition closely"
    ]
  }
}
```

**Layout:**
```
┌─ EXECUTIVE BRIEFING ────────────────────────────────────┐
│  [Org Health: 74 ↑] [Attrition Δ: -2.3%] [Prod: +4.1%] [Risk: MODERATE]
├─────────────────────────────────────────────────────────┤
│  RISK FACTORS               │  RECOMMENDATIONS          │
│  [Workload: HIGH]           │  • Phase overtime...      │
│  [Satisfaction: MED]        │  • Monitor Sales...       │
├─────────────────────────────────────────────────────────┤
│  EXECUTIVE NARRATIVE                                    │
│  "The proposed policy of reducing overtime is           │
│   projected to improve org health by 6 points..."      │
├─────────────────────────────────────────────────────────┤
│                                    [🖨 Export PDF]      │
└─────────────────────────────────────────────────────────┘
```

**Risk severity colors:** `HIGH → rose`, `MEDIUM → amber`, `LOW → emerald`
**Verdict colors:** `IMPROVING → emerald`, `STABLE → amber`, `DECLINING → rose`
**PDF export:** `window.print()` with `@media print` CSS hiding sidebar

```jsx
import { Printer } from 'lucide-react'

const SEVERITY_COLOR = { HIGH:'#f87171', MEDIUM:'#fbbf24', LOW:'#4ade80' }
const VERDICT_COLOR  = { IMPROVING:'#4ade80', STABLE:'#fbbf24', DECLINING:'#f87171' }

export default function BriefingPanel({ result }) {
  if (!result) return null
  const { briefing, sim_result } = result
  if (!briefing) return null

  const verdictColor = VERDICT_COLOR[briefing.verdict] || '#94a3b8'

  return (
    <div style={{ marginTop: '2rem', animation: 'slideUp 0.4s ease-out' }}>
      <div style={{ display:'flex', justifyContent:'space-between', alignItems:'center', marginBottom:'1rem' }}>
        <h2 style={{ fontSize:'1.2rem', fontWeight:700 }}>Executive Briefing</h2>
        <button
          onClick={() => window.print()}
          style={{
            display:'flex', alignItems:'center', gap:6,
            padding:'0.4rem 0.9rem', borderRadius:8,
            background:'rgba(137,44,220,0.15)', border:'1px solid rgba(188,111,241,0.35)',
            color:'#BC6FF1', fontSize:'0.8rem', fontWeight:600, cursor:'pointer',
          }}
        >
          <Printer size={14} /> Export PDF
        </button>
      </div>

      {/* KPI Row */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:'0.75rem', marginBottom:'1rem' }}>
        {[
          { label:'Org Health Score', value: briefing.health_score, suffix:'/ 100', color: verdictColor },
          { label:'Attrition Δ',      value: sim_result?.attrition_delta != null ? `${(sim_result.attrition_delta*100).toFixed(1)}%` : '—' },
          { label:'Productivity Δ',   value: sim_result?.productivity_delta != null ? `${(sim_result.productivity_delta*100).toFixed(1)}%` : '—' },
          { label:'Risk Level',       value: briefing.risk_level || '—' },
        ].map((m, i) => (
          <div key={i} className="glass-card" style={{ padding:'1rem', textAlign:'center' }}>
            <div style={{ fontSize:'0.68rem', color:'#475569', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:6 }}>{m.label}</div>
            <div style={{ fontSize:'1.5rem', fontWeight:800, color: m.color || '#f1f5f9' }}>{m.value}</div>
          </div>
        ))}
      </div>

      {/* Risk + Recommendations */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'0.75rem', marginBottom:'0.75rem' }}>
        <div className="glass-card" style={{ padding:'1.25rem' }}>
          <div style={{ fontSize:'0.72rem', fontWeight:700, color:'#475569', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:12 }}>Risk Factors</div>
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {(briefing.risk_factors || []).map((r, i) => (
              <div key={i} style={{ display:'flex', justifyContent:'space-between', alignItems:'center' }}>
                <span style={{ fontSize:'0.85rem', color:'#cbd5e1' }}>{r.factor}</span>
                <span style={{
                  fontSize:'0.7rem', fontWeight:700,
                  padding:'0.2rem 0.55rem', borderRadius:999,
                  background: `${SEVERITY_COLOR[r.severity]}18`,
                  color: SEVERITY_COLOR[r.severity],
                }}>{r.severity}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="glass-card" style={{ padding:'1.25rem' }}>
          <div style={{ fontSize:'0.72rem', fontWeight:700, color:'#475569', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:12 }}>Recommendations</div>
          <ul style={{ listStyle:'none', display:'flex', flexDirection:'column', gap:8 }}>
            {(briefing.recommendations || []).map((rec, i) => (
              <li key={i} style={{ display:'flex', gap:8, fontSize:'0.85rem', color:'rgba(255,255,255,0.8)' }}>
                <span style={{ color:'#BC6FF1', flexShrink:0 }}>•</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Narrative */}
      <div className="glass-card" style={{ padding:'1.5rem' }}>
        <div style={{ fontSize:'0.72rem', fontWeight:700, color:'#475569', textTransform:'uppercase', letterSpacing:'0.08em', marginBottom:12 }}>Executive Narrative</div>
        <p style={{ fontSize:'0.9rem', color:'#94a3b8', lineHeight:1.75 }}>
          {briefing.executive_narrative || 'No narrative available.'}
        </p>
      </div>
    </div>
  )
}
```

Add `@keyframes slideUp { from{opacity:0;transform:translateY(16px)} to{opacity:1;transform:translateY(0)} }` in `index.css`.

---

## 9. `frontend/src/pages/Dashboard.jsx`

**Data sources:**
- Employees: `GET /api/sim/test-data` → array of employee objects
- Recent jobs: needs `GET /api/llm/orchestrate/status/{job_id}` per stored job — store last 5 job IDs in `localStorage` key `simuorg_job_history` (JSON array)

**Layout:**
1. Page header: `"Dashboard"` H1, subtitle `"Organisational health at a glance"`
2. **KPI row** — 4 `<KpiCard>` components: Total Employees (Users icon, indigo), Attrition Rate % (TrendingDown icon, rose), Avg Job Satisfaction (Star icon, amber), Last Health Score (Activity icon, emerald)
3. **Recent Simulations** table — columns: `Prompt (truncated 60 chars)`, `Status badge`, `Health Score`, `Time since (ago)` — fetched from localStorage job history; click row → navigates to `/simulate` (or just shows the data)
4. **System Status** row — 2 mini cards: "Backend" (ping `/api/sim/test-data`, green/red dot), "Model" (check if employees.length > 0 → "Trained" else "Needs Dataset")

**Session restore for Dashboard:**
```js
// On mount, read localStorage
const history = JSON.parse(localStorage.getItem('simuorg_job_history') || '[]')
// fetch status for each job_id to get health score
```

---

## 10. `frontend/src/pages/UploadData.jsx`

**Two-step flow:**

### Step 1 — Validate
- `POST /api/upload/validate` (multipart with file)
- Shows: `trust_score`, `rows`, `issues` list, `schema_report`

### Step 2 — Ingest
- `POST /api/upload/dataset` (multipart with same file)
- Returns `job_id` → poll `GET /api/upload/status/{job_id}` every 2s
- Show 4-stage progress bar: `Uploading → Parsing → Saving to DB → Training Model`

**Layout:**

```
┌─ UPLOAD DATASET ──────────────────────────────────────┐
│  Upload your HR employee CSV to begin                 │
│                                                       │
│  ┌── Drag & Drop Zone ──────────────────────────────┐ │
│  │  ⬆️  Drag your CSV here, or click to browse      │ │
│  │     CSV files only • Required columns listed     │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  [STEP 1: Validate First]  [STEP 2: Upload & Train]   │
│                                                       │
│  ── Validation Report ───────────────────────────── │
│   Trust Score: 94/100  ██████████░  Rows: 1,470      │
│   ✅ All required columns present                    │
│   ✅ OverTime column detected                        │
│   ⚠️  12 duplicate rows removed                     │
│                                                       │
│  ── Training Progress ───────────────────────────── │
│   ● Uploading  ●─── Parsing ───●── Saving ──●Training│
└───────────────────────────────────────────────────────┘
```

**Drag-and-drop implementation:**
```jsx
// Use onDragOver + onDrop events on a styled div
// onChange on hidden <input type="file" accept=".csv">
// Show filename + size when file is selected
```

**Schema** — required columns list shown in a small expandable section:
`EmployeeID, ManagerID, Department, JobRole, Age, JobSatisfaction, WorkLifeBalance, EnvironmentSatisfaction, YearsAtCompany, TotalWorkingYears, NumCompaniesWorked, YearsWithCurrManager, YearsSinceLastPromotion, JobLevel, MonthlyIncome, Attrition`

**API calls:**
```js
// Step 1
const formData = new FormData()
formData.append('file', file)
const { data } = await API.post('/upload/validate', formData)

// Step 2
const { data } = await API.post('/upload/dataset', formData)
// data.job_id → poll /upload/status/{job_id} every 2000ms
```

---

## 11. `frontend/src/pages/Simulate.jsx` ⭐ CORE PAGE

**Session restore (on mount):**
```js
useEffect(() => {
  const lastJobId  = localStorage.getItem('simuorg_last_job_id')
  const lastPrompt = localStorage.getItem('simuorg_last_prompt')
  if (lastPrompt) setPrompt(lastPrompt)
  if (lastJobId) {
    // fetch status — if completed, restore briefing result
    getOrchestrateStatus(lastJobId).then(({ data }) => {
      if (data.status === 'completed' && data.result) {
        setResult(data.result)
        setStatus('completed')
      }
    }).catch(() => {})
  }
}, [])
```

**State:**
```js
const [prompt, setPrompt]   = useState('')
const [status, setStatus]   = useState(null)   // null | 'queued' | 'running' | 'completed' | 'failed'
const [result, setResult]   = useState(null)   // the full orchestration result
const [error,  setError]    = useState(null)
const [loading, setLoading] = useState(false)
```

**Run handler:**
```js
const handleRun = async () => {
  if (!prompt.trim()) return
  setLoading(true); setResult(null); setError(null); setStatus('queued')
  localStorage.setItem('simuorg_last_prompt', prompt)

  try {
    const result = await orchestrateAndPoll(prompt, (s) => setStatus(s))
    setResult(result)
    setStatus('completed')

    // Store job history
    const { data: { job_id } } = await submitOrchestrate(prompt)  // NOTE: orchestrateAndPoll returns result not job_id
    // ** Fix: orchestrateAndPoll should be modified to also return job_id
    // Store in localStorage
    const history = JSON.parse(localStorage.getItem('simuorg_job_history') || '[]')
    history.unshift({ job_id, prompt: prompt.slice(0, 80), timestamp: Date.now() })
    localStorage.setItem('simuorg_job_history', JSON.stringify(history.slice(0, 10)))
  } catch (err) {
    setStatus('failed')
    setError(err.message)
  } finally {
    setLoading(false)
  }
}
```

> ⚠️ **Fix needed in `api.js`:** `orchestrateAndPoll` currently doesn't return the `job_id`. Modify it to resolve with `{ result, job_id }` instead of just `result`, so we can store the job_id for session restore.

**Layout:**

```
┌─ SIMULATE ──────────────────────────────────────────────┐
│  "Simulate a Policy"                                    │
│  Describe your HR policy in plain English and let      │
│  the AI pipeline do the rest.                         │
│                                                        │
│  ┌─ Prompt textarea ──────────────────────────────┐   │
│  │  e.g. "Reduce overtime by 20% and give all     │   │
│  │        staff a 12% salary raise"               │   │
│  │                                                │   │
│  │                                                │   │
│  └────────────────────────────────────────────────┘   │
│                              [⚡ Run Simulation]        │
│                                                        │
│  ── Status ─────────────────────────────────────────  │
│  [ Intent Parsed ✅ ]──────[ Simulation ⟳ ]──────[ Briefing ○ ]
│                                                        │
│  ── Executive Briefing ─────────────────────────────  │
│  (BriefingPanel renders here when status=completed)    │
└────────────────────────────────────────────────────────┘
```

**Textarea styling:**
```css
width: 100%; min-height: 120px; padding: 1rem 1.25rem;
background: rgba(82,5,123,0.12);
border: 1px solid rgba(188,111,241,0.25);
border-radius: 0.75rem; color: #ffffff;
font-family: 'Inter', sans-serif; font-size: 0.9rem;
resize: vertical; outline: none;
transition: border-color 0.2s, box-shadow 0.2s;
/* focus: */
border-color: #892CDC; box-shadow: 0 0 0 3px rgba(137,44,220,0.18);
```

**Run button:**
```css
display: flex; align-items: center; gap: 8px;
padding: 0.7rem 1.75rem; border-radius: 0.75rem;
background: linear-gradient(135deg, #892CDC, #52057B);
color: white; font-weight: 700; font-size: 0.9rem;
box-shadow: 0 4px 24px rgba(137,44,220,0.45);
border: 1px solid rgba(188,111,241,0.3);
cursor: pointer;
transition: transform 0.15s, box-shadow 0.15s;
/* hover: */
transform: translateY(-2px); box-shadow: 0 8px 32px rgba(137,44,220,0.55);
/* disabled: opacity 0.5; cursor: not-allowed */
```

---

## 12. `frontend/src/pages/Analytics.jsx`

**Data source:** `GET /api/sim/test-data` → returns array of employee objects with fields listed in `REQUIRED_COLUMNS` (schema.py).

**Computed on frontend from raw data (no new backend endpoints):**

| Chart | How to compute |
|-------|---------------|
| Attrition by Dept | Group by `department`, count `attrition === 'Yes'` / total × 100 |
| Satisfaction scatter | Plot `job_satisfaction` (x) vs computed attrition risk (use `attrition === 'Yes'` as 1/0), color by `work_life_balance` |
| Salary histogram | Bin `monthly_income` into brackets: <3k, 3-6k, 6-9k, 9-12k, 12k+ |
| Tenure vs attrition | Group by `years_at_company` (round to int), compute attrition % per year group |

**Filters (state):**
```js
const [deptFilter, setDeptFilter]   = useState('All')
const [roleFilter, setRoleFilter]   = useState('All')
const [levelFilter, setLevelFilter] = useState('All')
const filtered = employees.filter(e =>
  (deptFilter  === 'All' || e.department === deptFilter) &&
  (roleFilter  === 'All' || e.job_role   === roleFilter) &&
  (levelFilter === 'All' || e.job_level  === levelFilter)
)
```

**Recharts config for all charts:**
- `background: transparent`
- Grid: `stroke: rgba(255,255,255,0.06)`
- Axis text: `fill: #475569`, fontSize: 11
- Tooltip: custom dark style (background `#111827`, border `rgba(99,102,241,0.3)`)
- All charts wrapped in `<ResponsiveContainer width="100%" height={260}>`

**Chart colours:**
- Bars: `fill="url(#grad1)"` with a `<linearGradient>` from `#6366f1` to `#a855f7`
- Scatter dots: color mapped from WLB score 1→4 using `#f43f5e → #6366f1 → #10b981`
- Line: `stroke="#6366f1"`, `strokeWidth=2`, dots `fill="#6366f1"`

**Layout — 2×2 grid:**
```jsx
<div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:'1rem' }}>
  <div className="glass-card" style={{ padding:'1.25rem' }}>
    <h3>Attrition Rate by Department</h3>
    <BarChart .../>
  </div>
  <div className="glass-card" style={{ padding:'1.25rem' }}>
    <h3>Satisfaction vs Attrition Risk</h3>
    <ScatterChart .../>
  </div>
  <div className="glass-card" style={{ padding:'1.25rem' }}>
    <h3>Monthly Income Distribution</h3>
    <BarChart ... (bins) />
  </div>
  <div className="glass-card" style={{ padding:'1.25rem' }}>
    <h3>Tenure vs Attrition Rate</h3>
    <LineChart .../>
  </div>
</div>
```

---

## 13. `frontend/src/services/api.js` — Add these wrappers

Add to the **existing** `api.js` (keep all existing functions):

```js
// ── Upload ──────────────────────────────────────────────
export const validateDataset = (file) => {
  const form = new FormData()
  form.append('file', file)
  return API.post('/upload/validate', form)
}

export const uploadDataset = (file) => {
  const form = new FormData()
  form.append('file', file)
  return API.post('/upload/dataset', form)
}

export const getTrainingStatus = (jobId) => API.get(`/upload/status/${jobId}`)

// ── Employees ────────────────────────────────────────────
export const getEmployees = () => API.get('/sim/test-data')
```

Also modify `orchestrateAndPoll` to resolve with `{ result, job_id }`:

```js
export const orchestrateAndPoll = async (userText, onStatus = () => {}, intervalMs = 2500) => {
  const { data: { job_id } } = await submitOrchestrate(userText)
  localStorage.setItem('simuorg_last_job_id', job_id)  // ← persist immediately

  return new Promise((resolve, reject) => {
    const poll = setInterval(async () => {
      try {
        const { data } = await getOrchestrateStatus(job_id)
        onStatus(data.status)
        if (data.status === 'completed') {
          clearInterval(poll)
          resolve({ result: data.result, job_id })   // ← return job_id too
        } else if (data.status === 'failed') {
          clearInterval(poll)
          reject(new Error(data.error || 'Orchestration failed'))
        }
      } catch (err) {
        clearInterval(poll)
        reject(err)
      }
    }, intervalMs)
  })
}
```

---

## 14. Session Handling Summary

| Data | Key in localStorage | Set when | Read when |
|------|--------------------|-----------|-----------| 
| Last job ID | `simuorg_last_job_id` | `orchestrateAndPoll` starts | Simulate tab mounts |
| Last prompt | `simuorg_last_prompt` | User clicks Run | Simulate tab mounts |
| Job history (array of {job_id, prompt, timestamp}) | `simuorg_job_history` | Job completes | Dashboard mounts |

On app load, Simulate tab:
1. Read `simuorg_last_job_id` from localStorage
2. If exists → `GET /api/llm/orchestrate/status/{job_id}`
3. If `status === 'completed'` → set `result` → render `<BriefingPanel />`
4. If `status === 'running'` → re-attach polling (resume stepper)
5. If `status === 'failed'` / not found → silently clear localStorage

---

## 15. Additional CSS keyframes to add to `index.css`

/* Moved to Step 1 in index.css as the core animation/print system */
/* Ensure @keyframes slideUp matches 18px translation for consistency */
```css
@keyframes slideUp {
  from { opacity: 0; transform: translateY(18px); }
  to   { opacity: 1; transform: translateY(0); }
}
```

---

## 16. Employee Object Field Names (from backend)

The `/api/sim/test-data` endpoint returns snake_case fields (SQLModel serialization):

| DB field | JS field |
|----------|---------|
| employee_id | `employee_id` |
| department | `department` |
| job_role | `job_role` |
| monthly_income | `monthly_income` |
| attrition | `attrition` ("Yes"/"No") |
| job_satisfaction | `job_satisfaction` (1-4) |
| work_life_balance | `work_life_balance` (1-4) |
| years_at_company | `years_at_company` |
| job_level | `job_level` (1-5) |

---

## Build Order

1. `index.css` — design tokens first
2. `main.jsx` — BrowserRouter
3. `App.jsx` — routes shell
4. `Sidebar.jsx` — navigation
5. `KpiCard.jsx`, `StatusBadge.jsx` — simple components
6. `Dashboard.jsx` — uses KpiCard + StatusBadge
7. `api.js` — add new wrappers + fix orchestrateAndPoll
8. `StatusStepper.jsx`, `BriefingPanel.jsx` — complex components
9. `Simulate.jsx` — core page
10. `UploadData.jsx` — upload flow
11. `Analytics.jsx` — charts
