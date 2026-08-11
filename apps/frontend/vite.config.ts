import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    proxy: {
      "/api": process.env.API_PROXY_TARGET ?? "http://localhost:3001",
      "/graphql": process.env.API_PROXY_TARGET ?? "http://localhost:3001"
    }
  },
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.ts"]
  }
});
