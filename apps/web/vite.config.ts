import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const base = env.VITE_BASE_PATH || (mode === "gh-pages" ? "./" : "/");
  return {
    base,
    plugins: [react(), tailwindcss()],
  };
});
