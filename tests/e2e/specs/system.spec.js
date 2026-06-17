import { test, expect } from '@playwright/test'
import { loginAs } from './_auth.js'
// 模块: 系统配置(admin) | 用户/Skill/派单/模块映射
test.describe('系统配置(admin)', () => {
  test.beforeEach(async ({ page }) => { await loginAs(page, { role: 'admin' }) })
  test('用户管理列表', async ({ page }) => { await page.goto('/fpy/#/system/users'); await expect(page.locator('.el-table')).toBeVisible() })
  test('Skill 管理(9个LLM SKILL)', async ({ page }) => {
    await page.goto('/fpy/#/system/skills')
    await expect(page.locator('.el-table__row').first()).toBeVisible({ timeout: 15000 })
  })
  test('派单配置', async ({ page }) => { await page.goto('/fpy/#/system/dispatch'); await expect(page.getByText(/配额|默认兜底/)).toBeVisible() })
  test('模块责任人映射', async ({ page }) => { await page.goto('/fpy/#/system/module-owners'); await expect(page.locator('.el-table')).toBeVisible() })
})
