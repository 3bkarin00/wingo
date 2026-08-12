import React, { useState, useCallback, useRef, useEffect } from 'react'

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

// Professional wing presets
const PRESETS = {
  'RC Bicopter (1.5m)': {
    description: 'Lightweight RC bicopter wing, EPO/EVA foam friendly',
    planform: {
      span_mm: 1500,
      segments: [
        { name: 'root', y_end_frac: 0.5, dihedral_deg: 0, sweep_le_deg: 0 },
        { name: 'tip', y_end_frac: 1.0, dihedral_deg: 3, sweep_le_deg: 12 }
      ],
      stations: [
        { y_frac: 0.0, chord_mm: 140, twist_deg: 1, airfoil: 'naca2412' },
        { y_frac: 0.5, chord_mm: 120, twist_deg: 0.5, airfoil: 'naca2412' },
        { y_frac: 1.0, chord_mm: 80, twist_deg: 0, airfoil: 'naca2408' }
      ],
      twist_axis_xc: 0.25,
      mirror: true
    },
    airfoils: { sources: ['naca4'], resample_points: 127, te_min_thickness_mm: 0.5 },
    skin: { face_sheet: { material: 'EPO_30gsm', plies: 2 }, core: { material: 'EVA_foam', thickness_mm: 5 }, ramp_ratio: 5 },
    spars: [{ name: 'main', xc_root: 0.25, xc_tip: 0.25, web: { material: 'carbon_12gsm', plies: 2 }, tongue: { cross_section: 'rect_hollow', engagement_mm: 10, clearance_mm: 0.5, wall_mm: 1 } }],
    ribs: { count: 7, construction: { material: 'balsa_200kg', plies: 1 }, lightening_holes: { enabled: true, margin_mm: 3 } },
    output: { formats: ['stl'] }
  },
  'Sailplane (2m)': {
    description: 'High-AR sailplane wing, carbon/Nomex construction',
    planform: {
      span_mm: 2000,
      segments: [
        { name: 'root', y_end_frac: 0.4, dihedral_deg: 0, sweep_le_deg: 0 },
        { name: 'mid', y_end_frac: 0.7, dihedral_deg: 2, sweep_le_deg: 0 },
        { name: 'tip', y_end_frac: 1.0, dihedral_deg: 4, sweep_le_deg: 8 }
      ],
      stations: [
        { y_frac: 0.0, chord_mm: 180, twist_deg: 1.5, airfoil: 'naca63-418' },
        { y_frac: 0.4, chord_mm: 150, twist_deg: 1, airfoil: 'naca63-415' },
        { y_frac: 0.7, chord_mm: 120, twist_deg: 0.5, airfoil: 'naca63-412' },
        { y_frac: 1.0, chord_mm: 80, twist_deg: 0, airfoil: 'naca63-410' }
      ],
      twist_axis_xc: 0.25,
      mirror: true
    },
    airfoils: { sources: ['naca4', 'naca5', 'uiuc'], resample_points: 199, te_min_thickness_mm: 0.3 },
    skin: { face_sheet: { material: 'T700/epoxy', plies: 6 }, core: { material: 'Nomex honeycomb', thickness_mm: 8 }, ramp_ratio: 10 },
    spars: [
      { name: 'front', xc_root: 0.28, xc_tip: 0.25, web: { material: 'T700/epoxy', plies: 6 }, tongue: { cross_section: 'rect_hollow', engagement_mm: 15, clearance_mm: 0.3, wall_mm: 1 } },
      { name: 'rear', xc_root: 0.65, xc_tip: 0.6, web: { material: 'T700/epoxy', plies: 4 }, tongue: { cross_section: 'rect_hollow', engagement_mm: 15, clearance_mm: 0.3, wall_mm: 1 } }
    ],
    ribs: { count: 21, construction: { material: 'carbon prepeg', plies: 2 }, lightening_holes: { enabled: true, margin_mm: 2 } },
    hardpoints: { auto: ['hinge_lands', 'joint_housing_zones'] },
    output: { formats: ['step'] }
  },
  'Full-Scale Cessna (9m)': {
    description: 'Scaled to full-size general aviation wing section',
    planform: {
      span_mm: 9000,
      segments: [
        { name: 'root', y_end_frac: 0.3, dihedral_deg: 0, sweep_le_deg: -2 },
        { name: 'mid', y_end_frac: 0.7, dihedral_deg: 5, sweep_le_deg: 0 },
        { name: 'tip', y_end_frac: 1.0, dihedral_deg: 5, sweep_le_deg: 2 }
      ],
      stations: [
        { y_frac: 0.0, chord_mm: 1800, twist_deg: 2, airfoil: 'naca2415' },
        { y_frac: 0.3, chord_mm: 1500, twist_deg: 1.5, airfoil: 'naca2415' },
        { y_frac: 0.7, chord_mm: 1200, twist_deg: 1, airfoil: 'naca2412' },
        { y_frac: 1.0, chord_mm: 800, twist_deg: 0, airfoil: 'naca2410' }
      ],
      twist_axis_xc: 0.25,
      mirror: true
    },
    airfoils: { sources: ['naca4', 'uiuc'], resample_points: 199, te_min_thickness_mm: 1.0 },
    skin: { face_sheet: { material: '2024-T3 aluminum', plies: 1 }, core: { material: 'al honeycomb', thickness_mm: 20 }, ramp_ratio: 8 },
    spars: [
      { name: 'front', xc_root: 0.3, xc_tip: 0.25, web: { material: '2024-T3', plies: 4 }, tongue: { cross_section: 'rect_hollow', engagement_mm: 50, clearance_mm: 1.0, wall_mm: 3 } },
      { name: 'rear', xc_root: 0.6, xc_tip: 0.55, web: { material: '2024-T3', plies: 3 }, tongue: { cross_section: 'rect_hollow', engagement_mm: 50, clearance_mm: 1.0, wall_mm: 3 } }
    ],
    ribs: { count: 30, construction: { material: '2024-T3', plies: 2 }, lightening_holes: { enabled: true, margin_mm: 10 } },
    hardpoints: { auto: ['hinge_lands', 'joint_housing_zones', 'fuselage_bosses', 'fuel_pylons'], fuselage_attachment: { bolts: [{ y_mm: 0, x_c: 0.3, dia_mm: 12 }] } },
    output: { formats: ['step', 'gltf'] }
  },
  'Delta Wing (1m)': {
    description: 'High-speed delta wing, military UAV style',
    planform: {
      span_mm: 1000,
      segments: [
        { name: 'delta', y_end_frac: 1.0, dihedral_deg: 0, sweep_le_deg: 55 }
      ],
      stations: [
        { y_frac: 0.0, chord_mm: 600, twist_deg: 0, airfoil: 'naca0012' },
        { y_frac: 1.0, chord_mm: 50, twist_deg: 0, airfoil: 'naca0012' }
      ],
      twist_axis_xc: 0.5,
      mirror: true
    },
    airfoils: { sources: ['naca4'], resample_points: 127, te_min_thickness_mm: 0.3 },
    skin: { face_sheet: { material: 'T300/epoxy', plies: 4 }, core: { material: 'Nomex honeycomb', thickness_mm: 6 }, ramp_ratio: 8 },
    spars: [{ name: 'main', xc_root: 0.3, xc_tip: 0.3, web: { material: 'T300/epoxy', plies: 4 }, tongue: { cross_section: 'rect_hollow', engagement_mm: 10, clearance_mm: 0.3, wall_mm: 1 } }],
    ribs: { count: 11, construction: { material: 'T300/epoxy', plies: 2 }, lightening_holes: { enabled: false, margin_mm: 0 } },
    output: { formats: ['step', 'stl'] }
  },
  'UAV Test Wing (2.4m)': {
    description: 'UAV test wing, CFRP NACA 2412, 7 stations, AR 8.27',
    planform: {
      span_mm: 2400,
      segments: [
        { name: 'root', y_end_frac: 0.167, dihedral_deg: 0, sweep_le_deg: 0 },
        { name: 'inner', y_end_frac: 0.5, dihedral_deg: 3, sweep_le_deg: 5 },
        { name: 'mid', y_end_frac: 0.833, dihedral_deg: 3, sweep_le_deg: 5 },
        { name: 'tip', y_end_frac: 1.0, dihedral_deg: 3, sweep_le_deg: 5 }
      ],
      stations: [
        { y_frac: 0.0, chord_mm: 400, twist_deg: 2.0, airfoil: 'naca2412' },
        { y_frac: 0.167, chord_mm: 363, twist_deg: 1.8, airfoil: 'naca2412' },
        { y_frac: 0.333, chord_mm: 326, twist_deg: 1.5, airfoil: 'naca2412' },
        { y_frac: 0.5, chord_mm: 289, twist_deg: 1.5, airfoil: 'naca2412' },
        { y_frac: 0.667, chord_mm: 252, twist_deg: 0.7, airfoil: 'naca2412' },
        { y_frac: 0.833, chord_mm: 215, twist_deg: 0.3, airfoil: 'naca2412' },
        { y_frac: 1.0, chord_mm: 180, twist_deg: 0.0, airfoil: 'naca2412' }
      ],
      twist_axis_xc: 0.25,
      mirror: true
    },
    airfoils: { sources: ['naca4', 'uiuc'], resample_points: 199, te_min_thickness_mm: 0.8 },
    skin: { face_sheet: { material: 'CFRP twill', plies: 4 }, core: { material: 'rohacell_31', thickness_mm: 2 }, ramp_ratio: 3 },
    spars: [
      { name: 'main', xc_root: 0.25, xc_tip: 0.25, web: { material: 'CFRP twill', plies: 4 }, tongue: { cross_section: 'rect_hollow', engagement_mm: 20, clearance_mm: 0.2, wall_mm: 2 } },
      { name: 'rear', xc_root: 0.70, xc_tip: 0.70, web: { material: 'CFRP twill', plies: 3 }, tongue: { cross_section: 'rect_hollow', engagement_mm: 20, clearance_mm: 0.2, wall_mm: 2 } }
    ],
    ribs: { count: 9, construction: { material: 'CFRP twill', plies: 3 }, lightening_holes: { enabled: true, margin_mm: 8 } },
    output: { formats: ['step', 'stl', 'gltf'] }
  }
}

