import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  base: "/",
  server: {
    // Allows the server to be accessible outside the container
    host: true, 
    // This solves the "Blocked request" error for AWS/EC2 hostnames
    allowedHosts: true, 
    hmr: {
	clientPort: 80
    },
  },
  test: {
    globals: true,
    environment: "jsdom",
    setupFiles: "./src/test/setupTests.js",
    css: true,
  },
});
