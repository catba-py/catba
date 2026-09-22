import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import { resolve } from "path"

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@catba/pages": resolve(__dirname, "app"),
    },
  },
  build: {
    emptyOutDir: true,
  },
})
