// 注入 JWT 到 localStorage 模拟已登录(避免飞书OAuth交互)。TOKEN/ROLE 经环境变量传入。
export async function loginAs(page, { token = process.env.TOKEN, role = process.env.ROLE || 'admin', name = 'e2e' } = {}) {
  await page.goto('/fpy/')
  await page.evaluate(([t, u]) => {
    localStorage.setItem('token', t)
    localStorage.setItem('user', JSON.stringify(u))
  }, [token, { id: 1, name, role, feishuUid: 'e2e' }])
}
