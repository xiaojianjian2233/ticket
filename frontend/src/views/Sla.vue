<script setup>
import { onMounted, ref } from 'vue'
import { slaApi } from '@/api'
import { useAuth } from '@/stores/auth'
const auth = useAuth()
const tab = ref('list')
const rows = ref([]); const alerts = ref({ pending: 0, abandoned: [] }); const overview = ref({ breachTotal: 0, topOwners: [] })
const load = async () => {
  const d = await slaApi.list({ page_no: 1, page_size: 50 }); rows.value = d.items
  overview.value = await slaApi.overview()
  if (auth.can('admin')) { try { alerts.value = await slaApi.systemAlerts() } catch {} }
}
const requeue = async (id) => { await slaApi.requeue(id); load() }
onMounted(load)
</script>
<template>
  <el-card>
    <el-row :gutter="16" style="margin-bottom:16px">
      <el-col :span="6"><el-card shadow="never"><div style="color:#888">超时累计</div><div style="font-size:24px;font-weight:700">{{ overview.breachTotal }}</div></el-card></el-col>
    </el-row>
    <el-tabs v-model="tab">
      <el-tab-pane label="SLA超时列表" name="list">
        <el-table :data="rows" stripe>
          <el-table-column prop="slaType" label="类型" width="90"><template #default="{row}"><el-tag size="small" :type="row.slaType==='rd'?'warning':'primary'">{{ row.slaType==='rd'?'研发':'人工' }}</el-tag></template></el-table-column>
          <el-table-column prop="owner" label="责任人" width="120"/>
          <el-table-column prop="refId" label="单ID" width="100"/>
          <el-table-column prop="overdueHours" label="超时(h)" width="100"/>
          <el-table-column prop="notifyMark" label="通报时点"/>
        </el-table>
      </el-tab-pane>
      <el-tab-pane v-if="auth.can('admin')" label="系统告警" name="alerts">
        <p>队列待处理：{{ alerts.pending }}</p>
        <el-table :data="alerts.abandoned" stripe>
          <el-table-column prop="id" label="任务ID" width="90"/>
          <el-table-column prop="taskType" label="类型" width="140"/>
          <el-table-column prop="lastError" label="错误" show-overflow-tooltip/>
          <el-table-column label="操作" width="100"><template #default="{row}"><el-button size="small" @click="requeue(row.id)">重入队</el-button></template></el-table-column>
        </el-table>
      </el-tab-pane>
    </el-tabs>
  </el-card>
</template>
