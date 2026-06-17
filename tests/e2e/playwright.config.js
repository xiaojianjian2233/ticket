// Playwright 浏览器自动化配置。运行：cd tests/e2e && npm i && npx playwright install chromium && BASE_URL=http://dl.piaozone.com:18025 TOKEN=<JWT> npx playwright test
import { defineConfig, devices } from '@playwright/test'
export default defineConfig({
  testDir: './specs',
  timeout: 60000,
  retries: 1,                       // 稳定性：失败重试1次
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.BASE_URL || 'http://dl.piaozone.com:18025',
    actionTimeout: 15000,
    navigationTimeout: 30000,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    storageState: process.env.STORAGE_STATE || undefined,
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
