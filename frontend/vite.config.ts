import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, '.', '');
  const target = env.API_PROXY_TARGET || 'http://127.0.0.1:8000';
  return {
    plugins: [react()],
    server: {
      host: '0.0.0.0', port: 5173, strictPort: true,
      proxy: Object.fromEntries(['/api', '/healthz', '/readyz'].map(path => [path, { target, changeOrigin: true }])),
    },
    test: { environment: 'jsdom', setupFiles: './src/test-setup.ts', restoreMocks: true },
  };
});
