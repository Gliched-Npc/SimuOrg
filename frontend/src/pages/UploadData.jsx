import { useState, useRef, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Upload, CheckCircle, XCircle, AlertTriangle, ChevronDown, ChevronUp, FileText, ArrowRight } from 'lucide-react'
import { validateDataset, uploadDataset, getTrainingStatus, getFeatureImportance } from '../services/api'

const REQUIRED_COLS = [
  'EmployeeID','ManagerID','Department','JobRole','Age',
  'JobSatisfaction','WorkLifeBalance','EnvironmentSatisfaction',
  'YearsAtCompany','TotalWorkingYears','NumCompaniesWorked',
  'YearsWithCurrManager','YearsSinceLastPromotion',
  'JobLevel','MonthlyIncome','Attrition',
]

const TRAIN_STAGES = ['Uploading', 'Parsing', 'Saving to DB', 'Training Model']

export default function UploadData() {
  const navigate = useNavigate()
  const [file,          setFile]          = useState(null)
  const [isDragging,    setIsDragging]    = useState(false)
  const [validation,    setValidation]    = useState(null)     // {trust_score, rows, issues, ...}
  const [shapData,      setShapData]      = useState(null)     // ML feature importance buckets
  const [validating,    setValidating]    = useState(false)
  const [uploading,     setUploading]     = useState(false)
  const [trainStage,    setTrainStage]    = useState(-1)       // -1 = not started
  const [trainDone,     setTrainDone]     = useState(false)
  const [schemaOpen,    setSchemaOpen]    = useState(false)
  const [error,         setError]         = useState(null)
  const inputRef = useRef(null)

  // ── File Handling ────────────────────────────────────────
  const handleFile = (f) => {
    if (!f || !f.name.endsWith('.csv')) {
      setError('Please upload a valid CSV file.')
      return
    }
    setFile(f)
    setValidation(null)
    setTrainStage(-1)
    setTrainDone(false)
    setShapData(null)
    setError(null)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setIsDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  // ── Step 1: Validate ─────────────────────────────────────
  const handleValidate = async () => {
    if (!file) return
    setValidating(true)
    setValidation(null)
    setError(null)
    try {
      const { data } = await validateDataset(file)
      setValidation(data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Validation failed — check backend logs.')
    } finally {
      setValidating(false)
    }
  }

  // ── Session Restore ─────────────────────────────────────
  useEffect(() => {
    const lastJob = localStorage.getItem('simuorg_training_job_id')
    if (lastJob) {
      setUploading(true)
      setTrainStage(1)
      resumePoll(lastJob)
    }
  }, [])

  const resumePoll = (job_id) => {
    let stageTimer = 1
    const stageInterval = setInterval(() => {
      stageTimer = Math.min(stageTimer + 1, 3)
      setTrainStage(stageTimer)
    }, 3000)

    const poll = setInterval(async () => {
      try {
        const { data: status } = await getTrainingStatus(job_id)
        if (status.status === 'completed') {
          clearInterval(poll)
          clearInterval(stageInterval)
          setTrainStage(4)
          setTrainDone(true)
          setUploading(false)
          localStorage.removeItem('simuorg_training_job_id')
          
          getFeatureImportance()
            .then(res => setShapData(res.data.buckets))
            .catch(e => console.warn('SHAP fetch failed:', e))
        } else if (status.status === 'failed') {
          clearInterval(poll)
          clearInterval(stageInterval)
          setError(status.error || 'Training failed')
          setUploading(false)
          localStorage.removeItem('simuorg_training_job_id')
        }
      } catch (err) {
        // Network errors handled silently; wait for next tick
      }
    }, 2500)
  }

  // ── Step 2: Upload & Train ───────────────────────────────
  const handleUpload = async () => {
    if (!file) return
    setUploading(true)
    setTrainStage(0)
    setError(null)

    try {
      const { data } = await uploadDataset(file)
      const { job_id } = data
      localStorage.setItem('simuorg_training_job_id', job_id)
      setTrainStage(1)
      resumePoll(job_id)
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Upload failed — check backend logs.')
      setUploading(false)
    }
  }

  const formatBytes = (b) => b > 1048576 ? `${(b/1048576).toFixed(1)} MB` : `${Math.round(b/1024)} KB`

  return (
    <div style={{ animation: 'fadeIn 0.4s ease', maxWidth: 760, margin: '0 auto' }}>
      {/* ── Header ──────────────────────────────────────────── */}
      <div style={{ marginBottom: '2.5rem' }}>
        <h1 className="page-title">Upload Dataset</h1>
        <p className="page-sub">Import your HR employee CSV to begin training the simulation model.</p>
      </div>

      {/* ── Drop Zone ────────────────────────────────────────── */}
      <div className="glass-card" style={{ padding: '2rem', marginBottom: '1.5rem' }}>
        <div
          onDragOver={(e) => { e.preventDefault(); setIsDragging(true) }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          style={{
            border: `2px dashed ${isDragging ? '#892CDC' : file ? 'rgba(74,222,128,0.4)' : 'rgba(188,111,241,0.25)'}`,
            borderRadius: '1rem',
            padding: '3rem 2rem',
            textAlign: 'center',
            cursor: 'pointer',
            background: isDragging ? 'rgba(137,44,220,0.1)' : file ? 'rgba(74,222,128,0.04)' : 'rgba(82,5,123,0.06)',
            transition: 'all 0.25s',
          }}
        >
          <input
            ref={inputRef}
            type="file"
            accept=".csv"
            style={{ display: 'none' }}
            onChange={(e) => handleFile(e.target.files[0])}
          />
          {file ? (
            <>
              <FileText size={40} color="#4ade80" style={{ margin: '0 auto 1rem', display: 'block' }} />
              <div style={{ fontWeight: 700, fontSize: '1rem', color: '#4ade80' }}>{file.name}</div>
              <div style={{ fontSize: '0.8rem', color: 'rgba(188,111,241,0.5)', marginTop: 6 }}>
                {formatBytes(file.size)} · Click to change
              </div>
            </>
          ) : (
            <>
              <Upload size={40} color="rgba(188,111,241,0.4)" style={{ margin: '0 auto 1rem', display: 'block' }} />
              <div style={{ fontWeight: 700, fontSize: '1rem', color: '#fff' }}>
                Drag & drop your CSV here
              </div>
              <div style={{ fontSize: '0.85rem', color: 'rgba(188,111,241,0.5)', marginTop: 8 }}>
                or click to browse · CSV files only
              </div>
            </>
          )}
        </div>

        {/* Required Columns Accordion */}
        <div style={{ marginTop: '1.25rem' }}>
          <button
            onClick={() => setSchemaOpen(!schemaOpen)}
            style={{
              display: 'flex', alignItems: 'center', gap: 6,
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'rgba(188,111,241,0.55)', fontSize: '0.78rem', fontWeight: 600,
              padding: 0,
            }}
          >
            {schemaOpen ? <ChevronUp size={14}/> : <ChevronDown size={14}/>}
            Required columns ({REQUIRED_COLS.length})
          </button>
          {schemaOpen && (
            <div style={{
              marginTop: 10,
              display: 'flex', flexWrap: 'wrap', gap: 6,
              animation: 'slideUp 0.2s ease',
            }}>
              {REQUIRED_COLS.map(col => (
                <span key={col} style={{
                  padding: '0.2rem 0.6rem', borderRadius: 6,
                  background: 'rgba(137,44,220,0.1)',
                  border: '1px solid rgba(188,111,241,0.15)',
                  color: 'rgba(188,111,241,0.75)',
                  fontSize: '0.72rem', fontFamily: 'monospace',
                }}>
                  {col}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Action Buttons ────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
        <button
          onClick={handleValidate}
          disabled={!file || validating || uploading || trainDone}
          style={{
            flex: 1, padding: '0.75rem',
            borderRadius: 10, fontWeight: 700, fontSize: '0.9rem',
            cursor: !file || validating || uploading || trainDone ? 'not-allowed' : 'pointer',
            opacity: !file || trainDone ? 0.5 : 1,
            background: 'rgba(137,44,220,0.12)',
            border: '1px solid rgba(188,111,241,0.25)',
            color: '#BC6FF1',
            transition: 'all 0.18s',
          }}
        >
          {validating ? 'Validating…' : 'Validate First'}
        </button>
        <button
          onClick={handleUpload}
          disabled={!file || uploading || trainDone}
          style={{
            flex: 1, padding: '0.75rem',
            borderRadius: 10, fontWeight: 700, fontSize: '0.9rem',
            cursor: !file || uploading || trainDone ? 'not-allowed' : 'pointer',
            opacity: !file || trainDone ? 0.5 : 1,
            background: 'linear-gradient(135deg, #892CDC, #52057B)',
            border: '1px solid rgba(188,111,241,0.3)',
            color: '#fff',
            boxShadow: '0 4px 20px rgba(137,44,220,0.35)',
            transition: 'all 0.18s',
          }}
        >
          {uploading ? 'Training…' : ' Upload  & Train'}
        </button>
      </div>

      {/* ── Validation Report ──────────────────────────────────── */}
      {validation && (
        <div className="glass-card" style={{ padding: '1.75rem', marginBottom: '1.5rem', animation: 'slideUp 0.3s ease' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1.25rem' }}>
            <div>
              <h3 style={{ fontWeight: 700, fontSize: '1rem', color: '#fff' }}>Validation Report</h3>
              <div style={{ fontSize: '0.8rem', color: 'rgba(188,111,241,0.5)', marginTop: 3 }}>
                {validation.rows?.toLocaleString()} rows found
              </div>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{
                fontSize: '2rem', fontWeight: 900, lineHeight: 1,
                color: validation.trust_score >= 80 ? '#4ade80' : validation.trust_score >= 60 ? '#fbbf24' : '#f87171'
              }}>
                {validation.trust_score ?? '—'}
              </div>
              <div style={{ fontSize: '0.65rem', color: 'rgba(188,111,241,0.4)', marginTop: 2, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                Trust Score / 100
              </div>
            </div>
          </div>

          {/* Trust bar */}
          <div style={{
            height: 6, borderRadius: 3,
            background: 'rgba(188,111,241,0.1)',
            marginBottom: '1.25rem',
          }}>
            <div style={{
              height: '100%',
              width: `${validation.trust_score ?? 0}%`,
              borderRadius: 3,
              background: `linear-gradient(90deg, #892CDC, ${validation.trust_score >= 80 ? '#4ade80' : '#fbbf24'})`,
              transition: 'width 0.8s ease',
            }} />
          </div>

          {/* Issues */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(validation.issues || []).map((issueObj, i) => {
              const text = typeof issueObj === 'string' ? issueObj : (issueObj.message + ' ' + issueObj.suggestion)
              const severity = issueObj.severity || (text.toLowerCase().includes('error') ? 'error' : 'info')
              return (
              <div key={i} style={{ display: 'flex', alignItems: 'flex-start', gap: 10, fontSize: '0.85rem' }}>
                {severity === 'error'
                  ? <XCircle size={16} color="#f87171" style={{ flexShrink: 0, marginTop: 2 }} />
                  : severity === 'warning'
                  ? <AlertTriangle size={16} color="#fbbf24" style={{ flexShrink: 0, marginTop: 2 }} />
                  : <CheckCircle size={16} color="#4ade80" style={{ flexShrink: 0, marginTop: 2 }} />
                }
                <span style={{ color: 'rgba(255,255,255,0.75)' }}>
                  {typeof issueObj === 'string' ? issueObj : (
                    <>
                      <div style={{ fontWeight: 600, marginBottom: 4 }}>{issueObj.message}</div>
                      <div style={{ color: 'rgba(255,255,255,0.5)' }}>{issueObj.suggestion}</div>
                    </>
                  )}
                </span>
              </div>
            )})}
          </div>
        </div>
      )}

      {/* ── Training Progress ──────────────────────────────────── */}
      {trainStage >= 0 && (
        <div className="glass-card" style={{ padding: '1.75rem', animation: 'slideUp 0.3s ease' }}>
          <h3 style={{ fontWeight: 700, fontSize: '1rem', color: '#fff', marginBottom: '1.5rem' }}>
            Training Pipeline
          </h3>
          <div style={{ display: 'flex', alignItems: 'center' }}>
            {TRAIN_STAGES.map((stage, i) => (
              <div key={stage} style={{ display: 'flex', alignItems: 'center', flex: 1 }}>
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
                  <div style={{
                    width: 36, height: 36, borderRadius: '50%',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    background: trainStage > i ? 'rgba(74,222,128,0.15)' : trainStage === i ? 'rgba(137,44,220,0.2)' : 'rgba(188,111,241,0.06)',
                    border: `2px solid ${trainStage > i ? '#4ade80' : trainStage === i ? '#892CDC' : 'rgba(188,111,241,0.2)'}`,
                    transition: 'all 0.4s',
                    boxShadow: trainStage === i ? '0 0 12px rgba(137,44,220,0.4)' : 'none',
                  }}>
                    {trainStage > i
                      ? <CheckCircle size={16} color="#4ade80" />
                      : <span style={{ fontSize: '0.7rem', fontWeight: 800, color: trainStage === i ? '#BC6FF1' : 'rgba(188,111,241,0.3)' }}>{i+1}</span>
                    }
                  </div>
                  <span style={{
                    fontSize: '0.7rem', fontWeight: 600, whiteSpace: 'nowrap',
                    color: trainStage > i ? '#4ade80' : trainStage === i ? '#BC6FF1' : 'rgba(188,111,241,0.35)',
                  }}>
                    {stage}
                  </span>
                </div>
                {i < TRAIN_STAGES.length - 1 && (
                  <div style={{
                    flex: 1, height: 2, margin: '0 6px', marginBottom: 26,
                    background: trainStage > i ? 'linear-gradient(90deg, #4ade80, #892CDC)' : 'rgba(188,111,241,0.1)',
                    transition: 'background 0.6s',
                  }} />
                )}
              </div>
            ))}
          </div>

          {trainDone && (
            <div style={{ animation: 'fadeIn 0.5s ease', marginTop: '1.5rem' }}>
              <div style={{
                padding: '1rem 1.25rem',
                borderRadius: 10, background: 'rgba(74,222,128,0.08)',
                border: '1px solid rgba(74,222,128,0.2)',
                display: 'flex', alignItems: 'flex-start', gap: 10,
              }}>
                <CheckCircle size={20} color="#4ade80" style={{ flexShrink: 0, marginTop: 2 }} />
                <div>
                  <div style={{ fontWeight: 700, color: '#4ade80', fontSize: '0.9rem' }}>
                    Training Complete & Validated
                  </div>
                  <div style={{ fontSize: '0.8rem', color: 'rgba(74,222,128,0.6)', marginTop: 2 }}>
                    Your model is ready — head to Simulate to run policy analysis.
                  </div>
                </div>
              </div>

              {shapData && (
                <div style={{ marginTop: '1.5rem', background: 'rgba(0,0,0,0.2)', borderRadius: 10, padding: '1.25rem' }}>
                  <h4 style={{ fontSize: '0.85rem', color: '#fff', marginBottom: '1rem', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Model Genuinity (Top Features)
                  </h4>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
                    {shapData.most_influential?.slice(0,6).map((item, i) => {
                      const cleanName = item.feature.replace(/([A-Z])/g, ' $1').replace(/_/g, ' ').trim()
                      return (
                        <div key={item.feature} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', borderBottom: '1px solid rgba(188,111,241,0.1)', paddingBottom: '0.25rem' }}>
                          <span style={{ color: 'rgba(255,255,255,0.8)', textTransform: 'capitalize' }}>{cleanName}</span>
                          <span style={{ color: '#4ade80', fontWeight: 600 }}>{(item.importance * 100).toFixed(1)}%</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
              
              <div style={{ marginTop: '2rem', textAlign: 'center' }}>
                <button
                  onClick={() => navigate('/simulate')}
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: 10,
                    padding: '0.85rem 2.5rem', borderRadius: 12,
                    background: 'linear-gradient(135deg, #892CDC, #52057B)',
                    border: '1px solid rgba(188,111,241,0.4)',
                    color: '#fff', fontSize: '1.05rem', fontWeight: 700,
                    cursor: 'pointer', transition: 'all 0.2s ease',
                    boxShadow: '0 8px 32px rgba(137,44,220,0.35)',
                    animation: 'pulse 2s infinite',
                  }}
                  onMouseOver={(e) => e.currentTarget.style.transform = 'translateY(-2px)'}
                  onMouseOut={(e) => e.currentTarget.style.transform = 'none'}
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
        <div style={{
          display: 'flex', alignItems: 'flex-start', gap: 12,
          padding: '1.25rem 1.5rem', borderRadius: 12,
          background: 'rgba(248,113,113,0.08)',
          border: '1px solid rgba(248,113,113,0.2)',
          marginTop: '1rem',
        }}>
          <XCircle size={20} color="#f87171" style={{ flexShrink: 0, marginTop: 2 }} />
          <div>
            <div style={{ fontWeight: 700, color: '#f87171', fontSize: '0.9rem' }}>Error</div>
            <div style={{ color: 'rgba(248,113,113,0.75)', fontSize: '0.85rem', marginTop: 4 }}>{error}</div>
          </div>
        </div>
      )}
    </div>
  )
}
