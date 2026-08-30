import { defineConfig, devices } from '@playwright/test';

const PORT = 3100;

export default defineConfig({
  testDir: './e2e',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: 'list',
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: 'on-first-retry',
  },
  projects: [
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        launchOptions: {
          // The scene is the thing under test, so a runner without a GPU still
          // has to rasterise WebGL. Without these the page falls through to the
          // "cannot render" notice and the gate passes for the wrong reason.
          args: [
            '--use-gl=angle',
            '--use-angle=swiftshader',
            '--enable-unsafe-swiftshader',
          ],
        },
      },
    },
  ],
  webServer: {
    // A production build, not `next dev`: reactStrictMode double-mounts the R3F
    // canvas in development and the GL context is lost, so the scene never
    // renders there.
    command: `npm run build && npx next start -p ${PORT}`,
    port: PORT,
    // Never reuse: a server left running on this port from an earlier build
    // makes the gate pass or fail against code that is not the code under
    // test, which is worse than having no gate.
    reuseExistingServer: false,
    timeout: 300_000,
  },
});
