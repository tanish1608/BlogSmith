import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server proxies API calls to the FastAPI backend on :8000.
// Production build is emitted to dist/ and served by FastAPI.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/account": "http://localhost:8000",
      "/sites": "http://localhost:8000",
      "/tools": "http://localhost:8000",
      "/health": "http://localhost:8000",
    },
  },
  build: { outDir: "dist" },
});
