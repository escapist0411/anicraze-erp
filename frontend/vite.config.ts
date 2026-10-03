import path from 'node:path';
import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig(({ command, mode }) => {
  if (command === 'build') {
    const url = loadEnv(mode, process.cwd(), 'VITE_').VITE_API_URL?.trim();
    let parsed: URL | undefined;
    try { parsed = url ? new URL(url) : undefined; } catch { parsed = undefined; }
    if (!parsed || parsed.protocol !== 'https:' || parsed.username || parsed.password || parsed.search || parsed.hash ||
        parsed.pathname.replace(/\/$/, '') !== '/api/v1' ||
        /^(?:localhost|127\.0\.0\.1|\[::1\])$/i.test(parsed.hostname)) {
      throw new Error('Production build requires VITE_API_URL set to the public HTTPS API base URL.');
    }
    // Vite embeds every VITE_* value, including an unused local fallback from
    // an ignored .env. Replace that public fallback for this build process.
    process.env.VITE_API_BASE_URL = url;
    process.env.VITE_APP_ENV = 'production';
  }
  return {
    plugins: [react(), tailwindcss()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
  };
});
