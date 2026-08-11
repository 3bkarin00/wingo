import React, { useState } from 'react'

const defaultConfig = {
  planform: {
    span_mm: 2400,
    segments: [
      { name: 'center', y_end_frac: 0.20, dihedral_deg: 0.0, sweep_le_deg: 0.0 },
      { name: 'outer', y_end_frac: 1.00, dihedral_deg: 5.0, sweep_le_deg: 5.0 }
    ],
    stations: [
      { y_frac: 0.0, chord_mm: 320, twist_deg: 0.0, airfoil: 'naca23012' },
      { y_frac: 1.0, chord_mm: 180, twist_deg: -2.0, airfoil: 'naca23012' }
    ],
    twist_axis_xc: 0.25,
    mirror: true
  },
  airfoils: {
    sources: ['naca4', 'naca5', 'uiuc', 'dat_upload'],
    resample_points: 199,
    te_min_thickness_mm: 0.8
  },
  skin: {
    face_sheet: { material: 'cfrp_200gsm_twill', plies: 2 },
    core: { material: 'rohacell_31', thickness_mm: 3.0 },
    ramp_ratio: 3.0
  },
  spars: [
    {
      name: 'main',
      xc_root: 0.25,
      xc_tip: 0.25,
      web: { material: 'cfrp_200gsm_twill', plies: 4 },
      tongue: {
        cross_section: 'rect_hollow',
        engagement_mm: 120,
        clearance_mm: 0.2,
        wall_mm: 2.0
      }
    },
    {
      name: 'rear',
      xc_root: 0.70,
      xc_tip: 0.70,
      web: { material: 'cfrp_200gsm_twill', plies: 3 },
      tongue: {
        cross_section: 'rect_hollow',
        engagement_mm: 120,
        clearance_mm: 0.2,
        wall_mm: 2.0
      }
    }
  ],
  ribs: {
    count: 9,
    construction: { material: 'cfrp_200gsm_twill', plies: 3 },
    lightening_holes: { enabled: true, margin_mm: 8 }
  },
  output: { formats: ['step', 'stl', 'gltf'] }
}

export function ConfigPanel({ onPreview, loading, meshData, showPanel, onToggle }) {
  const [config, setConfig] = useState(defaultConfig)
  const [quality, setQuality] = useState('medium')

  const handlePreview = () => {
    onPreview(config, quality)
  }

  return (
    <div style={{
      width: showPanel ? '320px' : '40px',
      minWidth: showPanel ? '320px' : '40px',
      background: '#0f3460',
      borderRight: '1px solid #1a1a4e',
      display: 'flex',
      flexDirection: 'column',
      transition: 'width 0.3s ease',
      overflow: 'hidden'
    }}>
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '12px',
        borderBottom: '1px solid #1a1a4e'
      }}>
        {showPanel && <h2 style={{ fontSize: '16px', fontWeight: 'bold' }}>Wing Config</h2>}
        <button
          onClick={onToggle}
          style={{
            background: 'transparent',
            border: '1px solid #4a9eff',
            color: '#4a9eff',
            padding: '4px 8px',
            borderRadius: '4px',
            cursor: 'pointer',
            fontSize: '12px'
          }}
        >
          {showPanel ? '◀' : '▶'}
        </button>
      </div>

      {showPanel && (
        <div style={{ flex: 1, overflowY: 'auto', padding: '12px' }}>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', color: '#aaa' }}>
              Quality Level
            </label>
            <select
              value={quality}
              onChange={(e) => setQuality(e.target.value)}
              style={{
                width: '100%',
                padding: '8px',
                background: '#1a1a2e',
                border: '1px solid #4a9eff',
                color: '#eee',
                borderRadius: '4px'
              }}
            >
              <option value="low">Low (Preview)</option>
              <option value="medium">Medium (Interactive)</option>
              <option value="high">High (Export)</option>
            </select>
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', color: '#aaa' }}>
              Span (mm)
            </label>
            <input
              type="number"
              value={config.planform.span_mm}
              onChange={(e) => setConfig({
                ...config,
                planform: { ...config.planform, span_mm: parseFloat(e.target.value) || 2400 }
              })}
              style={{
                width: '100%',
                padding: '8px',
                background: '#1a1a2e',
                border: '1px solid #4a9eff',
                color: '#eee',
                borderRadius: '4px'
              }}
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', color: '#aaa' }}>
              Root Chord (mm)
            </label>
            <input
              type="number"
              value={config.planform.stations[0].chord_mm}
              onChange={(e) => {
                const newStations = [...config.planform.stations]
                newStations[0] = { ...newStations[0], chord_mm: parseFloat(e.target.value) || 320 }
                setConfig({ ...config, planform: { ...config.planform, stations: newStations } })
              }}
              style={{
                width: '100%',
                padding: '8px',
                background: '#1a1a2e',
                border: '1px solid #4a9eff',
                color: '#eee',
                borderRadius: '4px'
              }}
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', color: '#aaa' }}>
              Tip Chord (mm)
            </label>
            <input
              type="number"
              value={config.planform.stations[1].chord_mm}
              onChange={(e) => {
                const newStations = [...config.planform.stations]
                newStations[1] = { ...newStations[1], chord_mm: parseFloat(e.target.value) || 180 }
                setConfig({ ...config, planform: { ...config.planform, stations: newStations } })
              }}
              style={{
                width: '100%',
                padding: '8px',
                background: '#1a1a2e',
                border: '1px solid #4a9eff',
                color: '#eee',
                borderRadius: '4px'
              }}
            />
          </div>

          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', color: '#aaa' }}>
              Twist Axis (xc)
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.05"
              value={config.planform.twist_axis_xc}
              onChange={(e) => setConfig({
                ...config,
                planform: { ...config.planform, twist_axis_xc: parseFloat(e.target.value) }
              })}
              style={{ width: '100%' }}
            />
            <div style={{ textAlign: 'center', fontSize: '11px', color: '#666' }}>
              {config.planform.twist_axis_xc}
            </div>
          </div>

          <button
            onClick={handlePreview}
            disabled={loading}
            style={{
              width: '100%',
              padding: '12px',
              background: loading ? '#666' : '#4a9eff',
              border: 'none',
              color: '#fff',
              borderRadius: '4px',
              cursor: loading ? 'not-allowed' : 'pointer',
              fontSize: '14px',
              fontWeight: 'bold'
            }}
          >
            {loading ? 'Building...' : 'Generate Preview'}
          </button>

          {meshData && (
            <div style={{
              marginTop: '16px',
              padding: '12px',
              background: '#1a1a2e',
              borderRadius: '4px',
              fontSize: '12px'
            }}>
              <div style={{ marginBottom: '4px', color: '#4a9eff' }}>Mesh Stats</div>
              <div>Triangles: {meshData.mesh?.[quality]?.triangle_count || 0}</div>
              <div>Vertices: {meshData.mesh?.[quality]?.vertex_count || 0}</div>
              <div>Quality: {meshData.quality}</div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
