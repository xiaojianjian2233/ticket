import { test, expect } from '@playwright/test'
// 模块: 登录 | 用例: 正常渲染 / 飞书按钮 / 未登录守卫
test.describe('登录', () => {
  test('登录页正常渲染 + 飞书登录按钮', async ({ page }) => {
    await page.goto('/fpy/#/login')
    await expect(page.getByText('ticket-hub')).toBeVisible()
    await expect(page.getByRole('button', { name: /飞书登录/ })).toBeVisible()  // 元素定位+断言
  })
  test('未登录访问工单页 → 重定向登录(路由守卫)', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto('/fpy/#/tickets')
    await expect(page).toHaveURL(/#\/login/)   // 断言: 守卫跳转
  })
})
