import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Let the official React plugin handle JSX transformation.
// Custom esbuild loader/include settings can prevent JSX from being transformed.
export default defineConfig({
  plugins: [react()],
  server: {
    host: 'localhost',
    port: 5173,
    strictPort: true,
    proxy: { '/api': 'http://localhost:4000' },
  },
});
