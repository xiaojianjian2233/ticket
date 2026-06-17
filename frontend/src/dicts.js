// 状态枚举 → 标签 + 色（全流程复用）+ 权限字典
export const STATUS = {
  pending: { label: '待处理', type: 'info' },
  returned: { label: '已退回(不接管)', type: 'danger' },
  pending_manual: { label: '待人工审核', type: 'warning' },
  supplement: { label: '补充资料', type: 'warning' },
  pending_rd: { label: '待研发确认', type: 'primary' },
  done: { label: '处理完成', type: 'success' },
  closed: { label: '已关闭', type: 'info' },
}
// 工单类型（A/B/C/D 派生 + 配置/运维待来源）
export const TICKET_TYPE = {
  bug类: { label: 'bug类', type: 'danger' },
  需求类: { label: '需求类', type: 'warning' },
  配置类: { label: '配置类', type: 'primary' },
  运维类: { label: '运维类', type: 'primary' },
  问题资料缺失: { label: '问题资料缺失', type: 'info' },
  其它: { label: '其它', type: 'info' },
}
export const SOURCE = {
  ksm: { label: 'KSM', type: 'primary' },
  zhichi: { label: '智齿', type: 'success' },
  assistant: { label: '内部提单', type: 'warning' },   // 发票云内部需求单
}
// 来源筛选选项（多选）：内部提单=assistant；外部提单=ksm+zhichi
export const SOURCE_FILTER = [
  { label: 'KSM', sources: ['ksm'] },
  { label: '智齿', sources: ['zhichi'] },
  { label: '内部提单', sources: ['assistant'] },
  { label: '外部提单', sources: ['ksm', 'zhichi'] },
]
// 服务等级（KSM）枚举，用于列展示与多选筛选
export const SERVICE_LEVEL = [
  '标准成功服务（2023版）',
  '高级成功服务（含定制开发维）',
  '高级成功服务（仅工单）',
  '高级成功服务（2023版）',
  '战略客户绿色通道',
  '服务期外',
  '标准成功服务',
]
export const BRANCH = {
  A: { label: 'A-Bug', type: 'danger' },
  B: { label: 'B-需求', type: 'warning' },
  C: { label: 'C-补料', type: 'info' },
  D: { label: 'D-正常', type: 'success' },
}
export const REVIEW = {
  pending_review: { label: '待审', type: 'info' },
  approved: { label: '通过', type: 'success' },
  rejected: { label: '驳回', type: 'danger' },
}
export const SLA_STATE = {
  normal: { label: '正常', type: 'success' },
  breached: { label: '超时', type: 'danger' },
}
// hub 研发单状态：待跟进/研发中/测试中/已发版
export const HUB_STATUS = {
  待处理: { label: '待处理', type: 'info' },
  pending_follow: { label: '待跟进', type: 'info' },
  developing: { label: '研发中', type: 'primary' },
  testing: { label: '测试中', type: 'warning' },
  released: { label: '已发版', type: 'success' },
}
// hub 单类型：需求/bug
export const HUB_TYPE = {
  requirement: { label: '需求', type: 'warning' },
  bug: { label: 'bug', type: 'danger' },
}
export const LINEAR_SYNC = {
  pending: { label: '同步中', type: 'info' },
  synced: { label: '已同步', type: 'success' },
  failed: { label: '失败', type: 'danger' },
}
// 产品线白名单（权威源 ticket-tagging SKILL.md；新增模块责任人时下拉选择）
export const PRODUCT_LINES = [
  '星瀚-开票', '星瀚-收票', '星瀚-影像', '星瀚-档案',
  '星空旗舰版-开票', '星空旗舰版-收票',
  '标准版-开票', '标准版-收票', '标准版-影像',
  '标准版(星空企业版)-开票', '标准版(星空企业版)-收票',
  'EOP运营', '基础研发',
]
// 角色权限等级
export const ROLE_RANK = { visitor: 0, handler: 1, admin: 2 }
export const dict = (map, key) => map[key] || { label: key || '-', type: 'info' }
