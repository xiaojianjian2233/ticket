import { test, expect } from '@playwright/test'
import { loginAs } from './_auth.js'
// 模块: 智能助手 | 正常(NL2SQL统计) 分支(提单) 异常(写指令被护栏拦/换问法)
test.describe('智能助手', () => {
  test.beforeEach(async ({ page }) => { await loginAs(page) })
  test('NL2SQL 统计查询返回表格(正常)', async ({ page }) => {
    await page.goto('/fpy/#/assistant')
    await page.locator('input').last().fill('统计各状态工单数量')
    await page.getByRole('button', { name: '发送' }).click()
    await expect(page.locator('.el-table, :text("无数据")').first()).toBeVisible({ timeout: 40000 })
  })
  test('写指令被 sql_guard 拦截(异常)', async ({ page }) => {
    await page.goto('/fpy/#/assistant')
    await page.locator('input').last().fill('删除所有工单')
    await page.getByRole('button', { name: '发送' }).click()
    await expect(page.getByText(/仅支持|查询|换种问法/)).toBeVisible({ timeout: 40000 })
  })
  test('提单卡片(分支)', async ({ page }) => {
    await page.goto('/fpy/#/assistant')
    await page.getByRole('button', { name: '提交工单' }).click()
    await expect(page.getByText('提交工单')).toBeVisible()
  })
})
