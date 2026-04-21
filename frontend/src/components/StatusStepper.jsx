import React from "react";
import { Check, Clock, Loader } from "lucide-react";

export default function StatusStepper({ status }) {
  const steps = [
    {
      label: "Intent Parsed",
      done: ["running", "completed", "failed"].includes(status),
    },
    {
      label: "Simulation Running",
      done: ["completed", "failed"].includes(status),
      active: status === "running",
    },
    { label: "Briefing Ready", done: status === "completed" },
  ];

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 0,
        margin: "2rem 0",
        padding: "0 1rem",
      }}
    >
      {steps.map((step, i) => (
        <React.Fragment key={i}>
          <div
            style={{
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 8,
              minWidth: 100,
            }}
          >
            {/* Circle Container */}
            <div
              style={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: step.done
                  ? "rgba(74,222,128,0.12)"
                  : step.active
                    ? "rgba(0,173,181,0.18)"
                    : "rgba(51,201,207,0.06)",
                border: `2px solid ${
                  step.done
                    ? "#4ade80"
                    : step.active
                      ? "#00ADB5"
                      : "rgba(51,201,207,0.2)"
                }`,
                transition: "all 0.4s ease",
                boxShadow: step.active
                  ? "0 0 15px rgba(0,173,181,0.3)"
                  : "none",
              }}
            >
              {step.done ? (
                <Check size={18} color="#4ade80" />
              ) : step.active ? (
                <Loader
                  size={18}
                  color="#33c9cf"
                  style={{ animation: "spin 1.5s linear infinite" }}
                />
              ) : (
                <Clock size={18} color="rgba(51,201,207,0.4)" />
              )}
            </div>

            {/* Label */}
            <span
              style={{
                fontSize: "0.75rem",
                fontWeight: 600,
                color: step.done
                  ? "#4ade80"
                  : step.active
                    ? "#33c9cf"
                    : "rgba(51,201,207,0.4)",
                whiteSpace: "nowrap",
                transition: "color 0.4s ease",
              }}
            >
              {step.label}
            </span>
          </div>

          {/* Connector line */}
          {i < steps.length - 1 && (
            <div
              style={{
                flex: 1,
                height: 2,
                margin: "0 10px",
                marginBottom: 26,
                background:
                  steps[i + 1].done || step.done
                    ? "linear-gradient(90deg, #4ade80, #00ADB5)"
                    : "rgba(51,201,207,0.1)",
                transition: "background 0.6s ease",
              }}
            />
          )}
        </React.Fragment>
      ))}
    </div>
  );
}
