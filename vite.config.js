import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Strefa urządzenia nie może wpływać na wyniki: testy działają w strefie USA.
process.env.TZ = 'America/New_York'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
  },
})
