import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vitest/config'

// Strefa urządzenia nie może wpływać na wyniki: testy działają w strefie USA.
process.env.TZ = 'America/New_York'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icons/apple-touch-icon.png'],
      manifest: {
        name: 'F1 Prediction App',
        short_name: 'F1 Predict',
        description: 'Kalendarz, pogoda i predykcje weekendów Formuły 1',
        lang: 'pl',
        start_url: '/',
        display: 'standalone',
        background_color: '#0f1115',
        theme_color: '#e10600',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
          { src: 'icons/icon-512-maskable.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Dane zawsze najpierw z sieci (świeże), a bez internetu ostatnia pobrana wersja.
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/data/') && url.pathname.endsWith('.json'),
            handler: 'NetworkFirst',
            options: { cacheName: 'f1-data', networkTimeoutSeconds: 5 },
          },
        ],
      },
    }),
  ],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
  },
})
