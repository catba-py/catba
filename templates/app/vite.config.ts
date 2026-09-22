import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import { resolve } from "path"
import { fileURLToPath } from "url"
import { dirname } from "path"

const __dirname = dirname(fileURLToPath(import.meta.url))

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@catba/pages": resolve(__dirname, "app"),
    },
  },
  build: {
    emptyOutDir: true,
    rollupOptions: {
      input: resolve(__dirname, ".catba/generated/client-entry.js"),
    },
  },
})
