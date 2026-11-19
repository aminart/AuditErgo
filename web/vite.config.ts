/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// En développement (npm run dev), l'API Python tourne à part : python -m serveur --sans-navigateur
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": "http://127.0.0.1:8501" } },
  build: { outDir: "dist", emptyOutDir: true, chunkSizeWarningLimit: 800 },
  // Tests d'interface (npm test) : navigateur simulé, requêtes au serveur remplacées dans chaque test
  test: { environment: "jsdom", setupFiles: ["src/test/setup.ts"], include: ["src/**/*.test.{ts,tsx}"] },
});
