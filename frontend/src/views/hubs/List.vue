<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { hubApi } from '@/api'
import { HUB_STATUS, HUB_TYPE, dict } from '@/dicts'

const router = useRouter()
const loading = ref(false)
const rows = ref([])          // 真实 hub 数据（后端 /hubs）

// 状态筛选项（= Linear 工作流状态 + 待处理；值与 hub.status 原文一致）
const HUB_STATUS_OPTIONS = [
  'Backlog', 'Todo', '计划', '需求编写中', '需求评审完成', '技术设计完成', '设计评审完成',
  '编码&自测完成', '提测完成', '测试完成', '发布完成', 'Canceled', '已失效', '产研退回', '待处理',
]

const pad = (n) => String(n).padStart(2, '0')
const fmtDt = (s) => {
  if (!s) return ''
  const d = new Date(s)
  if (isNaN(d)) return s
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}
const load = async () => {
  loading.value = true
  try {
    // 拉全量（hub 量小），过滤在前端做，保留筛选 UI
    const d = await hubApi.list({ page_no: 1, page_size: 1000 })
    rows.value = (d.items || []).map((h) => ({
      id: h.id, hubNo: h.hubNo, problemSummary: h.problemSummary, rdNote: h.rdNote || '',
      type: h.type || '', status: h.rdStatus || '', devOwner: h.devOwner || '',
      productTag: h.productTag || '', funcModule: h.funcModule || '',
      createdAt: fmtDt(h.createdAt), rdResolvedAt: fmtDt(h.rdResolvedAt), releaseAt: fmtDt(h.releaseAt),
      releaseVersion: h.releaseVersion || '', ticketNos: h.ticketNos || [],
    }))
  } finally { loading.value = false }
}

const q = reactive({
  hubNo: '', devOwner: '', types: [], statuses: [], products: [], versions: [], ticketNos: [],
  createdRange: [], rdResolvedRange: [], releaseRange: [],
})

// 下拉选项（从真实数据去重）
const productOptions = computed(() => [...new Set(rows.value.map((r) => r.productTag).filter(Boolean))])
const versionOptions = computed(() => [...new Set(rows.value.map((r) => r.releaseVersion).filter(Boolean))])
const ticketOptions = computed(() => [...new Set(rows.value.flatMap((r) => r.ticketNos))])

const _inRange = (dt, range) => {
  if (!range || range.length < 2) return true
  if (!dt) return false
  const d = dt.slice(0, 10)
  return d >= range[0] && d <= range[1]
}
function snapshot() {
  return {
    hubNo: q.hubNo, devOwner: q.devOwner,
    types: [...q.types], statuses: [...q.statuses], products: [...q.products],
    versions: [...q.versions], ticketNos: [...q.ticketNos],
    createdRange: [...q.createdRange], rdResolvedRange: [...q.rdResolvedRange], releaseRange: [...q.releaseRange],
  }
}
const applied = ref(snapshot())     // 点「查询」才应用
const search = () => { applied.value = snapshot() }
const reset = () => {
  Object.assign(q, { hubNo: '', devOwner: '', types: [], statuses: [], products: [], versions: [], ticketNos: [], createdRange: [], rdResolvedRange: [], releaseRange: [] })
  applied.value = snapshot()
}
const filtered = computed(() => {
  const a = applied.value
  return rows.value.filter((r) => {
    if (a.hubNo && !r.hubNo.includes(a.hubNo)) return false
    if (a.devOwner && !(r.devOwner || '').includes(a.devOwner)) return false
    if (a.types.length && !a.types.includes(r.type)) return false
    if (a.statuses.length && !a.statuses.includes(r.status)) return false
    if (a.products.length && !a.products.includes(r.productTag)) return false
    if (a.versions.length && !a.versions.includes(r.releaseVersion)) return false
    if (a.ticketNos.length && !r.ticketNos.some((n) => a.ticketNos.includes(n))) return false
    if (!_inRange(r.createdAt, a.createdRange)) return false
    if (!_inRange(r.rdResolvedAt, a.rdResolvedRange)) return false
    if (!_inRange(r.releaseAt, a.releaseRange)) return false
    return true
  })
})

// 点击关联工单号 → 打开工单管理列表并筛出这些工单
const goTickets = (nos) => { if (nos && nos.length) router.push({ path: '/tickets', query: { nos: nos.join(',') } }) }
onMounted(load)
</script>

