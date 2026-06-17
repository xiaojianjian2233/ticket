<script setup>
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { routes } from '@/router'
import { useAuth } from '@/stores/auth'
import AssistantWidget from '@/components/AssistantWidget.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuth()

// 一级菜单（meta.top）
const topItems = computed(() => {
  const children = routes.find((r) => r.path === '/').children
  return children.filter((r) => r.meta?.top && !r.meta?.hidden && (!r.meta.role || auth.can(r.meta.role)))
})
// 分组菜单（按角色 + menu 分组）
const menus = computed(() => {
  const children = routes.find((r) => r.path === '/').children
  const groups = {}
  for (const r of children) {
    if (r.meta?.hidden || !r.meta?.menu) continue
    if (r.meta.role && !auth.can(r.meta.role)) continue
    ;(groups[r.meta.menu] ||= []).push(r)
  }
  return groups
})

// —— 页签栏 tagsView ——
const tabs = ref([{ title: '概览', path: '/overview', affix: true }])
function tabTitle() {
  if (route.name === 'ticketDetail') return route.query.no || ('工单' + route.params.id)  // 页签名=工单编号
  if (route.name === 'hubDetail') return 'hub#' + route.params.id
  return route.meta?.title || route.name
}
watch(
  () => route.fullPath,
  () => {
    const title = tabTitle()
    if (!title) return
    if (!tabs.value.find((t) => t.path === route.fullPath)) {
      tabs.value.push({ title, path: route.fullPath })
    }
  },
  { immediate: true },
)
const isActive = (p) => p === route.fullPath
const goTab = (p) => router.push(p)
const closeTab = (p) => {
  const i = tabs.value.findIndex((t) => t.path === p)
  if (i < 0 || tabs.value[i].affix) return
  tabs.value.splice(i, 1)
  if (isActive(p)) router.push(tabs.value[Math.max(0, i - 1)].path)
}
const logout = () => { auth.logout(); router.push('/login') }
</script>

<template>
  <el-container style="height: 100vh">
    <el-aside width="210px" style="background: #001529; overflow:auto">
      <div style="height:48px;color:#fff;display:flex;align-items:center;justify-content:center;font-weight:600">🎫 ticket-hub</div>
      <el-menu :default-active="route.path" router background-color="#001529" text-color="#bfcbd9" active-text-color="#fff">
        <el-menu-item v-for="m in topItems" :key="m.path" :index="'/' + m.path">
          <el-icon><component :is="m.meta.icon" /></el-icon><span>{{ m.meta.title }}</span>
        </el-menu-item>
        <el-sub-menu v-for="(items, group) in menus" :key="group" :index="group">
          <template #title>{{ group }}</template>
          <el-menu-item v-for="m in items" :key="m.path" :index="'/' + m.path">
            <el-icon><component :is="m.meta.icon" /></el-icon><span>{{ m.meta.title }}</span>
          </el-menu-item>
        </el-sub-menu>
      </el-menu>
    </el-aside>

    <el-container>
      <!-- 顶部页面名称栏：高度 30px -->
      <el-header style="height:30px;line-height:30px;padding:0 14px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #eee;background:#fff">
        <span style="font-size:13px;color:#333">{{ route.meta.title || '' }}</span>
        <el-dropdown @command="(c)=>c==='logout'&&logout()">
          <span style="cursor:pointer;font-size:13px">{{ auth.user?.name }} <el-tag size="small" type="info">{{ auth.role }}</el-tag></span>
          <template #dropdown><el-dropdown-menu><el-dropdown-item command="logout">退出登录</el-dropdown-item></el-dropdown-menu></template>
        </el-dropdown>
      </el-header>

      <!-- 页签栏 -->
      <div class="tags-bar">
        <span v-for="t in tabs" :key="t.path" class="tag" :class="{ active: isActive(t.path) }" @click="goTab(t.path)">
          {{ t.title }}
          <el-icon v-if="!t.affix" class="close" @click.stop="closeTab(t.path)"><Close /></el-icon>
        </span>
      </div>

      <el-main style="background:#f5f7fa;padding:14px">
        <router-view :key="route.fullPath" />
      </el-main>
    </el-container>

    <!-- 全局悬浮工单助手 -->
    <AssistantWidget />
  </el-container>
</template>

<style scoped>
.tags-bar { display:flex; gap:6px; padding:6px 10px; background:#fff; border-bottom:1px solid #eee; overflow-x:auto; flex-wrap:wrap; }
.tag { display:inline-flex; align-items:center; gap:4px; padding:3px 12px; font-size:12px; cursor:pointer;
       background:#fff; color:#888; border:1px solid #dcdfe6; border-radius:3px; white-space:nowrap; }
.tag.active { background:#1677ff; color:#fff; border-color:#1677ff; }
.tag .close { font-size:12px; }
.tag .close:hover { background:rgba(0,0,0,.15); border-radius:50%; }
</style>
