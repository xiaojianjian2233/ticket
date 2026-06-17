import { createRouter, createWebHashHistory } from 'vue-router'
import { useAuth } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const Layout = () => import('@/layout/Layout.vue')

export const routes = [
  { path: '/login', component: () => import('@/views/Login.vue'), meta: { public: true, title: '登录' } },
  {
    path: '/',
    component: Layout,
    children: [
      { path: '', redirect: '/tickets' },        // 进入系统默认看工单列表
      { path: 'overview', name: 'home', component: () => import('@/views/Home.vue'), meta: { title: '概览', icon: 'HomeFilled', top: true } },
      { path: 'tickets', name: 'tickets', component: () => import('@/views/tickets/List.vue'), meta: { title: '工单列表', icon: 'Tickets', top: true } },
      { path: 'tickets/unhandled', name: 'unhandled', component: () => import('@/views/tickets/Unhandled.vue'), meta: { title: '未接管工单列表', icon: 'Warning', top: true } },
      { path: 'tickets/my-pending', name: 'myPending', component: () => import('@/views/tickets/List.vue'), meta: { title: '待我处理的工单', icon: 'List', role: 'handler', scope: 'myPending', top: true } },
      { path: 'tickets/:id', name: 'ticketDetail', component: () => import('@/views/tickets/Detail.vue'), meta: { title: '工单详情', hidden: true } },
      { path: 'workbench', name: 'workbench', component: () => import('@/views/Workbench.vue'), meta: { title: '我的待办', hidden: true, role: 'handler' } },
      { path: 'hubs', name: 'hubs', component: () => import('@/views/hubs/List.vue'), meta: { title: 'hub工单', icon: 'SetUp', menu: 'hub管理', role: 'handler' } },
      { path: 'hubs/:id', name: 'hubDetail', component: () => import('@/views/hubs/Detail.vue'), meta: { title: 'hub工单详情', hidden: true, role: 'handler' } },
      { path: 'faq', name: 'faq', component: () => import('@/views/faq/Manage.vue'), meta: { title: 'FAQ管理', icon: 'Collection', menu: '知识库' } },
      { path: 'faq/browse', name: 'faqBrowse', component: () => import('@/views/faq/Browse.vue'), meta: { title: '知识库查阅', icon: 'Search', menu: '知识库' } },
      { path: 'faq/review', name: 'faqReview', component: () => import('@/views/faq/Review.vue'), meta: { title: 'FAQ审核', icon: 'Checked', menu: '知识库', role: 'handler' } },
      { path: 'sla', name: 'sla', component: () => import('@/views/Sla.vue'), meta: { title: 'SLA监控', icon: 'AlarmClock', top: true } },
      { path: 'assistant', name: 'assistant', component: () => import('@/views/Assistant.vue'), meta: { title: '工单助手', icon: 'ChatDotRound', hidden: true } },
      { path: 'system/users', name: 'users', component: () => import('@/views/system/Users.vue'), meta: { title: '用户管理', icon: 'User', menu: '系统配置', role: 'admin' } },
      { path: 'system/skills', name: 'skills', component: () => import('@/views/system/Skills.vue'), meta: { title: 'Skill管理', icon: 'MagicStick', menu: '系统配置', role: 'admin' } },
      { path: 'system/dispatch', name: 'dispatch', component: () => import('@/views/system/Dispatch.vue'), meta: { title: '派单规则管理', icon: 'Share', menu: '系统配置', role: 'admin' } },
      { path: 'system/module-owners', name: 'moduleOwners', component: () => import('@/views/system/ModuleOwners.vue'), meta: { title: '模块责任人', icon: 'Connection', menu: '系统配置', role: 'admin' } },
    ],
  },
]

const router = createRouter({ history: createWebHashHistory('/fpy/'), routes })

router.beforeEach((to) => {
  const auth = useAuth()
  if (to.meta.public) return true
  if (!auth.isLogin) return { path: '/login' }
  if (to.meta.role && !auth.can(to.meta.role)) {
    ElMessage.error('您没有权限访问该页面')
    return { path: '/' }
  }
  return true
})

export default router
