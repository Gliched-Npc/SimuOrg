const CONFIG = {
  queued: {
    color: "#33c9cf",
    bg: "rgba(51,201,207,0.12)",
    dot: true,
    label: "Queued",
  },
  running: {
    color: "#00ADB5",
    bg: "rgba(0,173,181,0.18)",
    dot: true,
    label: "Running",
  },
  completed: {
    color: "#4ade80",
    bg: "rgba(74,222,128,0.12)",
    dot: false,
    label: "Completed",
  },
  failed: {
    color: "#f87171",
    bg: "rgba(248,113,113,0.12)",
    dot: false,
    label: "Failed",
  },
};

export default function StatusBadge({ status }) {
  const c = CONFIG[status] || CONFIG.queued;
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 5,
        padding: "0.22rem 0.65rem",
        borderRadius: 999,
        background: c.bg,
        color: c.color,
        fontSize: "0.72rem",
        fontWeight: 600,
        border: `1px solid ${c.color}28`,
      }}
    >
      <span
        style={{
          width: 6,
          height: 6,
          borderRadius: "50%",
          background: c.color,
          animation: c.dot ? "pulse 1.4s ease-in-out infinite" : "none",
          flexShrink: 0,
        }}
      />
      {c.label}
    </span>
  );
}
