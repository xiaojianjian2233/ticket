<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ticketApi } from '@/api'
import { useAuth } from '@/stores/auth'
import { SOURCE, dict } from '@/dicts'
import { ElMessage, ElMessageBox } from 'element-plus'

const router = useRouter()
const auth = useAuth()
const loading = ref(false)
const rows = ref([])

// 默认近 7 天
const _fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
const _now = new Date()
const _ago7 = new Date(Date.now() - 6 * 24 * 3600 * 1000)
const q = reactive({ keyword: '', range: [_fmt(_ago7), _fmt(_now)] })

const load = async () => {
  loading.value = true
  try {
    const params = { keyword: q.keyword, page_no: 1, page_size: 50 }
    if (q.range && q.range.length === 2) {
      params.created_from = q.range[0] + ' 00:00:00'
      params.created_to = q.range[1] + ' 23:59:59'
    }
    const d = await ticketApi.unhandled(params)
    rows.value = d.items
  } finally { loading.value = false }
}
const reset = () => { q.keyword = ''; q.range = [_fmt(_ago7), _fmt(_now)]; load() }
const openDetail = (row) => router.push(`/tickets/${row.id}?no=${encodeURIComponent(row.ticketNo)}`)
const takeover = async (row) => {
  await ElMessageBox.confirm(`确认接管工单 ${row.ticketNo}？将转入人工待办。`, '接管工单')
  await ticketApi.takeover(row.id)
  ElMessage.success('已接管')
  load()
}
onMounted(load)
</script>

<template>
  <el-card>
    <!-- 筛选 -->
    <el-form :inline="true" @submit.prevent>
      <el-form-item label="工单编号"><el-input v-model="q.keyword" placeholder="工单编号" clearable style="width:200px" @keyup.enter="load" /></el-form-item>
      <el-form-item label="创建时间">
        <el-date-picker v-model="q.range" type="daterange" value-format="YYYY-MM-DD"
          start-placeholder="开始日期" end-placeholder="结束日期" :clearable="false" style="width:260px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" color="#0052d9" @click="load">查询</el-button>
        <el-button @click="reset">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe border>
      <el-table-column label="工单编号" width="172" fixed="left">
        <template #default="{row}"><el-link type="primary" :underline="false" @click="openDetail(row)" style="color:#0052d9;font-weight:600">{{ row.ticketNo }}</el-link></template>
      </el-table-column>
      <el-table-column prop="sourceBillNo" label="工单来源编号" width="160" show-overflow-tooltip><template #default="{row}">{{ row.sourceBillNo || '-' }}</template></el-table-column>
      <el-table-column prop="problemContent" label="问题内容" min-width="240" show-overflow-tooltip><template #default="{row}">{{ row.problemContent || '-' }}</template></el-table-column>
      <el-table-column label="工单附件" width="90" align="center">
        <template #default="{row}"><el-tag v-if="row.hasAttachment" type="success" size="small">有</el-tag><span v-else>无</span></template>
      </el-table-column>
      <el-table-column label="不接管原因" min-width="200" show-overflow-tooltip>
        <template #default="{row}">{{ row.routeReason || row.routeAction || '-' }}</template>
      </el-table-column>
      <el-table-column label="来源" width="90"><template #default="{row}"><el-tag :type="dict(SOURCE,row.source).type" size="small">{{ dict(SOURCE,row.source).label }}</el-tag></template></el-table-column>
      <el-table-column prop="createdAt" label="工单创建时间" width="170"><template #default="{row}">{{ row.createdAt ? new Date(row.createdAt).toLocaleString('zh-CN',{hour12:false}) : '-' }}</template></el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{row}">
          <el-button v-if="auth.can('handler')" size="small" type="primary" color="#0052d9" @click="takeover(row)">接管</el-button>
          <span v-else>-</span>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
