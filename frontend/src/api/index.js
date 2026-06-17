// 业务 API 封装（对应后端 41 路由）
import req from './request'

export const authApi = {
  loginUrl: () => req.get('/auth/feishu/login'),
  callback: (code) => req.get('/auth/feishu/callback', { params: { code } }),
  me: () => req.get('/auth/me'),
}
export const userApi = {
  list: (params) => req.get('/users', { params }),
  update: (id, data) => req.put(`/users/${id}`, data),
}
export const ticketApi = {
  list: (params) => req.get('/tickets', { params }),
  unhandled: (params) => req.get('/tickets/unhandled', { params }),
  detail: (id) => req.get(`/tickets/${id}`),
  handle: (id, data) => req.post(`/tickets/${id}/handle`, data),
  close: (id, data) => req.post(`/tickets/${id}/close`, data),
  batchClose: (ids) => req.post('/tickets/batch-close', { ids }),
  rejudge: (id) => req.post(`/tickets/${id}/rejudge`),
  takeover: (id) => req.post(`/tickets/${id}/takeover`),
  requeue: (id, data) => req.post(`/tickets/${id}/requeue`, data),
  tag: (id, data) => req.put(`/tickets/${id}/tag`, data),
  overview: (params) => req.get('/overview/stats', { params }),
  serviceLevels: () => req.get('/service-levels'),
  myTickets: (params) => req.get('/workbench/my-tickets', { params }),
  myPending: (params) => req.get('/workbench/my-pending', { params }),
}
export const hubApi = {
  list: (params) => req.get('/hubs', { params }),
  detail: (id) => req.get(`/hubs/${id}`),
  resyncLinear: (id) => req.post(`/hubs/${id}/resync-linear`),
  syncStatus: (id) => req.post(`/hubs/${id}/sync-status`),
}
export const faqApi = {
  list: (params) => req.get('/faq', { params }),
  browse: (params) => req.get('/faq/browse', { params }),
  search: (data) => req.post('/faq/search', data),
  reviewList: (params) => req.get('/faq/review-list', { params }),
  detail: (id) => req.get(`/faq/${id}`),
  review: (id, data) => req.post(`/faq/${id}/review`, data),
  edit: (id, data) => req.put(`/faq/${id}`, data),
  remove: (id) => req.delete(`/faq/${id}`),
}
export const slaApi = {
  list: (params) => req.get('/sla', { params }),
  overview: () => req.get('/sla/overview'),
  notifyLog: (params) => req.get('/sla/notify-log', { params }),
  systemAlerts: () => req.get('/sla/system-alerts'),
  requeue: (taskId) => req.post(`/sla/requeue-abandoned/${taskId}`),
}
export const assistantApi = {
  chat: (data) => req.post('/assistant/chat', data),
  submit: (data) => req.post('/assistant/submit', data),
}
export const skillApi = {
  list: () => req.get('/skills'),
  get: (name) => req.get(`/skills/${name}`),
  edit: (name, data) => req.put(`/skills/${name}`, data),
  rollback: (name, data) => req.post(`/skills/${name}/rollback`, data),
  preview: (name, data) => req.post(`/skills/${name}/preview`, data),
}
export const dispatchApi = {
  assignees: () => req.get('/dispatch/assignees'),
  createAssignee: (data) => req.post('/dispatch/assignees', data),
  updateAssignee: (id, data) => req.put(`/dispatch/assignees/${id}`, data),
  deleteAssignee: (id) => req.delete(`/dispatch/assignees/${id}`),
  setConfig: (data) => req.put('/dispatch/config', data),
  rules: () => req.get('/dispatch/rules'),
  rulesTaken: (params) => req.get('/dispatch/rules/taken', { params }),
  createRule: (data) => req.post('/dispatch/rules', data),
  updateRule: (id, data) => req.put(`/dispatch/rules/${id}`, data),
  deleteRule: (id) => req.delete(`/dispatch/rules/${id}`),
}
export const moduleOwnerApi = {
  list: (params) => req.get('/module-owners', { params }),
  options: () => req.get('/module-owners/options'),
  create: (data) => req.post('/module-owners', data),
  update: (id, data) => req.put(`/module-owners/${id}`, data),
  toggle: (id) => req.post(`/module-owners/${id}/toggle`),
  remove: (id) => req.delete(`/module-owners/${id}`),
}
