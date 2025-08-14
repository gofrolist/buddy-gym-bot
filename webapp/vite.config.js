import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Build the webapp to be served from /webapp/
export default defineConfig({
  base: '/webapp/',
  plugins: [react()],
  build: {
    outDir: 'dist',
  }
})
