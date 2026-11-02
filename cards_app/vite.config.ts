import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      // Everything is cached up front: the deck has to work on a bus with no signal.
      workbox: {
        globPatterns: ["**/*.{js,css,html,png,svg}"],
        maximumFileSizeToCacheInBytes: 4 * 1024 * 1024,
      },
      manifest: {
        name: "Chess cards",
        short_name: "Chess cards",
        description: "Cards from the mistakes in my own Lichess games",
        display: "standalone",
        background_color: "#f3f1ec",
        theme_color: "#f3f1ec",
        icons: [
          { src: "icon-192.png", sizes: "192x192", type: "image/png" },
          { src: "icon-512.png", sizes: "512x512", type: "image/png" },
        ],
      },
    }),
  ],
  server: { host: true },
  test: { include: ["src/**/*.test.ts"] },
});
