import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        // Keep the chart library out of the main bundle.
        manualChunks: { charts: ["recharts"] },
      },
    },
  },
  server: {
    host: "127.0.0.1",
    port: 3011,
    strictPort: true,
    proxy: { "/api/quality": "http://127.0.0.1:8767" },
  },
});
