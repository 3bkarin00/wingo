import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api proxies to the FastAPI dev server (backend/api/main.py) --
// including WebSocket upgrades (`ws: true`) for the job progress stream.
// Target is env-configurable (VITE_PROXY_TARGET), not hardcoded to the
// `make run-api` default port -- found empirically (P10 E2E gate's first
// real run): the gate deliberately runs the API on a non-default port
// (8731) to avoid colliding with a human's own `make run-api` session,
// and a hardcoded proxy target here made every /api/* fetch silently
// fail against the wrong port (empty config dropdown, no visible crash --
// see backend/api's own CORS-is-wide-open posture, this is the same
// "local dev tool" trust boundary).
const proxyTarget = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: proxyTarget,
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
