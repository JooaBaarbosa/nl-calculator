import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  build: {
    // A API Python serve esta pasta (ver mount_static em api.py).
    outDir: "../src/nl_calculator/static",
    emptyOutDir: true,
  },
  server: {
    proxy: { "/calculate": api, "/health": api },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.ts",
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/main.tsx", "src/**/*.test.*", "src/test-setup.ts"],
      thresholds: { lines: 90 },
    },
  },
});
