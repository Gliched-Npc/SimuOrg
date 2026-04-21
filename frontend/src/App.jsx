import { useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import Sidebar from './components/Sidebar'
import Dashboard from './pages/Dashboard'
import UploadData from './pages/UploadData'
import Simulate from './pages/Simulate'
import Analytics from './pages/Analytics'
import './App.css'

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(false)

  return (
    <div className="app-shell">
      {/* ── Ambient glow blobs ── */}
      <div className="glow-1" />
      <div className="glow-2" />
      <div className="glow-3" />

      {/* ── Mobile hamburger ── */}
      <button
        className="sidebar-toggle"
        onClick={() => setSidebarOpen(!sidebarOpen)}
        aria-label="Toggle navigation"
      >
        {sidebarOpen
          ? <>
              <span style={{ transform: 'rotate(45deg) translate(5px, 5px)' }} />
              <span style={{ opacity: 0, width: 0 }} />
              <span style={{ transform: 'rotate(-45deg) translate(5px, -5px)' }} />
            </>
          : <>
              <span />
              <span />
              <span />
            </>
        }
      </button>

      {/* ── Mobile overlay backdrop ── */}
      <div
        className={`sidebar-overlay${sidebarOpen ? ' active' : ''}`}
        onClick={() => setSidebarOpen(false)}
      />

      {/* ── Sidebar ── */}
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />

      {/* ── Main content ── */}
      <main className="main-content">
        <Routes>
          <Route path="/"          element={<Dashboard />} />
          <Route path="/upload"    element={<UploadData />} />
          <Route path="/simulate"  element={<Simulate />} />
          <Route path="*"          element={<Dashboard />} />
        </Routes>
      </main>
    </div>
  )
}
