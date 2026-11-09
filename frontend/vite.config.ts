import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // Shares the repository's .env. Vite only exposes variables that start with VITE_.
  envDir: "..",
  server: {
    port: 5173,
    // The backend only allows this origin, so a different port would fail with CORS errors.
    strictPort: true,
  },
  build: {
    // MapLibre alone is about 1 MB. It already loads as its own chunk, after the page paints.
    chunkSizeWarningLimit: 1100,
  },
  test: {
    environment: "node",
    include: ["src/**/*.test.ts"],
  },
});
