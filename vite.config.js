import { defineConfig } from "vite"
import path from "node:path"
import litestar from "litestar-vite-plugin"

const ASSET_URL = process.env.ASSET_URL || "/static/"
const VITE_PORT = process.env.VITE_PORT || "5173"
const VITE_HOST = process.env.VITE_HOST || "localhost"

export default defineConfig({
  base: ASSET_URL,
  clearScreen: false,
  publicDir: "public/",
  server: {
    host: "0.0.0.0",
    port: Number(VITE_PORT),
    cors: true,
    hmr: {
      host: VITE_HOST,
    },
  },
  plugins: [
    litestar({
      input: ["resources/main.js", "resources/main.css"],
      assetUrl: ASSET_URL,
      bundleDirectory: "src/app/domain/web/public",
      resourceDirectory: "resources",
      hotFile: "src/app/domain/web/public/hot",
    }),
  ],
  build: {
    cssCodeSplit: true,
    sourcemap: false,
    rollupOptions: {
      onwarn(warning, warn) {
        if (warning.code === "EVAL" && warning.id?.includes("htmx")) {
          return
        }
        warn(warning)
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(process.cwd(), "resources"),
    },
  },
})