<template>
  <el-card>
    <!-- 筛选：4 个一行 -->
    <el-row :gutter="12" class="filter-row">
      <el-col :span="6"><div class="fi"><span class="lbl">hub编号</span><el-input v-model="q.hubNo" placeholder="hub编号" clearable style="width:100%" @keyup.enter="search" /></div></el-col>
      <el-col :span="6"><div class="fi"><span class="lbl">hub单类型</span><el-select v-model="q.types" multiple collapse-tags collapse-tags-tooltip placeholder="全部" clearable style="width:100%"><el-option v-for="(v,k) in HUB_TYPE" :key="k" :label="v.label" :value="k" /></el-select></div></el-col>
      <el-col :span="6"><div class="fi"><span class="lbl">状态</span><el-select v-model="q.statuses" multiple collapse-tags collapse-tags-tooltip placeholder="全部" clearable style="width:100%"><el-option v-for="s in HUB_STATUS_OPTIONS" :key="s" :label="s" :value="s" /></el-select></div></el-col>
      <el-col :span="6"><div class="fi"><span class="lbl">产研责任人</span><el-input v-model="q.devOwner" placeholder="产研责任人" clearable style="width:100%" @keyup.enter="search" /></div></el-col>
      <el-col :span="6"><div class="fi"><span class="lbl">产品线</span><el-select v-model="q.products" multiple collapse-tags collapse-tags-tooltip placeholder="全部" clearable style="width:100%"><el-option v-for="p in productOptions" :key="p" :label="p" :value="p" /></el-select></div></el-col>
      <el-col :span="6"><div class="fi"><span class="lbl">上线版本号</span><el-select v-model="q.versions" multiple collapse-tags collapse-tags-tooltip placeholder="全部" clearable style="width:100%"><el-option v-for="v in versionOptions" :key="v" :label="v" :value="v" /></el-select></div></el-col>
      <el-col :span="6"><div class="fi"><span class="lbl">关联工单号</span><el-select v-model="q.ticketNos" multiple collapse-tags collapse-tags-tooltip placeholder="全部" clearable filterable style="width:100%"><el-option v-for="t in ticketOptions" :key="t" :label="t" :value="t" /></el-select></div></el-col>
      <el-col :span="6"><div class="fi"><span class="lbl">创建时间</span><el-date-picker v-model="q.createdRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始" end-placeholder="结束" style="width:100%" /></div></el-col>
      <el-col :span="6"><div class="fi"><span class="lbl">研发完成</span><el-date-picker v-model="q.rdResolvedRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始" end-placeholder="结束" style="width:100%" /></div></el-col>
      <el-col :span="6"><div class="fi"><span class="lbl">发版上线</span><el-date-picker v-model="q.releaseRange" type="daterange" value-format="YYYY-MM-DD" start-placeholder="开始" end-placeholder="结束" style="width:100%" /></div></el-col>
      <el-col :span="6"><div class="fi fi-btns"><el-button type="primary" color="#0052d9" @click="search">查询</el-button><el-button @click="reset">重置</el-button></div></el-col>
    </el-row>

    <!-- hub编号固定左列，其余横向滚动 -->
    <el-table :data="filtered" v-loading="loading" stripe border style="width:100%">
      <el-table-column label="hub编号" width="186" fixed="left">
        <template #default="{row}"><el-link type="primary" :underline="false" @click="router.push(`/hubs/${row.id}`)" style="color:#0052d9;font-weight:600">{{ row.hubNo }}</el-link></template>
      </el-table-column>
      <el-table-column label="产研任务说明" min-width="300" show-overflow-tooltip><template #default="{row}">{{ row.problemSummary || '-' }}</template></el-table-column>
      <el-table-column label="产研处理说明" min-width="240" show-overflow-tooltip><template #default="{row}">{{ row.rdNote || '-' }}</template></el-table-column>
      <el-table-column label="hub单类型" width="100"><template #default="{row}"><el-tag size="small" :type="dict(HUB_TYPE,row.type).type">{{ dict(HUB_TYPE,row.type).label }}</el-tag></template></el-table-column>
      <el-table-column label="状态" width="100"><template #default="{row}"><el-tag size="small" :type="dict(HUB_STATUS,row.status).type">{{ dict(HUB_STATUS,row.status).label }}</el-tag></template></el-table-column>
      <el-table-column label="产研责任人" width="110"><template #default="{row}">{{ row.devOwner || '-' }}</template></el-table-column>
      <el-table-column label="产品线" width="110"><template #default="{row}">{{ row.productTag || '-' }}</template></el-table-column>
      <el-table-column label="问题模块" width="120"><template #default="{row}">{{ row.funcModule || '-' }}</template></el-table-column>
      <el-table-column label="创建时间" width="172"><template #default="{row}">{{ row.createdAt || '-' }}</template></el-table-column>
      <el-table-column label="研发完成时间" width="172"><template #default="{row}">{{ row.rdResolvedAt || '-' }}</template></el-table-column>
      <el-table-column label="发版上线时间" width="172"><template #default="{row}">{{ row.releaseAt || '-' }}</template></el-table-column>
      <el-table-column label="关联工单号" min-width="240">
        <template #default="{row}">
          <el-link type="primary" :underline="true" @click="goTickets(row.ticketNos)" style="color:#0052d9">{{ row.ticketNos.join(',') }}</el-link>
        </template>
      </el-table-column>
    </el-table>
    <p class="tip">共 {{ filtered.length }} 条 hub 工单</p>
  </el-card>
</template>

<style scoped>
.filter-row { margin-bottom: 4px; }
.fi { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.fi .lbl { width: 76px; text-align: right; color: #606266; font-size: 13px; flex-shrink: 0; }
.fi-btns { justify-content: flex-start; }
.tip { color: #909399; font-size: 12px; margin-top: 10px; }
</style>
