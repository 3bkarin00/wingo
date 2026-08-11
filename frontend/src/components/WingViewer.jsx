import React, { useRef, useMemo } from 'react'
import { Canvas } from '@react-three/fiber'
import { OrbitControls } from '@react-three/drei'
import * as THREE from 'three'

function WingMesh({ vertices, indices, color = '#4a9eff' }) {
  const meshRef = useRef()

  const geometry = useMemo(() => {
    const geo = new THREE.BufferGeometry()
    const posArray = new Float32Array(vertices)
    const indexArray = new Uint32Array(indices)
    geo.setAttribute('position', new THREE.BufferAttribute(posArray, 3))
    geo.setIndex(new THREE.BufferAttribute(indexArray, 1))
    geo.computeVertexNormals()
    return geo
  }, [vertices, indices])

  return (
    <mesh
      ref={meshRef}
      geometry={geometry}
    >
      <meshStandardMaterial
        color={color}
        metalness={0.3}
        roughness={0.6}
        side={THREE.DoubleSide}
      />
    </mesh>
  )
}

function WingViewerScene({ meshData, quality }) {
  const lodLevel = quality || 'medium'
  const mesh = meshData?.mesh?.[lodLevel]

  if (!mesh || !mesh.vertices || mesh.vertices.length === 0) {
    return null
  }

  return (
    <>
      <ambientLight intensity={0.5} />
      <directionalLight position={[10, 10, 5]} intensity={1} />
      <directionalLight position={[-10, 5, -5]} intensity={0.3} />
      <WingMesh vertices={mesh.vertices} indices={mesh.indices} />
    </>
  )
}

export function WingViewer({ config, meshData, quality, loading }) {
  return (
    <div style={{
      flex: 1,
      position: 'relative',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)'
    }}>
      {loading && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          color: '#fff',
          fontSize: '18px',
          background: 'rgba(0,0,0,0.7)',
          padding: '10px 20px',
          borderRadius: '8px',
          zIndex: 10
        }}>
          Building geometry...
        </div>
      )}
      {!meshData && !loading && (
        <div style={{
          position: 'absolute',
          top: '50%',
          left: '50%',
          transform: 'translate(-50%, -50%)',
          color: '#aaa',
          fontSize: '16px',
          background: 'rgba(0,0,0,0.5)',
          padding: '10px 20px',
          borderRadius: '8px',
          zIndex: 10
        }}>
          No mesh data. Use the panel to generate a preview.
        </div>
      )}
      <Canvas
        camera={{ position: [0, 1500, 2000], fov: 45 }}
        style={{ width: '100%', height: '100%' }}
      >
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          minDistance={100}
          maxDistance={10000}
          target={[0, 0, 0]}
        />
        <WingViewerScene meshData={meshData} quality={quality} />
      </Canvas>
    </div>
  )
}

