import { test, expect } from '@playwright/test'
import { loginAs } from './_auth.js'
// 模块: SLA监控 | 正常(列表/概览) 分支(tab切换)
test.describe('SLA监控', () => {
  test.beforeEach(async ({ page }) => { await loginAs(page) })
  test('SLA 监控页 + 概览卡片', async ({ page }) => {
    await page.goto('/fpy/#/sla')
    await expect(page.getByText(/超时累计/)).toBeVisible()
    await expect(page.locator('.el-tabs')).toBeVisible()
  })
})
