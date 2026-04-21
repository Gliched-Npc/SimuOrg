import { useState, useEffect, useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  AreaChart,
  Area,
  Legend,
} from "recharts";
import {
  getEmployees,
  getModelMetrics,
  getFeatureImportance,
} from "../services/api";

// ── Palette ──────────────────────────────────────────────
const C_PRIMARY = "#00ADB5";
const C_LAVENDER = "#33c9cf";
const C_SUCCESS = "#4ade80";
const C_WARNING = "#fbbf24";
const C_DANGER = "#f87171";
const C_INFO = "#38bdf8";

// ── Chart tooltip component ──────────────────────────────
const GlassTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div
      style={{
        background: "rgba(26,15,53,0.95)",
        backdropFilter: "blur(12px)",
        border: "1px solid rgba(51,201,207,0.3)",
        borderRadius: 10,
        padding: "0.75rem 1rem",
        fontSize: "0.82rem",
        color: "#fff",
      }}
    >
      {label && (
        <div style={{ fontWeight: 700, marginBottom: 6, color: "#33c9cf" }}>
          {label}
        </div>
      )}
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || "#fff", marginTop: 2 }}>
          {p.name}:{" "}
          <strong>
            {typeof p.value === "number" ? p.value.toFixed(1) : p.value}
          </strong>
        </div>
      ))}
    </div>
  );
};

const AXIS_STYLE = { fill: "rgba(51,201,207,0.5)", fontSize: 11 };
const GRID_STROKE = "rgba(51,201,207,0.07)";

