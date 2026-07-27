import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { artifactUrl, type ArtifactManifest } from "./api";

interface Props {
  jobId: string;
  manifest: ArtifactManifest;
}

// Playwright-facing debug hook (plan.md §9 P10: "deflection slider animates
// about correct axis (compare a tracked vertex against server-computed
// position)") — the gate drives this directly rather than simulating
// mouse drags on the slider, since the numeric check needs an exact,
// repeatable vertex index/angle, not a rendered pixel position.
interface E2EHook {
  jobId: string;
  getBodyNames: () => string[];
  getCsBodyNames: () => string[];
  setDeflection: (deg: number) => void;
  setBodyVisible: (bodyName: string, visible: boolean) => void;
  isBodyVisible: (bodyName: string) => boolean | null;
  getVertexWorldPosition: (bodyName: string, vertexIndex: number) => [number, number, number] | null;
}

declare global {
  interface Window {
    __wingE2E?: E2EHook;
  }
}

// three.js's GLTFLoader internally sanitizes every loaded object's `.name`
// via its own PropertyBinding.sanitizeNodeName — it uses "/" as an
// animation-track path separator internally, so any "/" in a glTF node's
// declared name is stripped before the Object3D is created. Found
// empirically (P10 gate development): the exported glTF JSON correctly
// has our full naming-contract string (SEG-C/BODY-x/ROLE-y, verified by
// inspecting the raw file), but the LOADED three.js object ends up named
// "SEG-CBODY-xROLE-y" — an exact getObjectByName(contractName) lookup can
// therefore never match anything. This is a pure client-side lookup
// mismatch, not a naming-contract or exporter problem (STEP/DXF/report
// all still use the real "/"-bearing contract name) — normalize both
// sides of the comparison the same way instead of changing the contract.
function stripSlashes(name: string): string {
  return name.replace(/\//g, "");
}

function findFirstMesh(root: THREE.Object3D): THREE.Mesh | null {
  if ((root as THREE.Mesh).isMesh) return root as THREE.Mesh;
  let found: THREE.Mesh | null = null;
  root.traverse((child) => {
    if (!found && (child as THREE.Mesh).isMesh) found = child as THREE.Mesh;
  });
  return found;
}

export default function Viewer({ jobId, manifest }: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<THREE.Scene | null>(null);
  const nodesRef = useRef<Map<string, THREE.Object3D>>(new Map());
  const [loaded, setLoaded] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [visibility, setVisibility] = useState<Record<string, boolean>>({});
  const [deflectionDeg, setDeflectionDeg] = useState(0);

  const kin = manifest.kinematics;

  // Scene setup + glTF load — once per job/manifest.
  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x1b1d22);
    sceneRef.current = scene;

    const camera = new THREE.PerspectiveCamera(45, mount.clientWidth / mount.clientHeight, 1, 100000);
    camera.up.set(0, 0, 1); // Z-up (docs/conventions.md's frame: X aft, Y starboard, Z up)
    camera.position.set(1500, -2000, 1200);

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.target.set(0, 0, 0);

    scene.add(new THREE.AmbientLight(0xffffff, 0.6));
    const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
    dirLight.position.set(1000, -1000, 2000);
    scene.add(dirLight);
    scene.add(new THREE.AxesHelper(300));

    // React.StrictMode (main.tsx) double-invokes this effect in dev mode
    // (mount -> cleanup -> mount again) specifically to catch missing-
    // cleanup bugs in exactly this shape of code — an async operation
    // (loader.load) with no cancellation guard. Found empirically (P10
    // gate's deflection test): without `cancelled`, BOTH the first
    // (orphaned) and second (live) mounts' async glTF-load callbacks
    // eventually fire and overwrite the SAME shared nodesRef/sceneRef,
    // non-deterministically leaving nodesRef pointing at objects in a
    // DETACHED scene graph that the deflection effect's
    // `sceneRef.current.updateMatrixWorld(true)` call never reaches (it
    // walks the CURRENT/live scene, not the orphaned one) — the rotated
    // node's OWN matrix was set correctly, but its matrixWorld was never
    // recomputed, so read-back vertex positions reflected a stale
    // parent transform instead of the new rotation (a small, nonzero,
    // WRONG displacement — not simply "no rotation applied", which is
    // what made this confusing to diagnose from the symptom alone).
    let cancelled = false;
    const loader = new GLTFLoader();
    loader.load(
      artifactUrl(jobId, manifest.artifacts.gltf),
      (gltf) => {
        if (cancelled) return;
        scene.add(gltf.scene);
        const bySanitizedName = new Map<string, THREE.Object3D>();
        gltf.scene.traverse((o) => {
          // First object seen for a given sanitized name wins — the
          // wrapping node/first primitive, whichever three.js assigned
          // the UN-suffixed name to (a body whose tessellation produced
          // multiple glTF primitives gets "_1", "_2", ... siblings from
          // three.js's own de-duplication, which we deliberately don't
          // index here: toggling/rotating the first-matched object is
          // what the naming contract's per-BODY granularity means).
          if (o.name && !bySanitizedName.has(o.name)) bySanitizedName.set(o.name, o);
        });
        const nodes = new Map<string, THREE.Object3D>();
        for (const b of manifest.bodies) {
          const obj = bySanitizedName.get(stripSlashes(b.contract_name));
          if (obj) nodes.set(b.contract_name, obj);
        }
        nodesRef.current = nodes;
        setVisibility(Object.fromEntries(manifest.bodies.map((b) => [b.contract_name, true])));
        scene.updateMatrixWorld(true);
        setLoaded(true);
      },
      undefined,
      (err) => {
        if (!cancelled) setLoadError(String(err));
      },
    );

    let raf = 0;
    const animate = () => {
      controls.update();
      renderer.render(scene, camera);
      raf = requestAnimationFrame(animate);
    };
    animate();

    const onResize = () => {
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    window.addEventListener("resize", onResize);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", onResize);
      controls.dispose();
      renderer.dispose();
      if (renderer.domElement.parentNode === mount) mount.removeChild(renderer.domElement);
    };
  }, [jobId, manifest]);

  // Body visibility toggles.
  useEffect(() => {
    for (const [name, obj] of nodesRef.current) {
      obj.visible = visibility[name] ?? true;
    }
  }, [visibility]);

  // Deflection slider -> rigid rotation of every CS-side node about the
  // true hinge axis: M = T(p0) . R(axis, angle) . T(-p0) in WORLD space,
  // then converted into each node's PARENT-LOCAL frame before being
  // assigned as its local `.matrix` (Object3D.matrix is always relative
  // to its own parent, not world space). Found empirically (P10 gate's
  // deflection test): cq.Assembly's glTF export applies an implicit
  // root-level Z-up -> Y-up coordinate conversion (glTF's own spec-
  // mandated convention, confirmed by dumping a CS body's matrixWorld at
  // rest — a 90 deg rotation, not identity) as an ANCESTOR transform —
  // `axis_p0`/`axis_dir` come from the server in our NATIVE Z-up frame
  // (docs/conventions.md), so building the rotation matrix directly in
  // that frame and assigning it as a node's LOCAL matrix silently
  // interpreted it in the node's (Y-up-converted) PARENT frame instead,
  // producing a real but WRONG rotation (small, nonzero, not the
  // intended transform — not simply "no rotation applied", which is what
  // made this one hard to spot from the symptom alone: two independent
  // real-run diagnostics, both showing a small-but-wrong displacement,
  // before dumping the raw matrixWorld data made the mismatch visible).
  // Transforming axis_p0/axis_dir into the node's OWN parent frame first
  // (inverse of the parent's matrixWorld — a point needs the full
  // inverse; a direction only needs the rotation part, hence
  // transformDirection) is correct regardless of what that ancestor
  // transform actually is, without needing to know or reverse-engineer
  // it explicitly.
  useEffect(() => {
    if (!kin) return;
    const p0World = new THREE.Vector3(...kin.axis_p0);
    const dirWorld = new THREE.Vector3(...kin.axis_dir).normalize();
    const rad = THREE.MathUtils.degToRad(deflectionDeg);
    for (const name of kin.cs_body_names) {
      const obj = nodesRef.current.get(name);
      if (!obj || !obj.parent) continue;
      const parentInverse = new THREE.Matrix4().copy(obj.parent.matrixWorld).invert();
      const p0 = p0World.clone().applyMatrix4(parentInverse);
      const dir = dirWorld.clone().transformDirection(parentInverse);
      const rot = new THREE.Matrix4().makeRotationAxis(dir, rad);
      const toOrigin = new THREE.Matrix4().makeTranslation(-p0.x, -p0.y, -p0.z);
      const fromOrigin = new THREE.Matrix4().makeTranslation(p0.x, p0.y, p0.z);
      const m = fromOrigin.multiply(rot).multiply(toOrigin);
      obj.matrixAutoUpdate = false;
      obj.matrix.copy(m);
    }
    sceneRef.current?.updateMatrixWorld(true);
  }, [kin, deflectionDeg, loaded]);

  useEffect(() => {
    window.__wingE2E = {
      jobId,
      getBodyNames: () => Array.from(nodesRef.current.keys()),
      getCsBodyNames: () => kin?.cs_body_names ?? [],
      setDeflection: (deg: number) => setDeflectionDeg(deg),
      setBodyVisible: (bodyName: string, visible: boolean) =>
        setVisibility((v) => ({ ...v, [bodyName]: visible })),
      isBodyVisible: (bodyName: string) => nodesRef.current.get(bodyName)?.visible ?? null,
      getVertexWorldPosition: (bodyName: string, vertexIndex: number) => {
        const obj = nodesRef.current.get(bodyName);
        if (!obj) return null;
        const mesh = findFirstMesh(obj);
        const posAttr = mesh?.geometry?.attributes?.position;
        if (!mesh || !posAttr || vertexIndex >= posAttr.count) return null;
        const v = new THREE.Vector3().fromBufferAttribute(posAttr, vertexIndex);
        mesh.updateMatrixWorld(true);
        v.applyMatrix4(mesh.matrixWorld);
        return [v.x, v.y, v.z] as [number, number, number];
      },
    };
    return () => {
      delete window.__wingE2E;
    };
  }, [jobId]);

  return (
    <div className="viewer">
      <div ref={mountRef} className="viewer-canvas" data-testid="viewer-canvas" />
      <div className="viewer-panel">
        <h3>Bodies ({manifest.bodies.length})</h3>
        <div className="body-list">
          {manifest.bodies.map((b) => (
            <label key={b.contract_name} title={b.contract_name}>
              <input
                type="checkbox"
                checked={visibility[b.contract_name] ?? true}
                onChange={(e) =>
                  setVisibility((v) => ({ ...v, [b.contract_name]: e.target.checked }))
                }
              />
              {b.body_name} <span className="role">({b.role})</span>
            </label>
          ))}
        </div>
        {kin && (
          <div className="deflection">
            <h3>Deflection</h3>
            <input
              type="range"
              min={-kin.max_deflection_deg}
              max={kin.max_deflection_deg}
              step={0.1}
              value={deflectionDeg}
              data-testid="deflection-slider"
              onChange={(e) => setDeflectionDeg(parseFloat(e.target.value))}
            />
            <span>{deflectionDeg.toFixed(1)}&deg;</span>
          </div>
        )}
        {!loaded && !loadError && <p>Loading model&hellip;</p>}
        {loadError && <p className="error">{loadError}</p>}
      </div>
    </div>
  );
}
