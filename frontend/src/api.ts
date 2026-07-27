// Thin fetch wrappers over backend/api's routes (backend/api/routes/
// configs.py, jobs.py) — every shape here mirrors backend/api/schemas.py
// field-for-field; if the two drift, this file is the one that's wrong.

export interface SampleConfigInfo {
  name: string;
  source: string;
}

export interface BodyManifestEntry {
  contract_name: string;
  body_name: string;
  role: string;
  segment: string;
  has_sub_faces: boolean;
}

export interface KinematicsManifest {
  axis_p0: [number, number, number];
  axis_dir: [number, number, number];
  max_deflection_deg: number;
  wing_body_names: string[];
  cs_body_names: string[];
}

export interface ArtifactManifest {
  job_id: string;
  bodies: BodyManifestEntry[];
  kinematics: KinematicsManifest | null;
  warnings: string[];
  timings_s: Record<string, unknown>;
  artifacts: { gltf: string; step?: string; stl?: Record<string, string> };
}

export type JobStatus = "pending" | "running" | "done" | "failed";

export interface JobResponse {
  id: string;
  status: JobStatus;
  checkpoint: { stage: string } | null;
  artifact_manifest: ArtifactManifest | null;
}

export interface ProgressPayload {
  status: JobStatus;
  checkpoint: { stage: string } | null;
}

const API_BASE = "/api";

async function asJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return (await res.json()) as T;
}

export function listSampleConfigs(): Promise<SampleConfigInfo[]> {
  return fetch(`${API_BASE}/configs/samples`).then((r) => asJson(r));
}

export function getSampleConfig(name: string): Promise<Record<string, unknown>> {
  return fetch(`${API_BASE}/configs/samples/${encodeURIComponent(name)}`).then((r) => asJson(r));
}

export function createJob(config: Record<string, unknown>): Promise<JobResponse> {
  return fetch(`${API_BASE}/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ config }),
  }).then((r) => asJson(r));
}

export function getJob(jobId: string): Promise<JobResponse> {
  return fetch(`${API_BASE}/jobs/${jobId}`).then((r) => asJson(r));
}

export function artifactUrl(jobId: string, filename: string): string {
  return `${API_BASE}/jobs/${jobId}/artifacts/${filename}`;
}

export function sampleKinematics(
  jobId: string,
  bodyName: string,
  pointLocal: [number, number, number],
  angleDeg: number,
): Promise<{ point_world: [number, number, number]; moved: boolean }> {
  return fetch(`${API_BASE}/jobs/${jobId}/kinematics/sample`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ body_name: bodyName, point_local: pointLocal, angle_deg: angleDeg }),
  }).then((r) => asJson(r));
}

export function openProgressSocket(
  jobId: string,
  onMessage: (payload: ProgressPayload) => void,
): WebSocket {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${window.location.host}${API_BASE}/jobs/${jobId}/ws`);
  ws.onmessage = (evt) => onMessage(JSON.parse(evt.data) as ProgressPayload);
  return ws;
}