// ── Analytics Page ────────────────────────────────────────
export default function Analytics() {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [deptFilter, setDeptFilter] = useState("All");
  const [levelFilter, setLevelFilter] = useState("All");
  const [shapData, setShapData] = useState(null);
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    Promise.all([
      getEmployees().catch(() => ({ data: [] })),
      getFeatureImportance().catch(() => ({ data: null })),
      getModelMetrics().catch(() => ({ data: null })),
    ]).then(([empRes, shapRes, metRes]) => {
      setEmployees(Array.isArray(empRes.data) ? empRes.data : []);

      if (shapRes.data?.buckets) {
        const most = shapRes.data.buckets.most_influential || [];
        const mod = shapRes.data.buckets.moderately_influential || [];
        setShapData(
          [...most, ...mod].slice(0, 8).map((f) => ({
            name: f.feature,
            importance: +(f.importance * 100).toFixed(1),
          })),
        );
      }

      if (metRes.data?.business_recommendation) {
        setMetrics(metRes.data);
      }

      setLoading(false);
    });
  }, []);

  // ── Filtered Dataset ──────────────────────────────────
  const filtered = useMemo(
    () =>
      employees.filter(
        (e) =>
          (deptFilter === "All" || e.department === deptFilter) &&
          (levelFilter === "All" || String(e.job_level) === levelFilter),
      ),
    [employees, deptFilter, levelFilter],
  );

  // ── Unique Filter Options ─────────────────────────────
  const depts = useMemo(
    () => [
      "All",
      ...new Set(employees.map((e) => e.department).filter(Boolean)),
    ],
    [employees],
  );
  const levels = useMemo(
    () =>
      [
        "All",
        ...new Set(
          employees.map((e) => String(e.job_level)).filter(Boolean),
        ).values(),
      ].sort(),
    [employees],
  );

  // ── Chart 1: Attrition by Department ─────────────────
  const attrByDept = useMemo(() => {
    const map = {};
    filtered.forEach((e) => {
      const dept = e.department || "Unknown";
      if (!map[dept]) map[dept] = { dept, yes: 0, total: 0 };
      map[dept].total++;
      if (e.attrition === "Yes") map[dept].yes++;
    });
    return Object.values(map)
      .map((d) => ({
        name: d.dept.slice(0, 12),
        rate: +((d.yes / d.total) * 100).toFixed(1),
      }))
      .sort((a, b) => b.rate - a.rate);
  }, [filtered]);

  // ── Chart 2: Key Attrition Drivers (SHAP) ────────────
  // (Replaces Salary Distribution)
  // ── Chart 3: Tenure vs Attrition ─────────────────────
  const tenureAttr = useMemo(() => {
    const map = {};
    filtered.forEach((e) => {
      const y = Math.min(e.years_at_company ?? 0, 20);
      if (!map[y]) map[y] = { year: y, yes: 0, total: 0 };
      map[y].total++;
      if (e.attrition === "Yes") map[y].yes++;
    });
    return Object.values(map)
      .sort((a, b) => a.year - b.year)
      .map((d) => ({
        year: `Yr ${d.year}`,
        rate: +((d.yes / d.total) * 100).toFixed(1),
      }));
  }, [filtered]);

  // ── Chart 4: Satisfaction Distribution ───────────────
  const satDist = useMemo(() => {
    const map = {
      1: { stayed: 0, left: 0 },
      2: { stayed: 0, left: 0 },
      3: { stayed: 0, left: 0 },
      4: { stayed: 0, left: 0 },
    };
    filtered.forEach((e) => {
      const s = e.job_satisfaction;
      if (s >= 1 && s <= 4) {
        if (e.attrition === "Yes") map[s].left++;
        else map[s].stayed++;
      }
    });
    return [1, 2, 3, 4].map((s) => ({
      name: `Sat ${s}`,
      stayed: map[s].stayed,
      left: map[s].left,
    }));
  }, [filtered]);

  // ── Summary KPIs ──────────────────────────────────────
  const totalFiltered = filtered.length;
  const attrRate =
    totalFiltered > 0
      ? (
          (filtered.filter((e) => e.attrition === "Yes").length /
            totalFiltered) *
          100
        ).toFixed(1)
      : "0.0";
  const avgIncome =
    totalFiltered > 0
      ? Math.round(
          filtered.reduce((s, e) => s + (e.monthly_income || 0), 0) /
            totalFiltered,
        )
      : 0;

  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          height: "60vh",
        }}
      >
        <div style={{ textAlign: "center", color: "rgba(51,201,207,0.5)" }}>
          <div
            style={{
              fontSize: "2rem",
              marginBottom: 12,
              animation: "spin 1.5s linear infinite",
              display: "inline-block",
            }}
          >
            ⟳
          </div>
          <div>Loading analytics pipeline…</div>
        </div>
      </div>
    );
  }

  // Helper to format bold text from LLM strings
  const renderRecommendation = (text) => {
    if (!text) return null;
    return text.split("\\n").map((line, i) => {
      if (!line.trim()) return <br key={i} />;
      const parts = line.split(/(\*\*.*?\*\*)/g);
      return (
        <div key={i} style={{ marginBottom: 6 }}>
          {parts.map((p, j) => {
            if (p.startsWith("**") && p.endsWith("**")) {
              return (
                <strong key={j} style={{ color: "#fff", fontSize: "0.9rem" }}>
                  {p.slice(2, -2)}
                </strong>
              );
            }
            return p;
          })}
        </div>
      );
    });
  };

  if (employees.length === 0) {
    return (
      <div style={{ animation: "fadeIn 0.4s ease" }}>
        <h1 className="page-title" style={{ marginBottom: "0.5rem" }}>
          Analytics
        </h1>
        <p className="page-sub" style={{ marginBottom: "3rem" }}>
          Deep-dive workforce insights
        </p>
        <div
          className="glass-card"
          style={{ padding: "4rem 2rem", textAlign: "center" }}
        >
          <div style={{ fontSize: "3rem", marginBottom: "1rem" }}>📊</div>
          <div style={{ fontWeight: 700, color: "#fff", marginBottom: 8 }}>
            No Data Available
          </div>
          <div style={{ color: "rgba(51,201,207,0.5)", fontSize: "0.9rem" }}>
            Upload an employee dataset first to visualize workforce analytics.
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        animation: "fadeIn 0.4s ease",
        maxWidth: 1200,
        margin: "0 auto",
      }}
    >
      {/* ── Header ─────────────────────────────────────────── */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: "2rem",
          flexWrap: "wrap",
          gap: "1rem",
        }}
      >
        <div>
          <h1 className="page-title">Analytics</h1>
          <p className="page-sub">
            Deep-dive workforce insights · {totalFiltered.toLocaleString()}{" "}
            employees shown
          </p>
        </div>

        {/* Filters */}
        <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap" }}>
          {[
            {
              label: "Department",
              value: deptFilter,
              opts: depts,
              set: setDeptFilter,
            },
            {
              label: "Level",
              value: levelFilter,
              opts: levels,
              set: setLevelFilter,
            },
          ].map(({ label, value, opts, set }) => (
            <select
              key={label}
              value={value}
              onChange={(e) => set(e.target.value)}
              style={{
                padding: "0.5rem 0.9rem",
                borderRadius: 8,
                background: "rgba(57,62,70,0.4)",
                border: "1px solid rgba(51,201,207,0.25)",
                color: "#33c9cf",
                fontSize: "0.82rem",
                fontWeight: 600,
                cursor: "pointer",
                outline: "none",
                backdropFilter: "blur(12px)",
              }}
            >
              {opts.map((o) => (
                <option key={o} value={o} style={{ background: "#1a0f35" }}>
                  {label}: {o}
                </option>
              ))}
            </select>
          ))}
        </div>
      </div>

      {/* ── Mini KPI Strip ─────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))",
          gap: "0.75rem",
          marginBottom: "1.25rem",
        }}
      >
        {[
          {
            label: "Employees",
            value: totalFiltered.toLocaleString(),
            color: C_LAVENDER,
          },
          {
            label: "Attrition %",
            value: `${attrRate}%`,
            color: parseFloat(attrRate) > 20 ? C_DANGER : C_SUCCESS,
          },
          {
            label: "Avg Salary",
            value: `$${avgIncome.toLocaleString()}`,
            color: C_INFO,
          },
        ].map(({ label, value, color }) => (
          <div
            key={label}
            className="glass-card"
            style={{ padding: "1rem 1.25rem", textAlign: "center" }}
          >
            <div
              style={{
                fontSize: "0.65rem",
                color: "rgba(51,201,207,0.45)",
                textTransform: "uppercase",
                letterSpacing: "0.1em",
                marginBottom: 6,
                fontWeight: 700,
              }}
            >
              {label}
            </div>
            <div style={{ fontSize: "1.5rem", fontWeight: 900, color }}>
              {value}
            </div>
          </div>
        ))}
      </div>

      {/* ── Business Diagnostic Banner ─────────────────────── */}
      {metrics?.business_recommendation && (
        <div
          className="glass-card"
          style={{
            padding: "1.5rem 1.75rem",
            marginBottom: "1.75rem",
            borderLeft: `4px solid ${C_SUCCESS}`,
            background: "rgba(74,222,128,0.05)",
          }}
        >
          <h3
            style={{
              fontSize: "0.85rem",
              fontWeight: 800,
              color: C_SUCCESS,
              letterSpacing: "0.05em",
              textTransform: "uppercase",
              marginBottom: "1rem",
            }}
          >
            AI Diagnostic & Strategy
          </h3>
          <div
            style={{
              color: "rgba(255,255,255,0.8)",
              fontSize: "0.85rem",
              lineHeight: 1.6,
            }}
          >
            {renderRecommendation(metrics.business_recommendation)}
          </div>
        </div>
      )}

      {/* ── Chart Grid ─────────────────────────────────────── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(420px, 1fr))",
          gap: "1.25rem",
        }}
      >
        {/* Chart 1 — Attrition by Department */}
        <div className="glass-card" style={{ padding: "1.5rem" }}>
          <h3
            style={{
              fontSize: "0.9rem",
              fontWeight: 700,
              color: "#fff",
              marginBottom: "0.25rem",
            }}
          >
            Attrition Rate by Department
          </h3>
          <p
            style={{
              fontSize: "0.75rem",
              color: "rgba(51,201,207,0.45)",
              marginBottom: "1.25rem",
            }}
          >
            % of staff who left, by team
          </p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={attrByDept}
              margin={{ top: 0, right: 10, left: -20, bottom: 20 }}
            >
              <defs>
                <linearGradient id="grad1" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={C_PRIMARY} stopOpacity={0.9} />
                  <stop offset="100%" stopColor="#007a80" stopOpacity={0.6} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
              <XAxis
                dataKey="name"
                tick={{ ...AXIS_STYLE, fontSize: 10 }}
                angle={-30}
                textAnchor="end"
              />
              <YAxis tick={AXIS_STYLE} unit="%" />
              <Tooltip
                content={<GlassTooltip />}
                cursor={{ fill: "rgba(0,173,181,0.08)" }}
              />
              <Bar
                dataKey="rate"
                fill="url(#grad1)"
                radius={[6, 6, 0, 0]}
                name="Attrition %"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Chart 2 — Key Attrition Drivers (SHAP) */}
        <div className="glass-card" style={{ padding: "1.5rem" }}>
          <h3
            style={{
              fontSize: "0.9rem",
              fontWeight: 700,
              color: "#fff",
              marginBottom: "0.25rem",
            }}
          >
            Key Attrition Drivers
          </h3>
          <p
            style={{
              fontSize: "0.75rem",
              color: "rgba(51,201,207,0.45)",
              marginBottom: "1.25rem",
            }}
          >
            AI-identified factors causing turnover (SHAP %)
          </p>
          <ResponsiveContainer width="100%" height={280}>
            {shapData ? (
              <BarChart
                data={shapData}
                layout="vertical"
                margin={{ top: 0, right: 30, left: 10, bottom: 0 }}
              >
                <defs>
                  <linearGradient id="grad2" x1="0" y1="0" x2="1" y2="0">
                    <stop offset="0%" stopColor={C_INFO} stopOpacity={0.85} />
                    <stop
                      offset="100%"
                      stopColor={C_LAVENDER}
                      stopOpacity={0.5}
                    />
                  </linearGradient>
                </defs>
                <CartesianGrid
                  strokeDasharray="3 3"
                  stroke={GRID_STROKE}
                  horizontal={true}
                  vertical={false}
                />
                <XAxis type="number" tick={AXIS_STYLE} unit="%" />
                <YAxis
                  type="category"
                  dataKey="name"
                  tick={{ ...AXIS_STYLE, fontSize: 10 }}
                  width={90}
                />
                <Tooltip
                  content={<GlassTooltip />}
                  cursor={{ fill: "rgba(0,173,181,0.08)" }}
                />
                <Bar
                  dataKey="importance"
                  fill="url(#grad2)"
                  radius={[0, 4, 4, 0]}
                  name="Impact"
                />
              </BarChart>
            ) : (
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  height: "100%",
                  color: "rgba(51,201,207,0.4)",
                }}
              >
                No SHAP data available
              </div>
            )}
          </ResponsiveContainer>
        </div>

        {/* Chart 3 — Tenure vs Attrition */}
        <div className="glass-card" style={{ padding: "1.5rem" }}>
          <h3
            style={{
              fontSize: "0.9rem",
              fontWeight: 700,
              color: "#fff",
              marginBottom: "0.25rem",
            }}
          >
            Tenure vs Attrition Rate
          </h3>
          <p
            style={{
              fontSize: "0.75rem",
              color: "rgba(51,201,207,0.45)",
              marginBottom: "1.25rem",
            }}
          >
            Attrition % by years at company
          </p>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart
              data={tenureAttr}
              margin={{ top: 0, right: 10, left: -20, bottom: 0 }}
            >
              <defs>
                <linearGradient id="grad3" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor={C_PRIMARY} stopOpacity={0.35} />
                  <stop offset="100%" stopColor={C_PRIMARY} stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
              <XAxis dataKey="year" tick={{ ...AXIS_STYLE, fontSize: 10 }} />
              <YAxis tick={AXIS_STYLE} unit="%" />
              <Tooltip content={<GlassTooltip />} />
              <Area
                type="monotone"
                dataKey="rate"
                stroke={C_LAVENDER}
                strokeWidth={2}
                fill="url(#grad3)"
                name="Attrition %"
                dot={{ fill: C_PRIMARY, strokeWidth: 0, r: 4 }}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>

        {/* Chart 4 — Satisfaction vs Attrition */}
        <div className="glass-card" style={{ padding: "1.5rem" }}>
          <h3
            style={{
              fontSize: "0.9rem",
              fontWeight: 700,
              color: "#fff",
              marginBottom: "0.25rem",
            }}
          >
            Satisfaction vs Attrition
          </h3>
          <p
            style={{
              fontSize: "0.75rem",
              color: "rgba(51,201,207,0.45)",
              marginBottom: "1.25rem",
            }}
          >
            Stayed vs left, grouped by satisfaction score
          </p>
          <ResponsiveContainer width="100%" height={280}>
            <BarChart
              data={satDist}
              margin={{ top: 0, right: 10, left: -20, bottom: 0 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke={GRID_STROKE} />
              <XAxis dataKey="name" tick={AXIS_STYLE} />
              <YAxis tick={AXIS_STYLE} />
              <Tooltip
                content={<GlassTooltip />}
                cursor={{ fill: "rgba(0,173,181,0.08)" }}
              />
              <Legend
                wrapperStyle={{
                  fontSize: "0.78rem",
                  color: "rgba(51,201,207,0.6)",
                }}
              />
              <Bar
                dataKey="stayed"
                fill={C_SUCCESS}
                opacity={0.8}
                radius={[4, 4, 0, 0]}
                name="Stayed"
              />
              <Bar
                dataKey="left"
                fill={C_DANGER}
                opacity={0.8}
                radius={[4, 4, 0, 0]}
                name="Left"
              />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
