import { defineConfig } from "vite";
export default defineConfig({
  base: "./",
  server: {
    host: "127.0.0.1",
    port: 5178,
    strictPort: true,
    proxy: { "/api": "http://127.0.0.1:8770" },
  },
  build: { target: "es2022" },
});
