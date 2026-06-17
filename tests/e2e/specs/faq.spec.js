import { test, expect } from '@playwright/test'
import { loginAs } from './_auth.js'
// 模块: 知识库 | 正常(列表/查阅搜索) 边界(空) 分支(审核列表)
test.describe('知识库', () => {
  test.beforeEach(async ({ page }) => { await loginAs(page) })
  test('FAQ 管理列表', async ({ page }) => { await page.goto('/fpy/#/faq'); await expect(page.locator('.el-table')).toBeVisible() })
  test('知识库语义搜索(分支)', async ({ page }) => {
    await page.goto('/fpy/#/faq/browse')
    await page.locator('input').first().fill('开票失败')
    await page.getByRole('button', { name: '搜索' }).click()
    await expect(page.locator('.el-card')).toBeVisible()
  })
  test('FAQ 审核列表', async ({ page }) => { await page.goto('/fpy/#/faq/review'); await expect(page.getByText(/审核/)).toBeVisible() })
})
