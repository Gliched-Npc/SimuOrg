import { NavLink } from "react-router-dom";
import { LayoutDashboard, Upload, Zap, BarChart2 } from "lucide-react";
import logo from "../assets/logo.png";

const links = [
  { to: "/", label: "Dashboard", icon: LayoutDashboard },
  { to: "/upload", label: "Upload", icon: Upload },
  { to: "/simulate", label: "Simulate", icon: Zap },
];

export default function Sidebar({ open, onClose }) {
  return (
    <aside
      className={open ? "open" : ""}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "220px",
        height: "100vh",
        background: "rgba(57, 62, 70, 0.65)",
        backdropFilter: "blur(80px)",
        WebkitBackdropFilter: "blur(80px)",
        borderRight: "1px solid rgba(51,201,207,0.25)",
        boxShadow: "inset 1px 0 0 rgba(255,255,255,0.05)",
        display: "flex",
        flexDirection: "column",
        zIndex: 100,
      }}
    >
      {/* ── Logo ── */}
      <div
        style={{
          padding: "1.5rem 1.25rem 1rem",
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <img
          src={logo}
          alt="SimuOrg"
          style={{
            width: 48,
            height: 48,
            borderRadius: "14px",
            objectFit: "contain",
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.15)",
            filter: "drop-shadow(0 8px 16px rgba(0,0,0,0.4))",
            padding: "4px",
            flexShrink: 0,
            transition: "transform 0.3s ease",
          }}
        />
        <div>
          <div
            style={{
              fontWeight: 800,
              fontSize: "1rem",
              color: "#ffffff",
              lineHeight: 1.1,
            }}
          >
            SimuOrg
          </div>
          <div
            style={{
              fontSize: "0.58rem",
              color: "rgba(51,201,207,0.65)",
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              marginTop: 3,
            }}
          >
            Intelligence Platform
          </div>
        </div>
      </div>

      {/* ── Divider ── */}
      <div
        style={{
          height: 1,
          background: "rgba(51,201,207,0.15)",
          margin: "0 1rem 0.75rem",
        }}
      />

      {/* ── Nav ── */}
      <nav style={{ flex: 1, padding: "0 0.6rem", overflowY: "auto" }}>
        {links.map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            onClick={onClose}
            style={({ isActive }) => ({
              display: "flex",
              alignItems: "center",
              gap: 10,
              padding: "0.65rem 1rem",
              borderRadius: "0.6rem",
              margin: "0.2rem 0",
              textDecoration: "none",
              fontSize: "0.875rem",
              fontWeight: isActive ? 600 : 500,
              color: isActive ? "#ffffff" : "rgba(255,255,255,0.6)",
              background: isActive ? "rgba(255,255,255,0.15)" : "transparent",
              borderLeft: isActive
                ? "3px solid #33c9cf"
                : "3px solid transparent",
              transition: "all 0.18s ease",
            })}
            onMouseOver={(e) => {
              const isActive =
                e.currentTarget.style.borderLeft.includes("#33c9cf");
              if (!isActive)
                e.currentTarget.style.background = "rgba(255,255,255,0.08)";
            }}
            onMouseOut={(e) => {
              const isActive =
                e.currentTarget.style.borderLeft.includes("#33c9cf");
              if (!isActive) e.currentTarget.style.background = "transparent";
            }}
          >
            <Icon size={17} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* ── Footer ── */}
      <div
        style={{
          padding: "1rem 1.25rem",
          fontSize: "0.68rem",
          color: "rgba(51,201,207,0.35)",
          borderTop: "1px solid rgba(51,201,207,0.1)",
        }}
      >
        SimuOrg v1.0 · FastAPI · React
      </div>
    </aside>
  );
}
