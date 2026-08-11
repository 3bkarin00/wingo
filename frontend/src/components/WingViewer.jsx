import React, { useRef, useState, useMemo, useCallback } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Grid, Environment, Html } from '@react-three/drei'
import * as THREE from 'three'

function WingMesh({ vertices, indices, color = '#4a9eff' }) {
  const meshRef = useRef()
  const [hovered, setHovered] = useState(false)

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
      onPointerOver={() => setHovered(true)}
      onPointerOut={() => setHovered(false)}
    >
      <meshStandardMaterial
        color={hovered ? '#6bb3ff' : color}
        metalness={0.3}
        roughness={0.6}
        side={THREE.DoubleSide}
        wireframe={false}
      />
    </mesh>
  )
}

function WingViewerScene({ meshData, quality, loading }) {
  const lodLevel = quality || 'medium'
  const mesh = meshData?.mesh?.[lodLevel]

  if (loading) {
    return (
      <>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <Html position={[0, 2, 0]}>
          <div style={{
            color: '#fff',
            fontSize: '18px',
            textAlign: 'center',
            background: 'rgba(0,0,0,0.7)',
            padding: '10px 20px',
            borderRadius: '8px'
          }}>
            Building geometry...
          </div>
        </Html>
      </>
    )
  }

  if (!mesh || !mesh.vertices || mesh.vertices.length === 0) {
    return (
      <>
        <ambientLight intensity={0.5} />
        <directionalLight position={[10, 10, 5]} intensity={1} />
        <Html position={[0, 2, 0]}>
          <div style={{
            color: '#aaa',
            fontSize: '16px',
            textAlign: 'center',
            background: 'rgba(0,0,0,0.5)',
            padding: '10px 20px',
            borderRadius: '8px'
          }}>
            No mesh data. Use the panel to generate a preview.
          </div>
        </Html>
      </>
    )
  }

  return (
    <>
      <ambientLight intensity={0.4} />
      <directionalLight position={[10, 10, 5]} intensity={0.8} />
      <directionalLight position={[-10, 5, -5]} intensity={0.3} />
      <WingMesh vertices={mesh.vertices} indices={mesh.indices} />
      <Grid
        position={[0, -2, 0]}
        args={[20, 20]}
        cellColor={'#444'}
        sectionColor={'#666'}
      />
    </>
  )
}

export function WingViewer({ config, meshData, quality, loading, panelVisible }) {
  return (
    <div style={{
      flex: 1,
      position: 'relative',
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 100%)'
    }}>
      <Canvas
        camera={{ position: [5, 3, 5], fov: 50 }}
        style={{ width: '100%', height: '100%' }}
      >
        <OrbitControls
          enablePan={true}
          enableZoom={true}
          enableRotate={true}
          minDistance={2}
          maxDistance={50}
        />
        <WingViewerScene meshData={meshData} quality={quality} loading={loading} />
        <Environment preset={'city'} />
      </Canvas>
    </div>
  )
}

