<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const auth = useAuth()
const router = useRouter()
const booting = ref(true)

onMounted(async () => {
  // 仅本地开发(npm run dev)：强制以 admin 登录，免手动注入；生产构建被 import.meta.env.DEV=false 剔除
  if (import.meta.env.DEV) {
    const DEV_ADMIN_TOKEN = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxIiwibmFtZSI6Ilx1NjcyY1x1NTczMFx1OTg4NFx1ODljOGFkbWluIiwicm9sZSI6ImFkbWluIiwiaWF0IjoxNzgxMTM4NDcwLCJleHAiOjE3ODE3NDMyNzB9.wZcTs-3xdZAwBj2GATdWVL2_ceAs6wp2Wz68NQM8J6Q'
    auth.setSession(DEV_ADMIN_TOKEN, { id: 1, name: '本地预览(admin)', role: 'admin', feishuUid: 'dev' })
  }
  // 飞书 callback：redirect_uri 落在 /fpy/?code=xxx（根路径），在此统一处理
  const params = new URLSearchParams(window.location.search)
  const code = params.get('code')
  if (code && !auth.isLogin) {
    try {
      await auth.handleCallback(code)
      ElMessage.success('登录成功')
    } catch {
      ElMessage.error('登录失败，请重试')
    }
    // 清除 query，回到首页
    window.history.replaceState({}, '', import.meta.env.BASE_URL)
    router.replace('/')
  }
  booting.value = false
})
</script>

<template>
  <router-view v-if="!booting" />
  <div v-else style="display: flex; height: 100vh; align-items: center; justify-content: center">登录态加载中…</div>
</template>
