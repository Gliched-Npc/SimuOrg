const COLORS = {
  purple: { grad: "#00ADB5", bg: "rgba(0,173,181,0.15)" },
  lavender: { grad: "#33c9cf", bg: "rgba(51,201,207,0.12)" },
  emerald: { grad: "#4ade80", bg: "rgba(74,222,128,0.12)" },
  amber: { grad: "#fbbf24", bg: "rgba(251,191,36,0.12)" },
  rose: { grad: "#f87171", bg: "rgba(248,113,113,0.12)" },
  info: { grad: "#38bdf8", bg: "rgba(56,189,248,0.12)" },
};

export default function KpiCard({
  label,
  value,
  delta,
  deltaDir,
  icon: Icon,
  color = "purple",
}) {
  const { grad, bg } = COLORS[color] || COLORS.purple;

  return (
    <div
      className="glass-card"
      style={{
        padding: "1.5rem",
        position: "relative",
        overflow: "hidden",
        cursor: "default",
      }}
    >
      {/* Crystalline Accent Edge */}
      <div
        style={{
          position: "absolute",
          top: 0,
          left: 0,
          right: 0,
          height: 3,
          background: `linear-gradient(90deg, transparent, ${grad}, transparent)`,
          opacity: 0.8,
        }}
      />

      {/* Header */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "flex-start",
          marginBottom: 12,
        }}
      >
        <span
          style={{
            fontSize: "0.7rem",
            fontWeight: 600,
            color: "rgba(51,201,207,0.6)",
            textTransform: "uppercase",
            letterSpacing: "0.09em",
          }}
        >
          {label}
        </span>
        {Icon && (
          <div style={{ background: bg, borderRadius: 8, padding: 6 }}>
            <Icon size={15} color={grad} />
          </div>
        )}
      </div>

      {/* Value */}
      <div
        style={{
          fontSize: "2rem",
          fontWeight: 800,
          color: "#ffffff",
          letterSpacing: "-0.03em",
          lineHeight: 1,
        }}
      >
        {value ?? "—"}
      </div>

      {/* Delta */}
      {delta && (
        <div
          style={{
            marginTop: 8,
            fontSize: "0.75rem",
            fontWeight: 600,
            color:
              deltaDir === "up"
                ? "#4ade80"
                : deltaDir === "down"
                  ? "#f87171"
                  : "rgba(51,201,207,0.55)",
          }}
        >
          {deltaDir === "up" ? "▲" : deltaDir === "down" ? "▼" : "·"} {delta}
        </div>
      )}
    </div>
  );
}
