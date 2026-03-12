import path from 'path';
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  server: {
    port: 5173,
    host: '0.0.0.0',
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/auth': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, '.'),
    },
  },
  build: {
    // @mdxeditor/editor is ~656KB monolithic (lazy-loaded, settings page only).
    // Remaining app code is well-split across 7 vendor chunks.
    chunkSizeWarningLimit: 700,
    rollupOptions: {
      output: {
        manualChunks: {
          'pdf-viewer': ['react-pdf', 'pdfjs-dist'],
          'markdown-editor': ['@mdxeditor/editor'],
          'recharts-vendor': ['recharts'],
          'animations': ['framer-motion'],
          'router-icons': ['react-router-dom', 'lucide-react'],
          'markdown-render': ['react-markdown', 'remark-gfm'],
        },
      },
    },
  },
});
