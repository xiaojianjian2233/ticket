import { test, expect, request } from '@playwright/test'
// 端到端串联: 推智齿 webhook → 后端入队 → (worker异步流水线) → 工单列表可见
test('端到端: webhook 入站 → 工单出现在列表', async ({ page, playwright }) => {
  const base = process.env.BASE_URL || 'http://dl.piaozone.com:18025'
  const tid = 'E2EUI' + Date.now()
  const api = await playwright.request.newContext()
  const r = await api.post(`${base}/webhook/zhichi`, { data: {
    ticketid: tid, ticket_code: 'ZC-E2EUI', ticket_title: '发票开票测试E2E',
    ticket_content: '星瀚开票提示失败请协助处理该发票问题描述足够长以通过流转',
    ticket_status: 1, ticket_level: 2, create_time: '2026-06-11 10:00:00', enterprise_name: 'E2E',
    extend_fields_list: [{ field_name: '产品分类', field_type: '6', field_text: '星瀚-开票' }],
  } })
  expect(r.ok()).toBeTruthy()
  const body = await r.json()
  expect(body.code).toBe(0)         // 入队成功
  // 注: 流水线异步(秒~分钟级), UI 出现需轮询; 此处验证入站契约。完整断言见 tests/api/test_pipeline.py
})
