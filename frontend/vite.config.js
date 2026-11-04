import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  // El .env está en la raíz del monorepo. Vite solo expone al navegador las variables VITE_*.
  envDir: "..",
  server: {
    // En local, las peticiones a /api van a FastAPI (en Vercel lo resuelve vercel.json).
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
});
