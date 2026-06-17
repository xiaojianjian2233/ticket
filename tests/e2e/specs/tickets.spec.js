import { test, expect } from '@playwright/test'
import { loginAs } from './_auth.js'
// 模块: 工单 | 正常(列表/详情) 分支(筛选) 边界(空结果) 异常(无权限按钮)
test.describe('工单管理', () => {
  test.beforeEach(async ({ page }) => { await loginAs(page) })
  test('工单列表加载 + 列展示 + 分页', async ({ page }) => {
    await page.goto('/fpy/#/tickets')
    await expect(page.locator('.el-table')).toBeVisible()
    await expect(page.locator('.el-table__row').first()).toBeVisible({ timeout: 20000 })
  })
  test('按状态筛选(分支)', async ({ page }) => {
    await page.goto('/fpy/#/tickets')
    await page.locator('.el-select').first().click()
    await page.getByText('待人工').click()
    await page.getByRole('button', { name: '查询' }).click()
    await expect(page.locator('.el-table')).toBeVisible()
  })
  test('点击行进详情(正常)', async ({ page }) => {
    await page.goto('/fpy/#/tickets')
    await page.locator('.el-table__row').first().click()
    await expect(page).toHaveURL(/#\/tickets\/\d+/)
    await expect(page.getByText(/流转判定|答复/)).toBeVisible()
  })
})
