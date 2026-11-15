import { fileURLToPath } from 'node:url'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  build: {
    rolldownOptions: {
      input: {
        onboard: fileURLToPath(new URL('./index.html', import.meta.url)),
        ground: fileURLToPath(new URL('./ground.html', import.meta.url)),
      },
    },
  },
})
