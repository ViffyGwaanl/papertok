import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { VitePWA } from "vite-plugin-pwa";

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // Capacitor/WebView builds should avoid Service Worker caching surprises.
  // Keep PWA enabled for web builds.
  const enablePwa = mode !== "capacitor";

  return {
    plugins: [
      react(),
      tailwindcss(),
      ...(enablePwa
        ? [
            VitePWA({
              registerType: "autoUpdate",
              // IMPORTANT: avoid serving SPA index.html for static/PDF/image navigations.
              // Otherwise opening /static/* in a new tab may show the PaperTok homepage.
              workbox: {
                navigateFallbackDenylist: [/^\/static\//, /^\/api\//],
              },
              manifest: {
                name: "PaperTok",
                short_name: "PaperTok",
                icons: [
                  {
                    src: "/wiki-logo.svg",
                    sizes: "any",
                    type: "image/svg+xml",
                  },
                ],
                start_url: "/",
                display: "standalone",
                background_color: "#ffffff",
                theme_color: "#000000",
              },
            }),
          ]
        : []),
    ],
  };
});
