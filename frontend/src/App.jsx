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
    setMeshData(null)
    console.log('Sending config:', JSON.stringify(cfg, null, 2))
    console.log('Quality:', q)
    try {
      const controller = new AbortController()
      const timeoutId = setTimeout(() => controller.abort(), 60000) // 60s timeout
      const res = await fetch('/api/wing/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ config: cfg, quality: q }),
        signal: controller.signal
      })
      clearTimeout(timeoutId)
      const data = await res.json()
      console.log('API response:', data)
      if (data.success) {
        setMeshData(data)
      } else {
        alert('Preview failed: ' + (data.error || JSON.stringify(data)))
      }
    } catch (err) {
      console.error('Fetch error:', err)
      alert('Preview failed: ' + (err.name === 'AbortError' ? 'Timeout (try "Low" quality)' : err.message))
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
