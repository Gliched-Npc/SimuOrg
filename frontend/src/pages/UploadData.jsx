import { useState, useRef, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  Upload,
  CheckCircle,
  XCircle,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  FileText,
  ArrowRight,
  Database,
} from "lucide-react";
import {
  validateDataset,
  uploadDataset,
  getTrainingStatus,
  getFeatureImportance,
  getModelMetrics,
  getDatasetMetadata,
} from "../services/api";

const REQUIRED_COLS = [
  "EmployeeID",
  "ManagerID",
  "Department",
  "JobRole",
  "Age",
  "JobSatisfaction",
  "WorkLifeBalance",
  "EnvironmentSatisfaction",
  "YearsAtCompany",
  "TotalWorkingYears",
  "NumCompaniesWorked",
  "YearsWithCurrManager",
  "YearsSinceLastPromotion",
  "JobLevel",
  "MonthlyIncome",
  "Attrition",
];

const TRAIN_STAGES = ["Uploading", "Parsing", "Saving to DB", "Training Model"];

export default function UploadData() {
  const navigate = useNavigate();
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [validation, setValidation] = useState(null); // {trust_score, rows, issues, ...}
  const [shapData, setShapData] = useState(null); // ML feature importance buckets
  const [mlMetrics, setMlMetrics] = useState(null); // quality_report from /api/ml/metrics
  const [datasetMeta, setDatasetMeta] = useState(null); // from /api/upload/metadata
  const [validating, setValidating] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [trainStage, setTrainStage] = useState(-1); // -1 = not started
  const [trainDone, setTrainDone] = useState(false);
  const [schemaOpen, setSchemaOpen] = useState(false);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);
  const pollRef = useRef(null); // holds the status poll setInterval
  const stageRef = useRef(null); // holds the stage animation setInterval

  // ── File Handling ────────────────────────────────────────
  const handleFile = (f) => {
    if (!f || !f.name.endsWith(".csv")) {
      setError("Please upload a valid CSV file.");
      return;
    }
    setFile(f);
    setValidation(null);
    setTrainStage(-1);
    setTrainDone(false);
    setShapData(null);
    setMlMetrics(null);
    setDatasetMeta(null);
    setError(null);
  };

  const onDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFile(e.dataTransfer.files[0]);
  };

  // ── Step 1: Validate ─────────────────────────────────────
  const handleValidate = async () => {
    if (!file) return;
    setValidating(true);
    setValidation(null);
    setError(null);
    try {
      const { data } = await validateDataset(file);
      setValidation(data);
    } catch (err) {
      setError(
        err.response?.data?.detail || "Validation failed — check backend logs.",
      );
    } finally {
      setValidating(false);
    }
  };

  // ── Cleanup helper — always clears both intervals safely ────────────────
  const clearPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (stageRef.current) {
      clearInterval(stageRef.current);
      stageRef.current = null;
    }
  }, []);

  // ── Session Restore ─────────────────────────────────────
  useEffect(() => {
    const lastJob = localStorage.getItem("simuorg_training_job_id");
    if (lastJob) {
      // First, check the current status immediately (don't assume it's still running)
      getTrainingStatus(lastJob)
        .then(({ data: status }) => {
          if (status.status === "completed") {
            // Already done — skip animation, go straight to done state
            localStorage.removeItem("simuorg_training_job_id");
            setTrainStage(4);
            setTrainDone(true);
            setUploading(false);
            Promise.allSettled([
              getFeatureImportance(),
              getModelMetrics(),
            ]).then(([shapRes, metricsRes]) => {
              if (shapRes.status === "fulfilled")
                setShapData(shapRes.value.data.buckets);
              if (metricsRes.status === "fulfilled")
                setMlMetrics(metricsRes.value.data);
            });
          } else if (status.status === "failed") {
            localStorage.removeItem("simuorg_training_job_id");
            setError(status.error || "Training failed");
            setUploading(false);
          } else {
            // Still genuinely running — resume the progress animation
            setUploading(true);
            setTrainStage(1);
            resumePoll(lastJob);
          }
        })
        .catch(() => {
          // If we can't reach the backend, just clear and let user re-upload
          localStorage.removeItem("simuorg_training_job_id");
        });
    } else {
      // Check if dataset already exists
      Promise.allSettled([
        getDatasetMetadata(),
        getFeatureImportance(),
        getModelMetrics(),
      ]).then(([metaRes, shapRes, metricsRes]) => {
        if (
          metaRes.status === "fulfilled" &&
          metricsRes.status === "fulfilled"
        ) {
          setDatasetMeta(metaRes.value.data);
          if (shapRes.status === "fulfilled")
            setShapData(shapRes.value.data.buckets);
          setMlMetrics(metricsRes.value.data);
          setTrainDone(true);
        }
      });
    }

    // Cleanup: clear any running intervals when navigating away from this page
    return () => clearPolling();
  }, [clearPolling]);

  const resumePoll = (job_id) => {
    clearPolling(); // safety: ensure no stale intervals from a previous call

    let stageTimer = 1;
    stageRef.current = setInterval(() => {
      stageTimer = Math.min(stageTimer + 1, 3);
      setTrainStage(stageTimer);
    }, 3000);

    pollRef.current = setInterval(async () => {
      try {
        const { data: status } = await getTrainingStatus(job_id);
        if (status.status === "completed") {
          clearPolling();
          setTrainStage(4);
          setTrainDone(true);
          setUploading(false);
          localStorage.removeItem("simuorg_training_job_id");

          Promise.allSettled([getFeatureImportance(), getModelMetrics()]).then(
            ([shapRes, metricsRes]) => {
              if (shapRes.status === "fulfilled")
                setShapData(shapRes.value.data.buckets);
              if (metricsRes.status === "fulfilled")
                setMlMetrics(metricsRes.value.data);
            },
          );
        } else if (status.status === "failed") {
          clearPolling();
          setError(status.error || "Training failed");
          setUploading(false);
          localStorage.removeItem("simuorg_training_job_id");
        }
      } catch (err) {
        // Network errors handled silently; wait for next tick
      }
    }, 2500);
  };

  // ── Step 2: Upload & Train ───────────────────────────────
  const handleUpload = async () => {
    if (!file) return;
    setUploading(true);
    setTrainStage(0);
    setError(null);

    try {
      const { data } = await uploadDataset(file);
      const { job_id } = data;
      localStorage.setItem("simuorg_training_job_id", job_id);
      localStorage.removeItem("simuorg_job_history");
      setTrainStage(1);
      resumePoll(job_id);
    } catch (err) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Upload failed — check backend logs.",
      );
      setUploading(false);
    }
  };

  const formatBytes = (b) =>
    b > 1048576
      ? `${(b / 1048576).toFixed(1)} MB`
      : `${Math.round(b / 1024)} KB`;

  return (
    <div
      style={{ animation: "fadeIn 0.4s ease", maxWidth: 760, margin: "0 auto" }}
    >
      {/* ── Header ──────────────────────────────────────────── */}
      <div style={{ marginBottom: "2.5rem" }}>
        <h1 className="page-title">Upload Dataset</h1>
        <p className="page-sub">
          Import your HR employee CSV to begin training the simulation model.
        </p>
      </div>

      {/* Global Hidden Input */}
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        style={{ display: "none" }}
        onChange={(e) => handleFile(e.target.files[0])}
      />

      {/* ── Active Dataset Banner ────────────────────────────────────────── */}
      {datasetMeta && !file && (
        <div
          className="glass-card"
          style={{
            padding: "1.5rem",
            marginBottom: "1.5rem",
            border: "1px solid rgba(74,222,128,0.3)",
            background: "rgba(74,222,128,0.05)",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              flexWrap: "wrap",
              gap: 16,
            }}
          >
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  padding: 10,
                  background: "rgba(74,222,128,0.15)",
                  borderRadius: 10,
                }}
              >
                <Database size={24} color="#4ade80" />
              </div>
              <div>
                <div
                  style={{
                    fontWeight: 700,
                    color: "#fff",
                    fontSize: "1.05rem",
                  }}
                >
                  Active Dataset: {datasetMeta.filename}
                </div>
                <div
                  style={{
                    fontSize: "0.85rem",
                    color: "rgba(74,222,128,0.8)",
                    marginTop: 2,
                  }}
                >
                  {Number(datasetMeta.rows).toLocaleString()} employees ·
                  Uploaded {new Date(datasetMeta.uploaded_at).toLocaleString()}
                </div>
              </div>
            </div>
            <button
              onClick={() => inputRef.current?.click()}
              style={{
                padding: "0.65rem 1.25rem",
                borderRadius: 10,
                background: "rgba(0,173,181,0.15)",
                border: "1px solid #00ADB5",
                color: "#fff",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Upload New Dataset
            </button>
          </div>
        </div>
      )}

      {/* ── Drop Zone ────────────────────────────────────────── */}
      {(!datasetMeta || file) && (
        <div
          className="glass-card"
          style={{ padding: "2rem", marginBottom: "1.5rem" }}
        >
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setIsDragging(true);
            }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={onDrop}
            onClick={() => inputRef.current?.click()}
            style={{
              border: `2px dashed ${
                isDragging
                  ? "#00ADB5"
                  : file
                    ? "rgba(74,222,128,0.4)"
                    : "rgba(51,201,207,0.25)"
              }`,
              borderRadius: "1rem",
              padding: "3rem 2rem",
              textAlign: "center",
              cursor: "pointer",
              background: isDragging
                ? "rgba(0,173,181,0.1)"
                : file
                  ? "rgba(74,222,128,0.04)"
                  : "rgba(57,62,70,0.06)",
              transition: "all 0.25s",
            }}
          >
            {file ? (
              <>
                <FileText
                  size={40}
                  color="#4ade80"
                  style={{ margin: "0 auto 1rem", display: "block" }}
                />
                <div
                  style={{
                    fontWeight: 700,
                    fontSize: "1rem",
                    color: "#4ade80",
                  }}
                >
                  {file.name}
                </div>
                <div
                  style={{
                    fontSize: "0.8rem",
                    color: "rgba(51,201,207,0.5)",
                    marginTop: 6,
                  }}
                >
                  {formatBytes(file.size)} · Click to change
                </div>
              </>
            ) : (
              <>
                <Upload
                  size={40}
                  color="rgba(51,201,207,0.4)"
                  style={{ margin: "0 auto 1rem", display: "block" }}
                />
                <div
                  style={{ fontWeight: 700, fontSize: "1rem", color: "#fff" }}
                >
                  Drag & drop your CSV here
                </div>
                <div
                  style={{
                    fontSize: "0.85rem",
                    color: "rgba(51,201,207,0.5)",
                    marginTop: 8,
                  }}
                >
                  or click to browse · CSV files only
                </div>
              </>
            )}
          </div>

          {/* Required Columns Accordion */}
          <div style={{ marginTop: "1.25rem" }}>
            <button
              onClick={() => setSchemaOpen(!schemaOpen)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 6,
                background: "none",
                border: "none",
                cursor: "pointer",
                color: "rgba(51,201,207,0.55)",
                fontSize: "0.78rem",
                fontWeight: 600,
                padding: 0,
              }}
            >
              {schemaOpen ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
              Required columns ({REQUIRED_COLS.length})
            </button>
            {schemaOpen && (
              <div
                style={{
                  marginTop: 10,
                  display: "flex",
                  flexWrap: "wrap",
                  gap: 6,
                  animation: "slideUp 0.2s ease",
                }}
              >
                {REQUIRED_COLS.map((col) => (
                  <span
                    key={col}
                    style={{
                      padding: "0.2rem 0.6rem",
                      borderRadius: 6,
                      background: "rgba(0,173,181,0.1)",
                      border: "1px solid rgba(51,201,207,0.15)",
                      color: "rgba(51,201,207,0.75)",
                      fontSize: "0.72rem",
                      fontFamily: "monospace",
                    }}
                  >
                    {col}
                  </span>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Action Buttons ────────────────────────────────────── */}
      <div style={{ display: "flex", gap: "1rem", marginBottom: "1.5rem" }}>
        <button
          onClick={handleValidate}
          disabled={!file || validating || uploading || trainDone}
          style={{
            flex: 1,
            padding: "0.75rem",
            borderRadius: 10,
            fontWeight: 700,
            fontSize: "0.9rem",
            cursor:
              !file || validating || uploading || trainDone
                ? "not-allowed"
                : "pointer",
            opacity: !file || trainDone ? 0.5 : 1,
            background: "rgba(0,173,181,0.12)",
            border: "1px solid rgba(51,201,207,0.25)",
            color: "#33c9cf",
            transition: "all 0.18s",
          }}
        >
          {validating ? "Validating…" : "Validate First"}
        </button>
        <button
          onClick={handleUpload}
          disabled={!file || uploading || trainDone}
          style={{
            flex: 1,
            padding: "0.75rem",
            borderRadius: 10,
            fontWeight: 700,
            fontSize: "0.9rem",
            cursor: !file || uploading || trainDone ? "not-allowed" : "pointer",
            opacity: !file || trainDone ? 0.5 : 1,
            background: "linear-gradient(135deg, #00ADB5, #007a80)",
            border: "1px solid rgba(51,201,207,0.3)",
            color: "#fff",
            boxShadow: "0 4px 20px rgba(0,173,181,0.35)",
            transition: "all 0.18s",
          }}
        >
          {uploading ? "Training…" : " Upload  & Train"}
        </button>
      </div>

      {/* ── Validation Report ──────────────────────────────────── */}
      {validation && (
        <div
          className="glass-card"
          style={{
            padding: "1.75rem",
            marginBottom: "1.5rem",
            animation: "slideUp 0.3s ease",
          }}
        >
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "flex-start",
              marginBottom: "1.25rem",
            }}
          >
            <div>
              <h3 style={{ fontWeight: 700, fontSize: "1rem", color: "#fff" }}>
                Dataset Validation
              </h3>
              <div
                style={{
                  fontSize: "0.8rem",
                  color: "rgba(51,201,207,0.5)",
                  marginTop: 3,
                }}
              >
                {validation.rows?.toLocaleString()} rows found
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div
                style={{
                  fontSize: "2rem",
                  fontWeight: 900,
                  lineHeight: 1,
                  color:
                    validation.trust_score >= 80
                      ? "#4ade80"
                      : validation.trust_score >= 60
                        ? "#fbbf24"
                        : "#f87171",
                }}
              >
                {validation.trust_score ?? "—"}
              </div>
              <div
                style={{
                  fontSize: "0.65rem",
                  color: "rgba(51,201,207,0.4)",
                  marginTop: 2,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                }}
              >
                Data Readiness Score / 100
              </div>
            </div>
          </div>

          {/* Trust bar */}
          <div
            style={{
              height: 6,
              borderRadius: 3,
              background: "rgba(51,201,207,0.1)",
              marginBottom: "1.25rem",
            }}
          >
            <div
              style={{
                height: "100%",
                width: `${validation.trust_score ?? 0}%`,
                borderRadius: 3,
                background: `linear-gradient(90deg, #00ADB5, ${
                  validation.trust_score >= 80 ? "#4ade80" : "#fbbf24"
                })`,
                transition: "width 0.8s ease",
              }}
            />
          </div>

          {/* Issues */}
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {(validation.issues || []).map((issueObj, i) => {
              const text =
                typeof issueObj === "string"
                  ? issueObj
                  : issueObj.message + " " + issueObj.suggestion;
              const severity =
                issueObj.severity ||
                (text.toLowerCase().includes("error") ? "error" : "info");
              return (
                <div
                  key={i}
                  style={{
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 10,
                    fontSize: "0.85rem",
                  }}
                >
                  {severity === "error" ? (
                    <XCircle
                      size={16}
                      color="#f87171"
                      style={{ flexShrink: 0, marginTop: 2 }}
                    />
                  ) : severity === "warning" ? (
                    <AlertTriangle
                      size={16}
                      color="#fbbf24"
                      style={{ flexShrink: 0, marginTop: 2 }}
                    />
                  ) : (
                    <CheckCircle
                      size={16}
                      color="#4ade80"
                      style={{ flexShrink: 0, marginTop: 2 }}
                    />
                  )}
                  <span style={{ color: "rgba(255,255,255,0.75)" }}>
                    {typeof issueObj === "string" ? (
                      issueObj
                    ) : (
                      <>
                        <div style={{ fontWeight: 600, marginBottom: 4 }}>
                          {issueObj.message}
                        </div>
                        <div style={{ color: "rgba(255,255,255,0.5)" }}>
                          {issueObj.suggestion}
                        </div>
                      </>
                    )}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Training Progress ──────────────────────────────────── */}
      {trainStage >= 0 && (
        <div
          className="glass-card"
          style={{ padding: "1.75rem", animation: "slideUp 0.3s ease" }}
        >
          <h3
            style={{
              fontWeight: 700,
              fontSize: "1rem",
              color: "#fff",
              marginBottom: "1.5rem",
            }}
          >
            Training Pipeline
          </h3>
          <div style={{ display: "flex", alignItems: "center" }}>
            {TRAIN_STAGES.map((stage, i) => (
              <div
                key={stage}
                style={{ display: "flex", alignItems: "center", flex: 1 }}
              >
                <div
                  style={{
                    display: "flex",
                    flexDirection: "column",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: "50%",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      background:
                        trainStage > i
                          ? "rgba(74,222,128,0.15)"
                          : trainStage === i
                            ? "rgba(0,173,181,0.2)"
                            : "rgba(51,201,207,0.06)",
                      border: `2px solid ${
                        trainStage > i
                          ? "#4ade80"
                          : trainStage === i
                            ? "#00ADB5"
                            : "rgba(51,201,207,0.2)"
                      }`,
                      transition: "all 0.4s",
                      boxShadow:
                        trainStage === i
                          ? "0 0 12px rgba(0,173,181,0.4)"
                          : "none",
                    }}
                  >
                    {trainStage > i ? (
                      <CheckCircle size={16} color="#4ade80" />
                    ) : (
                      <span
                        style={{
                          fontSize: "0.7rem",
                          fontWeight: 800,
                          color:
                            trainStage === i
                              ? "#33c9cf"
                              : "rgba(51,201,207,0.3)",
                        }}
                      >
                        {i + 1}
                      </span>
                    )}
                  </div>
                  <span
                    style={{
                      fontSize: "0.7rem",
                      fontWeight: 600,
                      whiteSpace: "nowrap",
                      color:
                        trainStage > i
                          ? "#4ade80"
                          : trainStage === i
                            ? "#33c9cf"
                            : "rgba(51,201,207,0.35)",
                    }}
                  >
                    {stage}
                  </span>
                </div>
                {i < TRAIN_STAGES.length - 1 && (
                  <div
                    style={{
                      flex: 1,
                      height: 2,
                      margin: "0 6px",
                      marginBottom: 26,
                      background:
                        trainStage > i
                          ? "linear-gradient(90deg, #4ade80, #00ADB5)"
                          : "rgba(51,201,207,0.1)",
                      transition: "background 0.6s",
                    }}
                  />
                )}
              </div>
            ))}
          </div>

          {trainDone && (
            <div style={{ animation: "fadeIn 0.5s ease", marginTop: "1.5rem" }}>
              {/* ── Success Banner ── */}
              <div
                style={{
                  padding: "1rem 1.25rem",
                  borderRadius: 10,
                  background: "rgba(74,222,128,0.08)",
                  border: "1px solid rgba(74,222,128,0.2)",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: 10,
                  marginBottom: "1.5rem",
                }}
              >
                <CheckCircle
                  size={20}
                  color="#4ade80"
                  style={{ flexShrink: 0, marginTop: 2 }}
                />
                <div>
                  <div
                    style={{
                      fontWeight: 700,
                      color: "#4ade80",
                      fontSize: "0.9rem",
                    }}
                  >
                    Training Complete &amp; Validated
                  </div>
                  <div
                    style={{
                      fontSize: "0.8rem",
                      color: "rgba(74,222,128,0.6)",
                      marginTop: 2,
                    }}
                  >
                    Model is trained and ready. Review the quality report below
                    before simulating.
                  </div>
                </div>
              </div>

              {/* ── Model Quality Report ── */}
              {mlMetrics && (
                <div
                  style={{
                    borderRadius: 14,
                    border: "1px solid rgba(51,201,207,0.2)",
                    background: "rgba(57,62,70,0.12)",
                    overflow: "hidden",
                    marginBottom: "1.5rem",
                  }}
                >
                  {/* Report Header */}
                  <div
                    style={{
                      padding: "1.25rem 1.5rem",
                      borderBottom: "1px solid rgba(51,201,207,0.12)",
                      display: "flex",
                      justifyContent: "space-between",
                      alignItems: "center",
                    }}
                  >
                    <div>
                      <div
                        style={{
                          fontWeight: 800,
                          fontSize: "0.95rem",
                          color: "#fff",
                        }}
                      >
                        Model Quality Report
                      </div>
                      <div
                        style={{
                          fontSize: "0.72rem",
                          color: "rgba(51,201,207,0.5)",
                          marginTop: 2,
                        }}
                      >
                        Evaluated on held-out test split · XGBoost Attrition
                        Classifier
                      </div>
                    </div>
                    {/* Confidence Badge */}
                    {(() => {
                      const score =
                        mlMetrics.cv_auc_mean ?? mlMetrics.auc_roc ?? null;
                      const pct =
                        score != null ? Math.round(score * 100) : null;
                      const color =
                        pct >= 80
                          ? "#4ade80"
                          : pct >= 70
                            ? "#38bdf8"
                            : pct >= 60
                              ? "#fbbf24"
                              : "#f87171";
                      const label =
                        pct >= 80
                          ? "High Reliability"
                          : pct >= 70
                            ? "Good Reliability"
                            : pct >= 60
                              ? "Moderate Reliability"
                              : "Low Reliability";
                      return pct != null ? (
                        <div style={{ textAlign: "right" }}>
                          <div
                            style={{
                              fontSize: "2.2rem",
                              fontWeight: 900,
                              color,
                              lineHeight: 1,
                            }}
                          >
                            {pct}%
                          </div>
                          <div
                            style={{
                              fontSize: "0.65rem",
                              fontWeight: 700,
                              color,
                              textTransform: "uppercase",
                              letterSpacing: "0.08em",
                              marginTop: 2,
                              opacity: 0.85,
                            }}
                          >
                            {label}
                          </div>
                        </div>
                      ) : null;
                    })()}
                  </div>

                  {/* Metric Bars */}
                  <div
                    style={{
                      padding: "1.25rem 1.5rem",
                      display: "flex",
                      flexDirection: "column",
                      gap: "1rem",
                    }}
                  >
                    {[
                      {
                        label: "Model Reliability Score",
                        key: mlMetrics.cv_auc_mean,
                        desc: `Overall robustness of the predictive model (5-fold cross-validated ± ${
                          mlMetrics.cv_auc_std ?? "?"
                        })`,
                        color:
                          mlMetrics.cv_auc_mean >= 0.8
                            ? "#4ade80"
                            : mlMetrics.cv_auc_mean >= 0.7
                              ? "#38bdf8"
                              : mlMetrics.cv_auc_mean >= 0.6
                                ? "#fbbf24"
                                : "#f87171",
                      },
                    ]
                      .filter((m) => m.key != null)
                      .map(({ label, key, desc, color }) => {
                        const pct = Math.round(key * 100);
                        return (
                          <div key={label}>
                            <div
                              style={{
                                display: "flex",
                                justifyContent: "space-between",
                                marginBottom: 5,
                              }}
                            >
                              <div>
                                <span
                                  style={{
                                    fontSize: "0.82rem",
                                    fontWeight: 700,
                                    color: "#fff",
                                  }}
                                >
                                  {label}
                                </span>
                                <span
                                  style={{
                                    fontSize: "0.72rem",
                                    color: "rgba(51,201,207,0.45)",
                                    marginLeft: 8,
                                  }}
                                >
                                  {desc}
                                </span>
                              </div>
                              <span
                                style={{
                                  fontSize: "0.82rem",
                                  fontWeight: 800,
                                  color,
                                }}
                              >
                                {pct}%
                              </span>
                            </div>
                            <div
                              style={{
                                height: 6,
                                borderRadius: 3,
                                background: "rgba(51,201,207,0.1)",
                              }}
                            >
                              <div
                                style={{
                                  height: "100%",
                                  borderRadius: 3,
                                  width: `${pct}%`,
                                  background: `linear-gradient(90deg, #00ADB5, ${color})`,
                                  transition: "width 1s ease",
                                }}
                              />
                            </div>
                          </div>
                        );
                      })}

                    {/* Advanced Metrics Toggle */}
                    <div style={{ marginTop: "0.5rem" }}>
                      <button
                        onClick={() => setShowAdvanced(!showAdvanced)}
                        style={{
                          display: "inline-flex",
                          alignItems: "center",
                          gap: 6,
                          background: "none",
                          border: "none",
                          padding: "0.4rem 0",
                          color: "rgba(51,201,207,0.6)",
                          fontSize: "0.75rem",
                          fontWeight: 600,
                          cursor: "pointer",
                          transition: "color 0.2s",
                        }}
                        onMouseOver={(e) =>
                          (e.currentTarget.style.color = "#00ADB5")
                        }
                        onMouseOut={(e) =>
                          (e.currentTarget.style.color = "rgba(51,201,207,0.6)")
                        }
                      >
                        {showAdvanced ? "Hide" : "Show"} Advanced Mathematical
                        Diagnostics
                        {showAdvanced ? (
                          <ChevronUp size={14} />
                        ) : (
                          <ChevronDown size={14} />
                        )}
                      </button>

                      {showAdvanced && (
                        <div
                          style={{
                            marginTop: "1rem",
                            padding: "1.25rem",
                            background: "rgba(0,0,0,0.2)",
                            borderRadius: 8,
                            border: "1px dashed rgba(51,201,207,0.2)",
                            display: "grid",
                            gridTemplateColumns: "1fr 1fr",
                            gap: "1rem",
                            animation: "fadeIn 0.3s ease",
                          }}
                        >
                          {[
                            {
                              label: "AUC-ROC (Test)",
                              key: mlMetrics.auc_roc,
                              reason:
                                "Measures how reliably the AI can rank employees by flight risk, ensuring high-risk individuals are prioritised correctly.",
                            },
                            {
                              label: "Test Accuracy",
                              key: mlMetrics.test_accuracy,
                              reason:
                                "A general measure of correct predictions on unseen employees. Shows how often the AI was right when tested on data it never saw during training.",
                            },
                          ]
                            .filter((m) => m.key != null)
                            .map(({ label, key, reason }) => (
                              <div
                                key={label}
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: 4,
                                  background: "rgba(51,201,207,0.05)",
                                  padding: "10px",
                                  borderRadius: "6px",
                                }}
                              >
                                <div
                                  style={{
                                    display: "flex",
                                    justifyContent: "space-between",
                                    alignItems: "center",
                                  }}
                                >
                                  <span
                                    style={{
                                      fontSize: "0.75rem",
                                      color: "rgba(51,201,207,0.8)",
                                      fontWeight: 700,
                                    }}
                                  >
                                    {label}
                                  </span>
                                  <span
                                    style={{
                                      fontSize: "0.75rem",
                                      color: "#fff",
                                      fontWeight: 700,
                                      background: "rgba(51,201,207,0.15)",
                                      padding: "2px 6px",
                                      borderRadius: 4,
                                    }}
                                  >
                                    {Math.round(key * 100)}%
                                  </span>
                                </div>
                                <span
                                  style={{
                                    fontSize: "0.68rem",
                                    color: "rgba(255,255,255,0.45)",
                                    lineHeight: 1.4,
                                  }}
                                >
                                  {reason}
                                </span>
                              </div>
                            ))}
                        </div>
                      )}
                    </div>

                    {/* Signal Strength pill */}
                    {mlMetrics.signal_strength && (
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 8,
                          marginTop: 4,
                        }}
                      >
                        <span
                          style={{
                            fontSize: "0.72rem",
                            color: "rgba(51,201,207,0.5)",
                            fontWeight: 700,
                            textTransform: "uppercase",
                            letterSpacing: "0.08em",
                          }}
                        >
                          Predictive Signal:
                        </span>
                        <span
                          style={{
                            fontSize: "0.72rem",
                            fontWeight: 800,
                            padding: "0.2rem 0.65rem",
                            borderRadius: 999,
                            background:
                              mlMetrics.signal_strength === "excellent"
                                ? "rgba(74,222,128,0.12)"
                                : mlMetrics.signal_strength === "good"
                                  ? "rgba(56,189,248,0.12)"
                                  : mlMetrics.signal_strength === "moderate"
                                    ? "rgba(251,191,36,0.12)"
                                    : "rgba(248,113,113,0.12)",
                            color:
                              mlMetrics.signal_strength === "excellent"
                                ? "#4ade80"
                                : mlMetrics.signal_strength === "good"
                                  ? "#38bdf8"
                                  : mlMetrics.signal_strength === "moderate"
                                    ? "#fbbf24"
                                    : "#f87171",
                            border: `1px solid ${
                              mlMetrics.signal_strength === "excellent"
                                ? "rgba(74,222,128,0.25)"
                                : mlMetrics.signal_strength === "good"
                                  ? "rgba(56,189,248,0.25)"
                                  : mlMetrics.signal_strength === "moderate"
                                    ? "rgba(251,191,36,0.25)"
                                    : "rgba(248,113,113,0.25)"
                            }`,
                            textTransform: "capitalize",
                          }}
                        >
                          {mlMetrics.signal_strength}
                        </span>
                        <span
                          style={{
                            fontSize: "0.72rem",
                            color: "rgba(255,255,255,0.35)",
                          }}
                        >
                          {mlMetrics.simulation_reliable
                            ? "· Simulation results are reliable"
                            : "· Treat projections with caution"}
                        </span>
                      </div>
                    )}

                    {/* Recommendation from ML engine */}
                    {mlMetrics.recommendation &&
                      (() => {
                        const text = mlMetrics.recommendation;
                        let mainDesc = text;
                        let options = [];
                        if (
                          text.includes("SOLUTION:") &&
                          text.includes("[OPTION 1]") &&
                          text.includes("[OPTION 2]")
                        ) {
                          const parts = text.split("SOLUTION:");
                          mainDesc = parts[0].trim();
                          const optParts = parts[1].split("[OPTION 2]");
                          options.push(
                            optParts[0].replace("[OPTION 1]", "").trim(),
                          );
                          options.push(optParts[1].trim());
                        }

                        const isExcellent =
                          mlMetrics.signal_strength === "excellent";
                        const isGood = mlMetrics.signal_strength === "good";
                        const isModerate =
                          mlMetrics.signal_strength === "moderate";

                        const colorTheme = isExcellent
                          ? "#4ade80"
                          : isGood
                            ? "#38bdf8"
                            : isModerate
                              ? "#fbbf24"
                              : "#f87171";
                        const bgTheme = isExcellent
                          ? "rgba(74,222,128,0.08)"
                          : isGood
                            ? "rgba(56,189,248,0.08)"
                            : isModerate
                              ? "rgba(251,191,36,0.08)"
                              : "rgba(248,113,113,0.08)";
                        const borderTheme = isExcellent
                          ? "rgba(74,222,128,0.2)"
                          : isGood
                            ? "rgba(56,189,248,0.2)"
                            : isModerate
                              ? "rgba(251,191,36,0.2)"
                              : "rgba(248,113,113,0.2)";
                        const Icon =
                          isExcellent || isGood ? CheckCircle : AlertTriangle;

                        return (
                          <div
                            style={{
                              marginTop: 8,
                              padding: "1.25rem",
                              borderRadius: 12,
                              background: bgTheme,
                              border: `1px solid ${borderTheme}`,
                            }}
                          >
                            <div
                              style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 8,
                                marginBottom: 8,
                              }}
                            >
                              <Icon size={16} color={colorTheme} />
                              <div
                                style={{
                                  fontSize: "0.72rem",
                                  fontWeight: 800,
                                  color: colorTheme,
                                  textTransform: "uppercase",
                                  letterSpacing: "0.08em",
                                }}
                              >
                                ML Engine Assessment
                              </div>
                            </div>
                            <div
                              style={{
                                fontSize: "0.85rem",
                                color: "rgba(255,255,255,0.9)",
                                lineHeight: 1.5,
                                marginBottom: options.length ? 14 : 0,
                              }}
                            >
                              {mainDesc}
                            </div>

                            {options.length > 0 && (
                              <div
                                style={{
                                  display: "flex",
                                  flexDirection: "column",
                                  gap: 10,
                                }}
                              >
                                {/* Option 1 Box */}
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "flex-start",
                                    gap: 12,
                                    padding: "1rem",
                                    borderRadius: 10,
                                    background: "rgba(74,222,128,0.08)",
                                    border: "1px solid rgba(74,222,128,0.2)",
                                  }}
                                >
                                  <div
                                    style={{
                                      minWidth: 24,
                                      height: 24,
                                      borderRadius: "50%",
                                      background:
                                        "linear-gradient(135deg, #4ade80, #22c55e)",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      color: "#000",
                                      fontSize: "0.75rem",
                                      fontWeight: 800,
                                    }}
                                  >
                                    1
                                  </div>
                                  <div>
                                    <div
                                      style={{
                                        fontSize: "0.75rem",
                                        fontWeight: 800,
                                        color: "#4ade80",
                                        textTransform: "uppercase",
                                        letterSpacing: "0.05em",
                                        marginBottom: 4,
                                      }}
                                    >
                                      Recommended Path
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "rgba(255,255,255,0.85)",
                                        lineHeight: 1.5,
                                      }}
                                    >
                                      {options[0]}
                                    </div>
                                  </div>
                                </div>

                                {/* Option 2 Box */}
                                <div
                                  style={{
                                    display: "flex",
                                    alignItems: "flex-start",
                                    gap: 12,
                                    padding: "1rem",
                                    borderRadius: 10,
                                    background: "rgba(255,255,255,0.03)",
                                    border: "1px dashed rgba(255,255,255,0.15)",
                                  }}
                                >
                                  <div
                                    style={{
                                      minWidth: 24,
                                      height: 24,
                                      borderRadius: "50%",
                                      background: "transparent",
                                      border: "2px solid rgba(255,255,255,0.3)",
                                      display: "flex",
                                      alignItems: "center",
                                      justifyContent: "center",
                                      color: "rgba(255,255,255,0.6)",
                                      fontSize: "0.75rem",
                                      fontWeight: 800,
                                    }}
                                  >
                                    2
                                  </div>
                                  <div>
                                    <div
                                      style={{
                                        fontSize: "0.75rem",
                                        fontWeight: 700,
                                        color: "rgba(255,255,255,0.5)",
                                        textTransform: "uppercase",
                                        letterSpacing: "0.05em",
                                        marginBottom: 4,
                                      }}
                                    >
                                      Alternative
                                    </div>
                                    <div
                                      style={{
                                        fontSize: "0.85rem",
                                        color: "rgba(255,255,255,0.6)",
                                        lineHeight: 1.5,
                                      }}
                                    >
                                      {options[1]}
                                    </div>
                                  </div>
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })()}

                    {/* Top Driving Factors from SHAP */}
                    {shapData?.most_influential?.length > 0 && (
                      <div style={{ marginTop: "0.5rem" }}>
                        <div
                          style={{
                            fontSize: "0.72rem",
                            fontWeight: 700,
                            color: "rgba(51,201,207,0.5)",
                            textTransform: "uppercase",
                            letterSpacing: "0.08em",
                            marginBottom: "0.75rem",
                          }}
                        >
                          Top Attrition Drivers (SHAP)
                        </div>
                        <div
                          style={{
                            display: "flex",
                            flexDirection: "column",
                            gap: 8,
                          }}
                        >
                          {shapData.most_influential
                            .slice(0, 5)
                            .map((item, i) => {
                              const allImportances = [
                                ...(shapData.most_influential || []),
                                ...(shapData.moderately_influential || []),
                                ...(shapData.least_influential || []),
                              ];
                              const maxVal = Math.max(
                                ...allImportances.map((x) => x.importance),
                                0.001,
                              );
                              const barPct = Math.round(
                                (item.importance / maxVal) * 100,
                              );
                              const cleanName = item.feature
                                .replace(/_/g, " ")
                                .replace(/\b\w/g, (c) => c.toUpperCase());
                              const barColor =
                                i === 0
                                  ? "#33c9cf"
                                  : i === 1
                                    ? "#00ADB5"
                                    : "rgba(51,201,207,0.5)";
                              return (
                                <div key={item.feature}>
                                  <div
                                    style={{
                                      display: "flex",
                                      justifyContent: "space-between",
                                      marginBottom: 3,
                                    }}
                                  >
                                    <span
                                      style={{
                                        fontSize: "0.8rem",
                                        color: "rgba(255,255,255,0.8)",
                                      }}
                                    >
                                      {cleanName}
                                    </span>
                                    <span
                                      style={{
                                        fontSize: "0.75rem",
                                        color: barColor,
                                        fontWeight: 700,
                                      }}
                                    >
                                      #{i + 1} driver
                                    </span>
                                  </div>
                                  <div
                                    style={{
                                      height: 5,
                                      borderRadius: 3,
                                      background: "rgba(51,201,207,0.08)",
                                    }}
                                  >
                                    <div
                                      style={{
                                        height: "100%",
                                        borderRadius: 3,
                                        width: `${barPct}%`,
                                        background: barColor,
                                        transition: "width 1s ease",
                                      }}
                                    />
                                  </div>
                                </div>
                              );
                            })}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* ── Go to Simulate CTA ── */}
              <div style={{ marginTop: "1rem", textAlign: "center" }}>
                <button
                  onClick={() => navigate("/simulate")}
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 10,
                    padding: "0.85rem 2.5rem",
                    borderRadius: 12,
                    background: "linear-gradient(135deg, #00ADB5, #007a80)",
                    border: "1px solid rgba(51,201,207,0.4)",
                    color: "#fff",
                    fontSize: "1.05rem",
                    fontWeight: 700,
                    cursor: "pointer",
                    transition: "all 0.2s ease",
                    boxShadow: "0 8px 32px rgba(0,173,181,0.35)",
                    animation: "pulse 2s infinite",
                  }}
                  onMouseOver={(e) =>
                    (e.currentTarget.style.transform = "translateY(-2px)")
                  }
                  onMouseOut={(e) => (e.currentTarget.style.transform = "none")}
                >
                  Go to Simulate <ArrowRight size={20} />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Error Banner ──────────────────────────────────────── */}
      {error && (
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 12,
            padding: "1.25rem 1.5rem",
            borderRadius: 12,
            background: "rgba(248,113,113,0.08)",
            border: "1px solid rgba(248,113,113,0.2)",
            marginTop: "1rem",
          }}
        >
          <XCircle
            size={20}
            color="#f87171"
            style={{ flexShrink: 0, marginTop: 2 }}
          />
          <div>
            <div
              style={{ fontWeight: 700, color: "#f87171", fontSize: "0.9rem" }}
            >
              Error
            </div>
            <div
              style={{
                color: "rgba(248,113,113,0.75)",
                fontSize: "0.85rem",
                marginTop: 4,
              }}
            >
              {error}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
