<script setup>
import { onMounted, reactive, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ticketApi } from '@/api'
import { useAuth } from '@/stores/auth'
import { STATUS, SOURCE, SOURCE_FILTER, SERVICE_LEVEL, SLA_STATE, TICKET_TYPE, dict } from '@/dicts'
import { useDragColumns } from '@/composables/useDragColumns'
import { ElMessage } from 'element-plus'

const router = useRouter()
const route = useRoute()
const scope = route.meta.scope         // 'myPending' → 待我处理的工单（处理人=我 + 处理中）
const auth = useAuth()
const loading = ref(false)
const rows = ref([])
const total = ref(0)
const tableRef = ref()
const selected = ref([])

// 筛选：来源/服务等级多选；默认全部。ticketNos 来自 hub 页「关联工单号」跳转(?nos=)
// 日期时间格式化（年月日 时分秒）
const pad = (n) => String(n).padStart(2, '0')
const fmtDt = (s) => {
  if (!s) return '-'
  const d = new Date(s)
  if (isNaN(d)) return s
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
// 创建时间筛选默认近 7 天 [起, 止]
const defaultRange = () => {
  const end = new Date()
  const start = new Date(end.getTime() - 6 * 24 * 3600 * 1000)
  start.setHours(0, 0, 0, 0)
  const f = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  return [f(start), f(end)]
}
const q = reactive({ sourceSel: [], statusSel: [], slaSel: [], serviceSel: [], keyword: '', createdRange: defaultRange(), ticketNos: [], page_no: 1, page_size: 20 })
if (route.query.nos) q.ticketNos = String(route.query.nos).split(',').filter(Boolean)

// 列定义（默认顺序），可拖动调整顺序；列宽由 border 原生拖动
// 工单号、来源工单编号为固定左列（见模板），其余可拖动
const columns = ref([
  { key: 'problemContent', label: '问题内容', minWidth: 220, tooltip: true },
  { key: 'handleNote', label: '处理说明', minWidth: 200, tooltip: true },
  { key: 'productTag', label: '产品线', width: 120, prop: 'productTag' },
  { key: 'funcModule', label: '问题模块', width: 120, prop: 'funcModule', tooltip: true },
  { key: 'status', label: '工单状态', width: 110 },
  { key: 'ticketType', label: '工单类型', width: 110 },
  { key: 'dispatchAssignee', label: '处理人', width: 95 },
  { key: 'devOwner', label: '责任田负责人', width: 120 },
  { key: 'customerContact', label: '联系人姓名', width: 100, prop: 'customerContact' },
  { key: 'customerMobile', label: '联系人电话', width: 120, prop: 'customerMobile' },
  { key: 'customerEmail', label: '联系人邮箱', width: 150, prop: 'customerEmail', tooltip: true },
  { key: 'source', label: '来源', width: 90 },
  { key: 'customerCompany', label: '提单企业名称', width: 150, prop: 'customerCompany', tooltip: true },
  { key: 'customerTaxNo', label: '提单企业税号', width: 150, prop: 'customerTaxNo', tooltip: true },
  { key: 'customerTenant', label: '归属租户', width: 110, prop: 'customerTenant', tooltip: true },
  { key: 'returnCount', label: '客户驳回次数', width: 110, align: 'center' },
  { key: 'slaState', label: 'SLA', width: 80 },
  { key: 'remainingHours', label: '剩余处理时间(小时)', width: 150, align: 'center' },
  { key: 'serviceLevel', label: '服务等级', width: 170, prop: 'serviceLevel', tooltip: true },
  { key: 'createdAt', label: '创建时间', width: 165, align: 'center' },
  { key: 'resolvedAt', label: '处理完成时间', width: 165, align: 'center' },
  { key: 'closedAt', label: '处理关闭时间', width: 165, align: 'center' },
])
const { reset: resetCols } = useDragColumns(tableRef, columns, 'ticket-list-cols-v3')

const buildParams = () => {
  const sources = [...new Set(q.sourceSel.flatMap((l) => SOURCE_FILTER.find((o) => o.label === l)?.sources || []))]
  return {
    sources: sources.join(','),
    service_level: q.serviceSel.join(','),
    status: q.statusSel.join(','),
    sla_state: q.slaSel.join(','),
    keyword: q.keyword,
    created_from: (q.createdRange && q.createdRange[0]) || '',
    created_to: (q.createdRange && q.createdRange[1]) || '',
    ticket_nos: q.ticketNos.join(','),
    page_no: q.page_no,
    page_size: q.page_size,
  }
}
// 筛选条件缓存：进详情再返回时不重置（按页面 scope 区分 工单列表/待我处理）。手动「重置」会写回空态。
const CACHE_KEY = `ticket-list-filters:${scope || 'tickets'}`
const saveFilters = () => { try { sessionStorage.setItem(CACHE_KEY, JSON.stringify(q)) } catch (e) { /* ignore */ } }
const restoreFilters = () => {
  try {
    const s = sessionStorage.getItem(CACHE_KEY)
    if (s) Object.assign(q, JSON.parse(s))
  } catch (e) { /* ignore */ }
}
const load = async () => {
  saveFilters()                          // 每次查询/翻页都缓存当前筛选
  loading.value = true
  try {
    const fn = scope === 'myPending' ? ticketApi.myPending : ticketApi.list
    const d = await fn(buildParams()); rows.value = d.items; total.value = d.total
  } finally { loading.value = false }
}
const reset = () => { Object.assign(q, { sourceSel: [], statusSel: [], slaSel: [], serviceSel: [], keyword: '', createdRange: defaultRange(), ticketNos: [], page_no: 1 }); load() }
const clearNos = () => { q.ticketNos = []; q.page_no = 1; load() }
const quickClose = async (row) => { await ticketApi.close(row.id, {}); ElMessage.success('已关单'); load() }
const openDetail = (row) => router.push(`/tickets/${row.id}?no=${encodeURIComponent(row.ticketNo)}`)
const onSelect = (rs) => { selected.value = rs }

// —— 批量关闭 ——
const batch = reactive({ visible: false, loading: false, result: null })
const batchClose = async () => {
  if (!selected.value.length) return ElMessage.warning('请先勾选工单')
  batch.visible = true; batch.loading = true; batch.result = null
  try {
    const ids = selected.value.map((r) => r.id)
    batch.result = await ticketApi.batchClose(ids)
  } catch (e) {
    batch.result = { error: true }
  } finally { batch.loading = false; load() }
}
const skipReasons = () => {
  const ds = batch.result?.details || []
  return [...new Set(ds.filter((d) => d.result === 'skipped').map((d) => d.reason))].join('；') || '-'
}
// hub 跳转(?nos=)优先用传入工单号；否则恢复上次筛选缓存
onMounted(() => { if (!route.query.nos) restoreFilters(); load() })
</script>

<template>
  <el-card>
    <!-- 筛选区：4 个一行，与列表等宽对齐，超 4 个换行；查询/重置占一个位置 -->
    <el-row :gutter="12" class="filter-row">
      <el-col :span="6">
        <div class="filter-item"><span class="lbl">来源</span>
          <el-select v-model="q.sourceSel" multiple collapse-tags collapse-tags-tooltip placeholder="全部" clearable style="width:100%">
            <el-option v-for="o in SOURCE_FILTER" :key="o.label" :label="o.label" :value="o.label" />
          </el-select>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="filter-item"><span class="lbl">工单状态</span>
          <el-select v-model="q.statusSel" multiple collapse-tags collapse-tags-tooltip placeholder="全部" clearable style="width:100%">
            <el-option v-for="(v,k) in STATUS" :key="k" :label="v.label" :value="k" />
          </el-select>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="filter-item"><span class="lbl">SLA</span>
          <el-select v-model="q.slaSel" multiple collapse-tags collapse-tags-tooltip placeholder="全部" clearable style="width:100%">
            <el-option v-for="(v,k) in SLA_STATE" :key="k" :label="v.label" :value="k" />
          </el-select>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="filter-item"><span class="lbl">服务等级</span>
          <el-select v-model="q.serviceSel" multiple collapse-tags collapse-tags-tooltip placeholder="全部" clearable style="width:100%">
            <el-option v-for="s in SERVICE_LEVEL" :key="s" :label="s" :value="s" />
          </el-select>
        </div>
      </el-col>
      <el-col :span="6">
        <div class="filter-item"><span class="lbl">创建时间</span>
          <el-date-picker v-model="q.createdRange" type="datetimerange" range-separator="至"
            start-placeholder="开始时间" end-placeholder="结束时间" value-format="YYYY-MM-DD HH:mm:ss"
            :default-time="[new Date(2000,0,1,0,0,0), new Date(2000,0,1,23,59,59)]" style="width:100%" />
        </div>
      </el-col>
      <el-col :span="6">
        <div class="filter-item"><span class="lbl">关键词</span>
          <el-input v-model="q.keyword" placeholder="工单号/问题" clearable style="width:100%" @keyup.enter="q.page_no=1;load()" />
        </div>
      </el-col>
      <el-col :span="6">
        <div class="filter-item filter-btns">
          <el-button type="primary" color="#0052d9" @click="q.page_no=1;load()">查询</el-button>
          <el-button @click="reset">重置</el-button>
        </div>
      </el-col>
    </el-row>

    <!-- 工具条：批量操作 -->
    <div class="toolbar">
      <el-button type="primary" color="#0052d9" plain :disabled="!selected.length" @click="batchClose">
        批量关闭<span v-if="selected.length">（{{ selected.length }}）</span>
      </el-button>
      <el-button link type="info" @click="resetCols">恢复默认列序</el-button>
      <el-tag v-if="q.ticketNos.length" closable type="warning" @close="clearNos">按关联工单筛选：{{ q.ticketNos.length }} 个</el-tag>
    </div>

    <el-table ref="tableRef" :data="rows" v-loading="loading" stripe border @selection-change="onSelect" row-key="id">
      <el-table-column type="selection" width="44" fixed="left" reserve-selection />
      <el-table-column label="工单号" width="172" fixed="left">
        <template #default="{ row }"><el-link type="primary" :underline="false" @click="openDetail(row)" style="color:#0052d9;font-weight:600">{{ row.ticketNo }}</el-link></template>
      </el-table-column>
      <el-table-column label="来源工单编号" width="160" fixed="left" show-overflow-tooltip>
        <template #default="{ row }">{{ row.sourceBillNo || '-' }}</template>
      </el-table-column>
      <el-table-column
        v-for="col in columns" :key="col.key"
        :label="col.label" :width="col.width" :min-width="col.minWidth"
        :align="col.align || 'left'" :show-overflow-tooltip="col.tooltip" label-class-name="drag-col">
        <template #default="{ row }">
          <el-link v-if="col.key==='ticketNo'" type="primary" :underline="false" @click="openDetail(row)" style="color:#0052d9;font-weight:600">{{ row.ticketNo }}</el-link>
          <el-tag v-else-if="col.key==='source'" :type="dict(SOURCE,row.source).type" size="small">{{ dict(SOURCE,row.source).label }}</el-tag>
          <template v-else-if="col.key==='ticketType'">
            <el-tag v-if="row.ticketType" :type="dict(TICKET_TYPE,row.ticketType).type" size="small">{{ row.ticketType }}</el-tag><span v-else>-</span>
          </template>
          <el-tag v-else-if="col.key==='status'" :type="dict(STATUS,row.status).type" size="small">{{ dict(STATUS,row.status).label }}</el-tag>
          <el-tag v-else-if="col.key==='slaState'" :type="dict(SLA_STATE,row.slaState).type" size="small">{{ dict(SLA_STATE,row.slaState).label }}</el-tag>
          <template v-else-if="col.key==='devOwner'">
            <span v-if="row.devOwner && !row.devOwnerMissing">{{ row.devOwner }}</span><el-tag v-else type="warning" size="small">未分配</el-tag>
          </template>
          <template v-else-if="col.key==='returnCount'">
            <el-tag v-if="row.returnCount>0" type="danger" size="small">{{ row.returnCount }}</el-tag><span v-else>0</span>
          </template>
          <span v-else-if="col.key==='dispatchAssignee'">{{ row.dispatchAssignee || '-' }}</span>
          <span v-else-if="col.key==='handleNote'">{{ row.handleNote || '-' }}</span>
          <span v-else-if="col.key==='problemContent'">{{ row.problemContent || '-' }}</span>
          <template v-else-if="col.key==='remainingHours'">
            <span v-if="row.remainingHours == null">-</span>
            <span v-else :style="{ color: row.remainingHours < 0 ? '#f56c6c' : '#1f2937', fontWeight: 600 }">
              {{ row.remainingHours < 0 ? '超时 ' + Math.abs(row.remainingHours) : row.remainingHours }}
            </span>
          </template>
          <span v-else-if="col.key==='serviceLevel'">{{ row.serviceLevel || '-' }}</span>
          <span v-else-if="['createdAt','resolvedAt','closedAt'].includes(col.key)">{{ fmtDt(row[col.key]) }}</span>
          <span v-else>{{ row[col.prop] ?? '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button v-if="auth.can('handler') && !['done','closed','returned'].includes(row.status)" size="small" type="primary" color="#0052d9" @click="quickClose(row)">关单</el-button>
          <span v-else>-</span>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination style="margin-top:16px;justify-content:flex-end" layout="total, prev, pager, next" :total="total" :page-size="q.page_size" :current-page="q.page_no" @current-change="(p)=>{q.page_no=p;load()}" />

    <!-- 批量关闭结果弹窗 -->
    <el-dialog v-model="batch.visible" title="批量关闭" width="420px" :close-on-click-modal="false">
      <div v-if="batch.loading" v-loading="true" style="min-height:90px;display:flex;align-items:center;justify-content:center;color:#909399">
        后台正在处理中…
      </div>
      <div v-else-if="batch.result?.error" style="color:#f56c6c">处理失败，请重试。</div>
      <div v-else-if="batch.result" class="batch-result">
        <p>本次勾选 <b>{{ batch.result.total }}</b> 单</p>
        <p>成功关闭 <b style="color:#67c23a">{{ batch.result.success }}</b> ，失败 <b style="color:#f56c6c">{{ batch.result.failed }}</b> ，未执行 <b style="color:#e6a23c">{{ batch.result.skipped }}</b></p>
        <p v-if="batch.result.skipped">未执行原因：{{ skipReasons() }}</p>
      </div>
      <template #footer><el-button type="primary" :disabled="batch.loading" @click="batch.visible=false">知道了</el-button></template>
    </el-dialog>
  </el-card>
</template>

<style scoped>
.filter-row { margin-bottom: 4px; }
.filter-item { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.filter-item .lbl { width: 60px; text-align: right; color: #606266; font-size: 13px; flex-shrink: 0; }
.filter-btns { justify-content: flex-start; }
.toolbar { display: flex; align-items: center; gap: 8px; margin: 4px 0 12px; }
:deep(.drag-col) { cursor: move; }
</style>
