import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// /api proxies to the FastAPI dev server (backend/api/main.py, run via
// `uvicorn backend.api.main:app --port 8000`) — including WebSocket
// upgrades (`ws: true`) for the job progress stream.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        ws: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
