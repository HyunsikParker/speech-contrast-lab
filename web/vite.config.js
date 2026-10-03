import { defineConfig } from 'vite';
import { fileURLToPath } from 'node:url';

export default defineConfig({
  root: fileURLToPath(new URL('.', import.meta.url)),
  server: { host: '127.0.0.1', port: 5277, strictPort: true, proxy: { '/api': 'http://127.0.0.1:5276' } },
  build: { outDir: 'dist', emptyOutDir: true },
});
