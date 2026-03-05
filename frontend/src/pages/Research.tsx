import React, { useState } from 'react'

import {
  api,
  type BuildDatasetResponse,
  type DirectionalityResponse,
  type EventStudyResponse,
  type PredictivenessResponse,
} from '../services/api'
import { spacing } from '../theme'

type ExperimentType = 'directionality' | 'event-study' | 'predictiveness'

export const Research: React.FC = () => {
  const [startDay, setStartDay] = useState('2025-01-01')
  const [endDay, setEndDay] = useState('2025-12-31')
  const [horizon, setHorizon] = useState(5)
  const [symbolsInput, setSymbolsInput] = useState('')

  const [buildRunning, setBuildRunning] = useState(false)
  const [buildResult, setBuildResult] = useState<BuildDatasetResponse | null>(null)
  const [buildError, setBuildError] = useState<string | null>(null)

  const [experimentType, setExperimentType] = useState<ExperimentType>('directionality')
  const [datasetPath, setDatasetPath] = useState('')
  const [expK, setExpK] = useState(5)
  const [expH, setExpH] = useState(1)
  const [expWindow, setExpWindow] = useState(20)
  const [expThreshold, setExpThreshold] = useState('p95')
  const [expHorizon, setExpHorizon] = useState(5)
  const [expSplitDate, setExpSplitDate] = useState('')

  const [expRunning, setExpRunning] = useState(false)
  const [expResult, setExpResult] = useState<
    DirectionalityResponse | EventStudyResponse | PredictivenessResponse | null
  >(null)
  const [expError, setExpError] = useState<string | null>(null)

  const handleBuild = () => {
    setBuildRunning(true)
    setBuildError(null)
    setBuildResult(null)
    const symbols = symbolsInput.trim()
      ? symbolsInput.split(/[\s,]+/).filter(Boolean)
      : undefined

    api
      .buildDataset({ start_day: startDay, end_day: endDay, horizon, symbols: symbols ?? undefined })
      .then((res) => {
        setBuildResult(res)
        setDatasetPath(res.path)
      })
      .catch((e) => setBuildError(String(e)))
      .finally(() => setBuildRunning(false))
  }

  const handleRunExperiment = () => {
    const path = datasetPath.trim()
    if (!path) {
      setExpError('Dataset path is required. Build a dataset first or paste a path.')
      return
    }
    setExpRunning(true)
    setExpError(null)
    setExpResult(null)

    const run = () => {
      if (experimentType === 'directionality') {
        return api.runDirectionality({ dataset_path: path, k: expK, h: expH })
      }
      if (experimentType === 'event-study') {
        return api.runEventStudy({
          dataset_path: path,
          window: expWindow,
          threshold: expThreshold,
          horizon: expHorizon,
        })
      }
      return api.runPredictiveness({
        dataset_path: path,
        horizon: expHorizon,
        split_date: expSplitDate || undefined,
      })
    }

    run()
      .then(setExpResult)
      .catch((e) => setExpError(String(e)))
      .finally(() => setExpRunning(false))
  }

  const cardStyle: React.CSSProperties = {
    padding: '12px 16px',
    border: '1px solid #e5e7eb',
    borderRadius: 8,
    marginBottom: spacing.md,
  }

  const inputStyle: React.CSSProperties = {
    padding: '6px 10px',
    borderRadius: 6,
    border: '1px solid #d1d5db',
    fontSize: 14,
    marginRight: 8,
    marginBottom: 8,
  }

  const buttonStyle: React.CSSProperties = {
    padding: '6px 12px',
    borderRadius: 6,
    border: '1px solid #6366f1',
    background: '#6366f1',
    color: '#fff',
    fontWeight: 500,
    cursor: 'pointer',
  }

  const buttonDisabledStyle: React.CSSProperties = {
    ...buttonStyle,
    opacity: 0.6,
    cursor: 'not-allowed',
  }

  return (
    <div>
      <h2 style={{ marginBottom: spacing.lg }}>Research</h2>
      <p style={{ fontSize: 14, color: '#6b7280', marginBottom: spacing.xl }}>
        Build training datasets and run causal experiments (directionality, event study, predictiveness).
        See docs/CAUSAL_RESEARCH.md.
      </p>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0, marginBottom: spacing.md }}>1. Build Dataset</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 8, marginBottom: 12 }}>
          <label>
            Start:
            <input
              type="date"
              value={startDay}
              onChange={(e) => setStartDay(e.target.value)}
              style={inputStyle}
            />
          </label>
          <label>
            End:
            <input
              type="date"
              value={endDay}
              onChange={(e) => setEndDay(e.target.value)}
              style={inputStyle}
            />
          </label>
          <label>
            Horizon:
            <input
              type="number"
              min={1}
              max={30}
              value={horizon}
              onChange={(e) => setHorizon(Number(e.target.value))}
              style={{ ...inputStyle, width: 60 }}
            />
          </label>
          <label>
            Symbols (optional):
            <input
              type="text"
              placeholder="GME, AMC, TSLA"
              value={symbolsInput}
              onChange={(e) => setSymbolsInput(e.target.value)}
              style={{ ...inputStyle, width: 160 }}
            />
          </label>
          <button
            type="button"
            onClick={handleBuild}
            disabled={buildRunning}
            style={buildRunning ? buttonDisabledStyle : buttonStyle}
          >
            {buildRunning ? 'Building…' : 'Build'}
          </button>
        </div>
        {buildError && (
          <div style={{ color: '#b91c1c', fontSize: 14, marginBottom: 8 }} role="alert">
            {buildError}
          </div>
        )}
        {buildResult && (
          <div style={{ fontSize: 14, padding: 8, background: '#f9fafb', borderRadius: 6 }}>
            <div><strong>Path:</strong> {buildResult.path}</div>
            <div>Rows: {buildResult.rows_written} · Labels: {buildResult.labels_rows_upserted} · Features: {buildResult.features_rows_upserted}</div>
            {buildResult.git_sha && <div>Git: {buildResult.git_sha}</div>}
          </div>
        )}
      </div>

      <div style={cardStyle}>
        <h3 style={{ marginTop: 0, marginBottom: spacing.md }}>2. Run Experiment</h3>
        <div style={{ marginBottom: 12 }}>
          <label>
            Dataset path:
            <input
              type="text"
              placeholder="Path from build above, or paste path"
              value={datasetPath}
              onChange={(e) => setDatasetPath(e.target.value)}
              style={{ ...inputStyle, width: 400, display: 'block', marginTop: 4 }}
            />
          </label>
        </div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 12, marginBottom: 12 }}>
          {(['directionality', 'event-study', 'predictiveness'] as const).map((t) => (
            <label key={t} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <input
                type="radio"
                name="expType"
                checked={experimentType === t}
                onChange={() => setExperimentType(t)}
              />
              {t}
            </label>
          ))}
        </div>

        {experimentType === 'directionality' && (
          <div style={{ marginBottom: 12 }}>
            <label style={{ marginRight: 12 }}>
              k: <input type="number" min={1} max={50} value={expK} onChange={(e) => setExpK(Number(e.target.value))} style={{ ...inputStyle, width: 50 }} />
            </label>
            <label>
              h: <input type="number" min={1} max={30} value={expH} onChange={(e) => setExpH(Number(e.target.value))} style={{ ...inputStyle, width: 50 }} />
            </label>
          </div>
        )}
        {experimentType === 'event-study' && (
          <div style={{ marginBottom: 12 }}>
            <label style={{ marginRight: 12 }}>
              window: <input type="number" min={5} max={100} value={expWindow} onChange={(e) => setExpWindow(Number(e.target.value))} style={{ ...inputStyle, width: 50 }} />
            </label>
            <label style={{ marginRight: 12 }}>
              threshold: <input type="text" value={expThreshold} onChange={(e) => setExpThreshold(e.target.value)} style={{ ...inputStyle, width: 60 }} placeholder="p95" />
            </label>
            <label>
              horizon: <input type="number" min={1} max={30} value={expHorizon} onChange={(e) => setExpHorizon(Number(e.target.value))} style={{ ...inputStyle, width: 50 }} />
            </label>
          </div>
        )}
        {experimentType === 'predictiveness' && (
          <div style={{ marginBottom: 12 }}>
            <label style={{ marginRight: 12 }}>
              horizon: <input type="number" min={1} max={30} value={expHorizon} onChange={(e) => setExpHorizon(Number(e.target.value))} style={{ ...inputStyle, width: 50 }} />
            </label>
            <label>
              split_date (optional): <input type="date" value={expSplitDate} onChange={(e) => setExpSplitDate(e.target.value)} style={inputStyle} />
            </label>
          </div>
        )}

        <button
          type="button"
          onClick={handleRunExperiment}
          disabled={expRunning}
          style={expRunning ? buttonDisabledStyle : buttonStyle}
        >
          {expRunning ? 'Running…' : 'Run'}
        </button>
        {expError && (
          <div style={{ color: '#b91c1c', fontSize: 14, marginTop: 8 }} role="alert">
            {expError}
          </div>
        )}
        {expResult && !expRunning && (
          <div style={{ marginTop: 12, padding: 8, background: '#f9fafb', borderRadius: 6, fontFamily: 'monospace', fontSize: 13 }}>
            <pre style={{ margin: 0 }}>{JSON.stringify(expResult, null, 2)}</pre>
          </div>
        )}
      </div>
    </div>
  )
}
