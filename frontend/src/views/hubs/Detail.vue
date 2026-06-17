<script setup>
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { hubApi } from '@/api'
import { useAuth } from '@/stores/auth'
import { ElMessage } from 'element-plus'
const route = useRoute(); const router = useRouter(); const auth = useAuth()
const h = ref(null)
const load = async () => { h.value = await hubApi.detail(route.params.id) }
const resync = async () => { await hubApi.resyncLinear(route.params.id); ElMessage.success('已触发重新同步'); load() }
const syncing = ref(false)
const syncStatus = async () => {
  syncing.value = true
  try {
    const r = await hubApi.syncStatus(route.params.id)
    ElMessage.success(r.changed ? `已从 Linear 同步：${r.status}` : `已是最新：${r.status}`)
    load()
  } finally { syncing.value = false }
}
onMounted(load)
</script>
<template>
  <div v-if="h">
    <el-page-header @back="router.back()" :content="h.hubNo" style="margin-bottom:16px"/>
    <el-card style="margin-bottom:16px"><template #header>hub工单信息</template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="标题">{{ h.title }}</el-descriptions-item>
        <el-descriptions-item label="产品线">{{ h.productTag }}</el-descriptions-item>
        <el-descriptions-item label="功能模块">{{ h.funcModule || '-' }}</el-descriptions-item>
        <el-descriptions-item label="责任人">{{ h.devOwner }}</el-descriptions-item>
        <el-descriptions-item label="研发状态">{{ h.rdStatus }}</el-descriptions-item>
        <el-descriptions-item label="处理人">{{ h.rdHandler || '-' }}</el-descriptions-item>
        <el-descriptions-item label="说明" :span="2">{{ h.rdStatusNote || '-' }}</el-descriptions-item>
        <el-descriptions-item label="问题摘要" :span="2">{{ h.problemSummary || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
    <el-card style="margin-bottom:16px"><template #header>Linear</template>
      <p>同步状态：{{ h.linearSyncStatus }}</p>
      <el-link v-if="h.linearUrl" :href="h.linearUrl" target="_blank" type="primary">{{ h.linearUrl }}</el-link>
      <div style="margin-top:10px;display:flex;gap:10px">
        <el-button v-if="auth.can('handler')" type="primary" color="#0052d9" :loading="syncing" @click="syncStatus">从 Linear 同步状态</el-button>
        <el-button v-if="auth.can('admin') && h.linearSyncStatus==='failed'" @click="resync">重新同步 Linear</el-button>
      </div>
    </el-card>
    <el-card><template #header>关联 info 工单 ({{ (h.linkedTickets||[]).length }})</template>
      <el-table :data="h.linkedTickets" stripe>
        <el-table-column prop="ticketNo" label="工单号"/>
        <el-table-column label="操作" width="100"><template #default="{row}"><el-button size="small" @click="router.push(`/tickets/${row.id}`)">查看</el-button></template></el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