// localStorage helpers
const STORAGE_KEY = 'wingo_configs'

function loadSavedConfigs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? JSON.parse(raw) : {}
  } catch { return {} }
}

function saveConfigsToStorage(configs) {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify(configs)) } catch {}
}

function exportConfigJSON(config, name) {
  const blob = new Blob([JSON.stringify({ ...config, _meta: { name, exported: new Date().toISOString() } }, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `${name.replace(/[^a-zA-Z0-9]/g, '_')}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function importConfigJSON(file, onImport) {
  const reader = new FileReader()
  reader.onload = (e) => {
    try {
      const data = JSON.parse(e.target.result)
      const config = data._meta ? data : data
      const name = data._meta?.name || file.name.replace('.json', '')
      onImport(config, name)
    } catch (err) { alert('Invalid JSON config file: ' + err.message) }
  }
  reader.readAsText(file)
}

export function ConfigPanel({ onPreview, loading, meshData, showPanel, onToggle }) {
  const [config, setConfig] = useState(defaultConfig)
  const [quality, setQuality] = useState('low')
  const [savedConfigs, setSavedConfigs] = useState(() => loadSavedConfigs())
  const [showSaved, setShowSaved] = useState(false)
  const [presetFilter, setPresetFilter] = useState('')
  const fileInputRef = React.useRef(null)

  const handlePreview = () => {
    onPreview(config, quality)
  }

  const loadPreset = useCallback((name) => {
    const preset = PRESETS[name]
    if (preset) {
      setConfig(preset)
      setQuality('low')
    }
  }, [])

  // Airfoil upload
  const [uploadedAirfoils, setUploadedAirfoils] = useState([])
  const [airfoilPreview, setAirfoilPreview] = useState(null)
  const [nacaInput, setNacaInput] = useState('')
  const [customCoords, setCustomCoords] = useState('')
  const [customAirfoilName, setCustomAirfoilName] = useState('')
  const [activeTab, setActiveTab] = useState('presets') // presets | stations | airfoils
  const airfoilCanvasRef = useRef(null)

  // Draw airfoil on canvas
  useEffect(() => {
    if (!airfoilPreview || !airfoilCanvasRef.current) return
    const canvas = airfoilCanvasRef.current
    const ctx = canvas.getContext('2d')
    const w = canvas.width, h = canvas.height
    ctx.clearRect(0, 0, w, h)
    ctx.fillStyle = '#1a1a2e'
    ctx.fillRect(0, 0, w, h)
    ctx.strokeStyle = '#4a9eff'
    ctx.lineWidth = 2
    ctx.beginPath()
    const scale = Math.min(w, h) * 0.8
    const offsetX = w / 2 - (Math.max(...airfoilPreview.map(p => p[0])) + Math.min(...airfoilPreview.map(p => p[0]))) / 2 * scale
    const offsetY = h / 2 + (Math.max(...airfoilPreview.map(p => p[1])) + Math.min(...airfoilPreview.map(p => p[1]))) / 2 * scale
    airfoilPreview.forEach((p, i) => {
      const x = p[0] * scale + offsetX
      const y = h - (p[1] * scale + offsetY)
      i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)
    })
    ctx.closePath()
    ctx.stroke()
  }, [airfoilPreview])

  const handleUploadAirfoil = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const formData = new FormData()
    formData.append('file', file)
    try {
      const res = await fetch(`/api/airfoils/upload?name=${encodeURIComponent(file.name.replace('.dat', ''))}`, {
        method: 'POST',
        body: formData
      })
      if (res.ok) {
        const data = await res.json()
        setUploadedAirfoils(prev => [...prev, data.name])
        alert(`Airfoil "${data.name}" uploaded successfully! Use "db:${data.name}" as the airfoil name.`)
      } else {
        const err = await res.json()
        alert('Upload failed: ' + (err.detail || 'Unknown error'))
      }
    } catch (err) {
      alert('Upload failed: ' + err.message)
    }
    e.target.value = ''
  }

  const handleNacaGenerate = () => {
    const code = nacaInput.trim().toLowerCase()
    if (!code) return
    // Fetch from backend NACA generator by building a config with this airfoil
    const testConfig = {
      ...config,
      planform: {
        ...config.planform,
        stations: [{ y_frac: 0, chord_mm: 100, twist_deg: 0, airfoil: code }, ...config.planform.stations.slice(1)]
      }
    }
    // Just validate it works
    fetch('/api/wing/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ config: testConfig, quality: 'low' }),
      signal: AbortSignal.timeout(5000)
    }).then(async res => {
      if (res.ok) {
        alert(`NACA code "${code}" is valid! Add it to your stations.`)
      } else {
        const err = await res.json()
        alert(`Invalid NACA code: ${err.detail || 'Unknown error'}`)
      }
    }).catch(() => alert('Request failed'))
  }

  const handleCustomAirfoil = () => {
    if (!customAirfoilName || !customCoords) { alert('Enter a name and coordinates') ; return }
    const lines = customCoords.trim().split('\n').filter(l => l.trim())
    const coords = []
    for (const line of lines) {
      const parts = line.replace(',', ' ').split().map(Number)
      if (parts.length >= 2 && !isNaN(parts[0]) && !isNaN(parts[1])) {
        coords.push([parts[0], parts[1]])
      }
    }
    if (coords.length < 5) { alert('Need at least 5 coordinate points') ; return }
    // Normalize to unit chord
    const xMin = Math.min(...coords.map(p => p[0]))
    const chord = Math.max(...coords.map(p => p[0])) - xMin || 1
    const normalized = coords.map(p => [(p[0] - xMin) / chord, p[1]])
    if (normalized[0][0] !== normalized[normalized.length - 1][0] ||
        normalized[0][1] !== normalized[normalized.length - 1][1]) {
      normalized.push(normalized[0])
    }
    setAirfoilPreview(normalized)
    // Register as custom airfoil
    setUploadedAirfoils(prev => [...prev, customAirfoilName])
    alert(`Custom airfoil "${customAirfoilName}" created! Use "db:${customAirfoilName}" as the airfoil name.`)
    setCustomCoords('')
  }

  // Station editing
  const addStation = () => {
    const stations = [...config.planform.stations]
    const lastY = stations.length > 0 ? stations[stations.length - 1].y_frac : 0
    stations.push({
      y_frac: Math.min(lastY + 0.25, 1.0),
      chord_mm: 100,
      twist_deg: 0,
      airfoil: 'naca2412'
    })
    setConfig({ ...config, planform: { ...config.planform, stations } })
  }

  const removeStation = (idx) => {
    const stations = config.planform.stations.filter((_, i) => i !== idx)
    if (stations.length < 2) { alert('Need at least 2 stations') ; return }
    setConfig({ ...config, planform: { ...config.planform, stations } })
  }

  const updateStation = (idx, field, value) => {
    const stations = config.planform.stations.map((s, i) =>
      i === idx ? { ...s, [field]: field === 'y_frac' ? Math.max(0, Math.min(1, parseFloat(value) || 0)) :
                         field === 'chord_mm' ? Math.max(10, parseFloat(value) || 100) :
                         field === 'twist_deg' ? parseFloat(value) || 0 : value } : s
    )
    setConfig({ ...config, planform: { ...config.planform, stations } })
  }

  const handleSave = useCallback(() => {
    const name = prompt('Save config as:', 'My Wing')
    if (!name) return
    const key = name.replace(/[^a-zA-Z0-9_]/g, '_')
    const updated = { ...savedConfigs, [key]: { config, name, saved: new Date().toISOString() } }
    setSavedConfigs(updated)
    saveConfigsToStorage(updated)
  }, [config, savedConfigs])

  const handleLoad = useCallback((key) => {
    const entry = savedConfigs[key]
    if (entry) {
      setConfig(entry.config)
      setShowSaved(false)
    }
  }, [savedConfigs])

  const handleDelete = useCallback((key) => {
    const { [key]: _, ...rest } = savedConfigs
    setSavedConfigs(rest)
    saveConfigsToStorage(rest)
  }, [savedConfigs])

  const handleExport = useCallback(() => {
    const name = config._meta?.name || 'wing_config'
    exportConfigJSON(config, name)
  }, [config])

  const handleImportFile = useCallback((e) => {
    const file = e.target.files?.[0]
    if (!file) return
    importConfigJSON(file, (cfg, name) => {
      setConfig(cfg)
      const key = name.replace(/[^a-zA-Z0-9_]/g, '_')
      const updated = { ...savedConfigs, [key]: { config: cfg, name, saved: new Date().toISOString() } }
      setSavedConfigs(updated)
      saveConfigsToStorage(updated)
    })
    e.target.value = ''
  }, [savedConfigs])

  const presetKeys = Object.keys(PRESETS)
  const filteredPresets = presetFilter
    ? presetKeys.filter(k => k.toLowerCase().includes(presetFilter.toLowerCase()))
    : presetKeys

  return (
    <div style={{
      width: showPanel ? '340px' : '40px',
      minWidth: showPanel ? '340px' : '40px',
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
          {/* Quality + Span */}
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', color: '#aaa' }}>Quality</label>
            <select value={quality} onChange={(e) => setQuality(e.target.value)} style={{
              width: '100%', padding: '8px', background: '#1a1a2e', border: '1px solid #4a9eff',
              color: '#eee', borderRadius: '4px'
            }}>
              <option value="low">Low (Preview)</option>
              <option value="medium">Medium (Interactive)</option>
              <option value="high">High (Export)</option>
            </select>
          </div>
          <div style={{ marginBottom: '16px' }}>
            <label style={{ display: 'block', marginBottom: '4px', fontSize: '12px', color: '#aaa' }}>Span (mm)</label>
            <input type="number" value={config.planform.span_mm}
              onChange={(e) => setConfig({...config, planform: {...config.planform, span_mm: parseFloat(e.target.value) || 2400}})}
              style={{ width: '100%', padding: '8px', background: '#1a1a2e', border: '1px solid #4a9eff', color: '#eee', borderRadius: '4px' }} />
          </div>

          {/* Tabs */}
          <div style={{ display: 'flex', gap: '2px', marginBottom: '12px' }}>
            {[['presets','📐 Presets'],['stations','✈️ Stations'],['airfoils','🌀 Airfoils'],['data','💾 Data']].map(([key, label]) => (
              <button key={key} onClick={() => setActiveTab(key)} style={{
                flex: 1, padding: '6px 4px', background: activeTab === key ? '#4a9eff' : 'transparent',
                border: '1px solid #4a9eff', color: activeTab === key ? '#fff' : '#4a9eff',
                borderRadius: '4px 4px 0 0', cursor: 'pointer', fontSize: '10px'
              }}>{label}</button>
            ))}
          </div>

          {/* ── Presets Tab ── */}
          {activeTab === 'presets' && (
            <div>
              <input type="text" placeholder="Filter presets..." value={presetFilter}
                onChange={(e) => setPresetFilter(e.target.value)}
                style={{ width: '100%', padding: '6px', marginBottom: '6px', background: '#1a1a2e', border: '1px solid #4a9eff', color: '#eee', borderRadius: '4px', fontSize: '11px' }} />
              <div style={{ maxHeight: '200px', overflowY: 'auto' }}>
                {filteredPresets.map(name => (
                  <button key={name} onClick={() => loadPreset(name)} title={PRESETS[name].description} style={{
                    width: '100%', padding: '8px', marginBottom: '4px', background: 'transparent',
                    border: '1px solid #2ecc71', color: '#2ecc71', borderRadius: '4px',
                    cursor: 'pointer', fontSize: '11px', textAlign: 'left'
                  }}>{name}</button>
                ))}
                {filteredPresets.length === 0 && <div style={{ fontSize: '11px', color: '#666', padding: '4px' }}>No presets match</div>}
              </div>
            </div>
          )}

          {/* ── Stations Tab ── */}
          {activeTab === 'stations' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                <span style={{ fontSize: '12px', color: '#aaa' }}>{config.planform.stations.length} stations</span>
                <button onClick={addStation} style={{
                  padding: '4px 10px', background: '#2ecc71', border: 'none', color: '#fff',
                  borderRadius: '4px', cursor: 'pointer', fontSize: '11px'
                }}>+ Add Station</button>
              </div>
              <div style={{ maxHeight: '280px', overflowY: 'auto' }}>
                {config.planform.stations.map((st, idx) => (
                  <div key={idx} style={{
                    background: '#1a1a2e', padding: '8px', borderRadius: '4px', marginBottom: '6px',
                    border: '1px solid #333'
                  }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <span style={{ fontSize: '12px', fontWeight: 'bold', color: '#4a9eff' }}>Station {idx + 1}</span>
                      {config.planform.stations.length > 2 && (
                        <button onClick={() => removeStation(idx)} style={{
                          background: 'transparent', border: 'none', color: '#e74c3c',
                          cursor: 'pointer', fontSize: '14px'
                        }}>✕</button>
                      )}
                    </div>
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px' }}>
                      <div>
                        <label style={{ fontSize: '9px', color: '#888' }}>y_frac (0–1)</label>
                        <input type="number" step="0.05" min="0" max="1" value={st.y_frac}
                          onChange={(e) => updateStation(idx, 'y_frac', e.target.value)}
                          style={{ width: '100%', padding: '4px', background: '#0a0a1e', border: '1px solid #444', color: '#eee', borderRadius: '3px', fontSize: '11px' }} />
                      </div>
                      <div>
                        <label style={{ fontSize: '9px', color: '#888' }}>Chord (mm)</label>
                        <input type="number" value={st.chord_mm}
                          onChange={(e) => updateStation(idx, 'chord_mm', e.target.value)}
                          style={{ width: '100%', padding: '4px', background: '#0a0a1e', border: '1px solid #444', color: '#eee', borderRadius: '3px', fontSize: '11px' }} />
                      </div>
                      <div>
                        <label style={{ fontSize: '9px', color: '#888' }}>Twist (°)</label>
                        <input type="number" step="0.5" value={st.twist_deg}
                          onChange={(e) => updateStation(idx, 'twist_deg', e.target.value)}
                          style={{ width: '100%', padding: '4px', background: '#0a0a1e', border: '1px solid #444', color: '#eee', borderRadius: '3px', fontSize: '11px' }} />
                      </div>
                      <div>
                        <label style={{ fontSize: '9px', color: '#888' }}>Airfoil</label>
                        <input type="text" value={st.airfoil}
                          onChange={(e) => updateStation(idx, 'airfoil', e.target.value)}
                          placeholder="naca2412 / db:name"
                          style={{ width: '100%', padding: '4px', background: '#0a0a1e', border: '1px solid #444', color: '#eee', borderRadius: '3px', fontSize: '11px' }} />
                      </div>
                    </div>
                    {uploadedAirfoils.length > 0 && (
                      <div style={{ marginTop: '4px', fontSize: '9px', color: '#666' }}>
                        Available: {uploadedAirfoils.map(a => `db:${a}`).join(', ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ── Airfoils Tab ── */}
          {activeTab === 'airfoils' && (
            <div>
              {/* Upload .dat file */}
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#aaa', marginBottom: '4px' }}>Upload .dat File</label>
                <input type="file" accept=".dat" onChange={handleUploadAirfoil}
                  style={{ width: '100%', padding: '8px', background: '#1a1a2e', border: '1px solid #4a9eff', color: '#eee', borderRadius: '4px', fontSize: '11px' }} />
                {uploadedAirfoils.length > 0 && (
                  <div style={{ marginTop: '6px', fontSize: '10px', color: '#2ecc71' }}>
                    ✓ {uploadedAirfoils.join(', ')}
                  </div>
                )}
              </div>

              {/* NACA code validator */}
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#aaa', marginBottom: '4px' }}>NACA Code Validator</label>
                <div style={{ display: 'flex', gap: '4px' }}>
                  <input type="text" value={nacaInput} onChange={(e) => setNacaInput(e.target.value)}
                    placeholder="naca2412"
                    style={{ flex: 1, padding: '6px', background: '#1a1a2e', border: '1px solid #4a9eff', color: '#eee', borderRadius: '4px', fontSize: '11px' }} />
                  <button onClick={handleNacaGenerate} style={{
                    padding: '6px 10px', background: '#9b59b6', border: 'none', color: '#fff',
                    borderRadius: '4px', cursor: 'pointer', fontSize: '11px'
                  }}>✓</button>
                </div>
              </div>

              {/* Custom coordinates */}
              <div style={{ marginBottom: '12px' }}>
                <label style={{ display: 'block', fontSize: '12px', color: '#aaa', marginBottom: '4px' }}>Custom Airfoil (x y coords)</label>
                <input type="text" value={customAirfoilName} onChange={(e) => setCustomAirfoilName(e.target.value)}
                  placeholder="Name"
                  style={{ width: '100%', padding: '4px', marginBottom: '4px', background: '#1a1a2e', border: '1px solid #4a9eff', color: '#eee', borderRadius: '4px', fontSize: '11px' }} />
                <textarea value={customCoords} onChange={(e) => setCustomCoords(e.target.value)}
                  placeholder={"0.0 0.0\n0.25 0.05\n0.5 0.06\n0.75 0.03\n1.0 0.0\n0.75 -0.02\n0.25 -0.03\n0.0 0.0"}
                  rows={5}
                  style={{ width: '100%', padding: '4px', background: '#1a1a2e', border: '1px solid #4a9eff', color: '#eee', borderRadius: '4px', fontSize: '10px', fontFamily: 'monospace', resize: 'vertical' }} />
                <button onClick={handleCustomAirfoil} style={{
                  width: '100%', padding: '6px', marginTop: '4px', background: '#e67e22', border: 'none',
                  color: '#fff', borderRadius: '4px', cursor: 'pointer', fontSize: '11px'
                }}>Create Airfoil</button>
              </div>

              {/* Preview canvas */}
              {airfoilPreview && (
                <div>
                  <label style={{ display: 'block', fontSize: '12px', color: '#aaa', marginBottom: '4px' }}>Preview</label>
                  <canvas ref={airfoilCanvasRef} width={200} height={100}
                    style={{ width: '100%', background: '#1a1a2e', borderRadius: '4px', border: '1px solid #333' }} />
                </div>
              )}
            </div>
          )}

          {/* ── Data Tab ── */}
          {activeTab === 'data' && (
            <div>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px', marginBottom: '12px' }}>
                <button onClick={handleSave} style={{
                  padding: '8px', background: 'transparent', border: '1px solid #3498db',
                  color: '#3498db', borderRadius: '4px', cursor: 'pointer', fontSize: '11px'
                }}>💾 Save</button>
                <button onClick={handleExport} style={{
                  padding: '8px', background: 'transparent', border: '1px solid #9b59b6',
                  color: '#9b59b6', borderRadius: '4px', cursor: 'pointer', fontSize: '11px'
                }}>📤 Export JSON</button>
                <button onClick={() => fileInputRef.current?.click()} style={{
                  padding: '8px', background: 'transparent', border: '1px solid #e67e22',
                  color: '#e67e22', borderRadius: '4px', cursor: 'pointer', fontSize: '11px'
                }}>📥 Import JSON</button>
                <button onClick={() => setShowSaved(!showSaved)} style={{
                  padding: '8px', background: 'transparent', border: '1px solid #1abc9c',
                  color: '#1abc9c', borderRadius: '4px', cursor: 'pointer', fontSize: '11px'
                }}>📋 Load ({Object.keys(savedConfigs).length})</button>
              </div>
              <input ref={fileInputRef} type="file" accept=".json" style={{ display: 'none' }}
                onChange={handleImportFile} />

              {showSaved && Object.keys(savedConfigs).length > 0 && (
                <div style={{ maxHeight: '120px', overflowY: 'auto' }}>
                  {Object.entries(savedConfigs).map(([key, entry]) => (
                    <div key={key} style={{
                      display: 'flex', gap: '4px', marginBottom: '3px',
                      background: '#1a1a2e', padding: '4px', borderRadius: '4px'
                    }}>
                      <button onClick={() => handleLoad(key)} style={{
                        flex: 1, padding: '4px', background: 'transparent',
                        border: '1px solid #1abc9c', color: '#1abc9c',
                        borderRadius: '3px', cursor: 'pointer', fontSize: '10px'
                      }}>Load</button>
                      <button onClick={() => handleDelete(key)} style={{
                        padding: '4px 8px', background: 'transparent',
                        border: '1px solid #e74c3c', color: '#e74c3c',
                        borderRadius: '3px', cursor: 'pointer', fontSize: '10px'
                      }}>✕</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

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
              fontWeight: 'bold',
              marginTop: '12px'
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
