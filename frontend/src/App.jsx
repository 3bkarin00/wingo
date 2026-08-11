import React, { useState } from 'react'
import { WingViewer } from './components/WingViewer'
import { ConfigPanel } from './components/ConfigPanel'

export default function App() {
  const [showPanel, setShowPanel] = useState(true)
  const [quality, setQuality] = useState('medium')
  const [config, setConfig] = useState(null)
  const [meshData, setMeshData] = useState(null)
  const [loading, setLoading] = useState(false)

  const handlePreview = async (cfg, q) => {
    setLoading(true)
    setConfig(cfg)
    setQuality(q)
    console.log('Sending config:', JSON.stringify(cfg, null, 2))
    try {
      const res = await fetch('http://localhost:8000/api/wing/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: cfg, quality: q })
      })
      const data = await res.json()
      console.log('API response:', data)
      if (data.success) {
        setMeshData(data)
      } else {
        alert('Preview failed: ' + (data.error || JSON.stringify(data)))
      }
    } catch (err) {
      console.error('Fetch error:', err)
      alert('Preview failed: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{ display: 'flex', width: '100%', height: '100%' }}>
      <ConfigPanel
        onPreview={handlePreview}
        loading={loading}
        meshData={meshData}
        showPanel={showPanel}
        onToggle={() => setShowPanel(!showPanel)}
      />
      <WingViewer
        config={config}
        meshData={meshData}
        quality={quality}
        loading={loading}
        panelVisible={showPanel}
      />
    </div>
  )
}
