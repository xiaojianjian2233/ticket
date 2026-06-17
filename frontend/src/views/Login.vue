<script setup>
import { ref } from 'vue'
import { useAuth } from '@/stores/auth'
import { ElMessage } from 'element-plus'

const auth = useAuth()
const loading = ref(false)

const login = async () => {
  loading.value = true
  try {
    const url = await auth.fetchLoginUrl()
    window.location.href = url
  } catch {
    ElMessage.error('获取登录地址失败')
    loading.value = false
  }
}
</script>

<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <div class="logo">🎫 ticket-hub</div>
      <div class="sub">发票云工单自动处理中台</div>
      <el-button type="primary" size="large" :loading="loading" style="width: 100%" @click="login">
        飞书登录
      </el-button>
      <div class="tip">使用飞书账号授权登录（新用户默认只读）</div>
    </el-card>
  </div>
</template>

<style scoped>
.login-wrap { height: 100vh; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #1677ff22, #f5f7fa); }
.login-card { width: 360px; text-align: center; padding: 24px 8px; }
.logo { font-size: 26px; font-weight: 700; margin-bottom: 8px; }
.sub { color: #888; margin-bottom: 28px; }
.tip { color: #aaa; font-size: 12px; margin-top: 16px; }
</style>
