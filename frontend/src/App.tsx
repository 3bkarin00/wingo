import { useEffect, useState } from "react";
import {
  createJob,
  getJob,
  getSampleConfig,
  listSampleConfigs,
  openProgressSocket,
  type JobResponse,
  type ProgressPayload,
  type SampleConfigInfo,
} from "./api";
import Viewer from "./Viewer";

export default function App() {
  const [samples, setSamples] = useState<SampleConfigInfo[]>([]);
  const [selected, setSelected] = useState<string>("");
  const [job, setJob] = useState<JobResponse | null>(null);
  const [progress, setProgress] = useState<ProgressPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    listSampleConfigs()
      .then((s) => {
        setSamples(s);
        // te_half is the only sample with a device window + hinges — pick
        // it by default so the deflection slider has something to show.
        const preferred = s.find((x) => x.name === "te_half") ?? s[0];
        if (preferred) setSelected(preferred.name);
      })
      .catch((e) => setError(String(e)));
  }, []);

  // ?job=<uuid> loads an already-built job directly (skips the build
  // flow) — a real, shareable-URL feature, and also what made isolating
  // a client-side glTF-loading bug tractable without re-paying a real
  // job's full build cost every time (P10 gate development).
  useEffect(() => {
    const existingId = new URLSearchParams(window.location.search).get("job");
    if (!existingId) return;
    getJob(existingId).then(setJob).catch((e) => setError(String(e)));
  }, []);

  const submit = async () => {
    setError(null);
    setJob(null);
    setProgress(null);
    setSubmitting(true);
    try {
      const config = await getSampleConfig(selected);
      const created = await createJob(config);
      setJob(created);
      const ws = openProgressSocket(created.id, (payload) => {
        setProgress(payload);
        if (payload.status === "done" || payload.status === "failed") {
          getJob(created.id).then(setJob).catch((e) => setError(String(e)));
          ws.close();
        }
      });
    } catch (e) {
      setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="app">
      <header>
        <h1>WingStructGen — Web Viewer</h1>
        <div className="controls">
          <select value={selected} onChange={(e) => setSelected(e.target.value)} data-testid="config-select">
            {samples.map((s) => (
              <option key={s.name} value={s.name}>
                {s.name}
              </option>
            ))}
          </select>
          <button onClick={submit} disabled={!selected || submitting} data-testid="build-button">
            Build
          </button>
          {progress && (
            <span className="status" data-testid="job-status">
              {progress.status}
              {progress.checkpoint ? ` — ${progress.checkpoint.stage}` : ""}
            </span>
          )}
        </div>
        {error && <p className="error">{error}</p>}
      </header>
      <main>
        {job?.status === "done" && job.artifact_manifest ? (
          <Viewer jobId={job.id} manifest={job.artifact_manifest} />
        ) : (
          <p className="hint">Pick a config and click Build to submit a job.</p>
        )}
      </main>
    </div>
  );
}
