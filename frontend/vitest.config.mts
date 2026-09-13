import { fileURLToPath } from 'node:url';
import { defineConfig } from 'vitest/config';

export default defineConfig({
  resolve: {
    alias: { '@': fileURLToPath(new URL('.', import.meta.url)) },
  },
  test: {
    // Only `*.test.ts` under the app itself. Playwright owns `e2e/*.spec.ts`,
    // and vitest's default pattern would otherwise try to run those too.
    include: ['{app,components,lib}/**/*.test.{ts,tsx}'],
  },
});
