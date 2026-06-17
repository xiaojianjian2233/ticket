<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ticketApi, moduleOwnerApi } from '@/api'
import { useAuth } from '@/stores/auth'
import { STATUS, SOURCE, dict } from '@/dicts'
import { ElMessage, ElMessageBox } from 'element-plus'

const route = useRoute()
const router = useRouter()
const auth = useAuth()
const t = ref(null)
const loading = ref(false)
const selectedIdx = ref(0)

// —— 打标编辑：产品线/问题模块/责任田负责人（数据源=模块责任人） ——
const productLines = ref([])             // 启用产品线（去重）
const modulesByProduct = ref({})         // {产品线: [启用问题模块]}
const ownerMap = ref({})                 // {`产品线|||问题模块`: 责任人}
const TICKET_TYPE_OPTIONS = ['需求', 'bug', '应用技术类', '其他']
const tagForm = ref({ product: '', module: '', owner: '', ticketType: '' })
const isFinal = () => ['done', 'closed'].includes(t.value?.status)
const tagEditable = computed(() => auth.can('handler') && !isFinal())
const curModules = computed(() => modulesByProduct.value[tagForm.value.product] || [])

const loadOptions = async () => {
  const res = await moduleOwnerApi.options()
  const rows = res.items || []
  const ps = []; const mbp = {}; const om = {}
  rows.forEach((r) => {
    if (!ps.includes(r.productTag)) ps.push(r.productTag)
    ;(mbp[r.productTag] = mbp[r.productTag] || []).push(r.funcModule)
    om[`${r.productTag}|||${r.funcModule}`] = r.devOwner || ''
  })
  productLines.value = ps; modulesByProduct.value = mbp; ownerMap.value = om
}
// 改产品线 → 清空问题模块与责任人（联动）
const onProductChange = () => { tagForm.value.module = ''; tagForm.value.owner = '' }
// 改问题模块 → 自动带出责任田负责人
const onModuleChange = () => { tagForm.value.owner = ownerMap.value[`${tagForm.value.product}|||${tagForm.value.module}`] || '' }
// 点击操作按钮时落库：产品线/问题模块/责任田负责人/工单类型 有变更才更新
const persistTag = async () => {
  if (!tagEditable.value) return
  const f = tagForm.value
  if (!f.product && !f.module && !f.ticketType) return
  const unchanged = f.product === (t.value.productTag || '') && f.module === (t.value.funcModule || '')
    && f.owner === (t.value.devOwner || '') && f.ticketType === (t.value.ticketType || '')
  if (unchanged) return
  await ticketApi.tag(route.params.id, {
    product_tag: f.product || null, func_module: f.module || null,
    dev_owner: f.owner || null, ticket_type: f.ticketType || null,
  })
}

const load = async () => {
  loading.value = true
  try {
    t.value = await ticketApi.detail(route.params.id)
    selectedIdx.value = 0
    tagForm.value = { product: t.value.productTag || '', module: t.value.funcModule || '',
                      owner: t.value.devOwner || '', ticketType: t.value.ticketType || '' }
  } finally { loading.value = false }
}
const done = (msg) => { ElMessage.success(msg); load() }

// —— 操作 ——
// 确认答复并关单：处理说明为空 → 提示不可关单；不为空 → 回写并置为处理完成
const confirmClose = async () => {
  if (isFinal()) return
  const f = tagForm.value
  const miss = []
  if (!f.product || f.product === '无法判断') miss.push('产品线')
  if (!f.module) miss.push('问题模块')
  if (!f.owner || f.owner === '待人工分配') miss.push('责任田负责人')
  if (!f.ticketType) miss.push('工单类型')
  if (!(t.value.finalReply || '').trim()) miss.push('处理说明')
  if (miss.length) {
    return ElMessageBox.alert(`以下内容不能为空，无法关单：${miss.join('、')}`, '提示', { type: 'warning' })
  }
  await persistTag()
  await ticketApi.close(route.params.id, { reply_content: t.value.finalReply })
  done('已确认答复并关单')
}
const supply = async () => {
  const { value } = await ElMessageBox.prompt('需要客户补充的内容', '补充资料', { inputType: 'textarea' })
  await persistTag()
  await ticketApi.handle(route.params.id, { action: 'supply', reply_content: value })
  done('已发补料话术')
}
const toRd = async () => {
  await ElMessageBox.confirm('转研发？将创建/关联 hub 工单(责任人李志坚)。', '转研发')
  await persistTag()
  await ticketApi.handle(route.params.id, { action: 'to_rd' })
  done('已转研发')
}
const returnTicket = async () => {
  const { value } = await ElMessageBox.prompt('退回原因', '退回工单', { inputType: 'textarea', inputValue: '不接管' })
  await persistTag()
  await ticketApi.handle(route.params.id, { action: 'return', reply_content: value })
  done('已退回工单')
}

// —— 历史节点：优先用后端 timeline，缺失则按现有字段兜底；倒序（当前在最上）——
const sourceLabel = () => dict(SOURCE, t.value?.source).label
const buildFallback = () => {
  const o = t.value
  if (!o) return []
  const n = []
  n.push({ op: '创建工单', operator: sourceLabel(), time: o.createdAt, note: o.description || o.problemContent || '', attachments: o.attachments || [] })
  if (o.routeAction) n.push({ op: '流转判定', operator: 'AI', time: o.slaStartAt || o.createdAt, note: o.routeReason || o.routeAction, attachments: [] })
  ;(o.tags || []).forEach((tg) => n.push({ op: '智能打标', operator: tg.tagSource || '系统', time: tg.createdAt, note: `产品线：${tg.productTag || '-'}　模块：${tg.funcModule || '-'}　责任人：${tg.devOwner || '-'}`, attachments: [] }))
  if (o.finalReply) n.push({ op: '答复', operator: o.dispatchAssignee || '系统', time: o.resolvedAt, note: o.finalReply, attachments: [] })
  if (o.closedAt) n.push({ op: '关单', operator: '系统', time: o.closedAt, note: '工单已关闭', attachments: [] })
  return n
}
const timeline = computed(() => {
  const arr = Array.isArray(t.value?.timeline) && t.value.timeline.length ? [...t.value.timeline] : buildFallback()
  arr.sort((a, b) => new Date(b.time || 0) - new Date(a.time || 0))
  return arr
})
const curNode = computed(() => timeline.value[selectedIdx.value] || timeline.value[0] || null)
watch(timeline, () => { if (selectedIdx.value >= timeline.value.length) selectedIdx.value = 0 })

const fmt = (s) => {
  if (!s) return '-'
  const d = new Date(s)
  return isNaN(d) ? s : d.toLocaleString('zh-CN', { hour12: false })
}
const isImg = (a) => a.isImage || /\.(png|jpe?g|gif|webp|bmp)$/i.test(a.name || a.url || '')

onMounted(async () => { await load(); try { await loadOptions() } catch (e) { /* 参考数据失败不阻断详情 */ } })
</script>

<template>
  <div v-loading="loading" v-if="t" class="detail">
    <!-- ① 粘性操作栏：精简按钮、加大高度、整体右对齐 -->
    <div class="action-bar">
      <template v-if="auth.can('handler')">
        <el-button size="default" type="primary" color="#0052d9" :disabled="isFinal()" @click="confirmClose">确认答复并关单</el-button>
        <el-button size="default" :disabled="isFinal()" @click="supply">补充资料</el-button>
        <el-button size="default" :disabled="isFinal()" @click="toRd">转研发</el-button>
        <el-button size="default" :disabled="isFinal()" @click="returnTicket">退回工单</el-button>
      </template>
      <el-button size="default" @click="router.back()">返回</el-button>
    </div>

    <!-- ② 标题 + 副标题（来源工单编号）+ 标签位 -->
    <div class="title-block">
      <h2 class="title">{{ t.ticketNo }}</h2>
      <div class="subtitle">
        <span class="sub-no">来源单号：{{ t.sourceBillNo || '-' }}</span>
        <span class="tag-slot">
          <el-tag :type="dict(STATUS, t.status).type" size="small">{{ dict(STATUS, t.status).label }}</el-tag>
          <el-tag :type="dict(SOURCE, t.source).type" size="small">{{ dict(SOURCE, t.source).label }}</el-tag>
          <el-tag v-if="t.serviceLevel" type="success" size="small">{{ t.serviceLevel }}</el-tag>
          <el-tag v-if="t.slaState==='breached'" type="danger" size="small">SLA 超时</el-tag>
          <el-tag v-else type="success" size="small">SLA 正常</el-tag>
          <el-tag v-if="t.returnCount>0" type="danger" size="small">退回×{{ t.returnCount }}</el-tag>
        </span>
      </div>
    </div>

    <!-- ③ 容器：工单基本信息 -->
    <el-card class="block" shadow="never">
      <template #header><b>工单基本信息</b></template>
      <div class="contact-row">
        <div class="cell"><span class="lbl">联系人姓名</span><span>{{ t.customerContact || '-' }}</span></div>
        <div class="cell"><span class="lbl">联系人电话</span><span>{{ t.customerMobile || '-' }}</span></div>
        <div class="cell"><span class="lbl">联系人邮箱</span><span>{{ t.customerEmail || '-' }}</span></div>
      </div>
      <div class="field">
        <div class="lbl">问题内容</div>
        <div class="content-text">{{ t.description || t.problemContent || '（无）' }}</div>
      </div>
      <div class="field">
        <div class="lbl">反馈问题附件</div>
        <div class="atts" v-if="(t.attachments||[]).length">
          <a v-for="(a,i) in t.attachments" :key="i" class="att" :href="a.url || 'javascript:;'" target="_blank">
            <el-image v-if="isImg(a) && a.url" :src="a.url" fit="cover" class="att-img" :preview-src-list="[a.url]" />
            <span v-else class="att-file"><el-icon><Document /></el-icon> {{ a.name }}</span>
          </a>
        </div>
        <div v-else class="muted">无</div>
      </div>
    </el-card>

    <!-- ④ 容器：工单处理说明（左节点 / 右内容；当前节点橙色闪烁、可编辑；历史只读）-->
    <el-card class="block" shadow="never">
      <template #header><b>工单处理说明</b><span class="node-count">历史节点数 {{ timeline.length }}</span></template>
      <div class="handle-wrap">
        <!-- 左：历史节点（倒序，当前在最上）-->
        <div class="nodes">
          <div v-for="(n,i) in timeline" :key="i" class="node" :class="{ active: i===selectedIdx }" @click="selectedIdx=i">
            <span class="dot" :class="i===0 ? 'dot-orange blink' : 'dot-green'"></span>
            <div class="node-main">
              <div class="node-op">{{ n.op }}</div>
              <div class="node-meta">{{ n.operator || '系统' }} · {{ fmt(n.time) }}</div>
            </div>
          </div>
          <div v-if="!timeline.length" class="muted" style="padding:12px">暂无处理记录</div>
        </div>
        <!-- 右：打标(产品线/问题模块/责任田负责人) + 处理说明 + 处理附件 -->
        <div class="node-detail">
          <!-- 打标编辑行：产品线/问题模块 可改(联动)，责任田负责人自动带出；落库在点击操作按钮时 -->
          <div class="tag-row">
            <div class="tag-cell">
              <div class="lbl">产品线</div>
              <el-select v-if="tagEditable" v-model="tagForm.product" filterable placeholder="选择产品线"
                         @change="onProductChange" style="width:100%">
                <el-option v-for="p in productLines" :key="p" :label="p" :value="p" />
              </el-select>
              <div v-else class="content-text">{{ tagForm.product || '-' }}</div>
            </div>
            <div class="tag-cell">
              <div class="lbl">问题模块</div>
              <el-select v-if="tagEditable" v-model="tagForm.module" filterable placeholder="请先选择产品线"
                         :disabled="!tagForm.product" @change="onModuleChange" style="width:100%">
                <el-option v-for="m in curModules" :key="m" :label="m" :value="m" />
              </el-select>
              <div v-else class="content-text">{{ tagForm.module || '-' }}</div>
            </div>
            <div class="tag-cell">
              <div class="lbl">责任田负责人 <span class="auto-hint">（自动带出）</span></div>
              <div class="content-text owner-val">{{ tagForm.owner || '-' }}</div>
            </div>
            <div class="tag-cell">
              <div class="lbl">工单类型</div>
              <el-select v-if="tagEditable" v-model="tagForm.ticketType" placeholder="请选择工单类型" clearable style="width:100%">
                <el-option v-for="tp in TICKET_TYPE_OPTIONS" :key="tp" :label="tp" :value="tp" />
              </el-select>
              <div v-else class="content-text">{{ tagForm.ticketType || '-' }}</div>
            </div>
          </div>
          <template v-if="curNode">
            <div class="field">
              <div class="lbl">处理说明</div>
              <el-input v-if="selectedIdx===0 && !isFinal()" class="reply-ta" type="textarea" :rows="6" v-model="t.finalReply" placeholder="请录入工单的处理答复内容" />
              <div v-else class="content-text">{{ (selectedIdx===0 ? (t.finalReply || curNode.note) : curNode.note) || '（无）' }}</div>
            </div>
            <div class="field">
              <div class="lbl">处理附件</div>
              <div class="atts" v-if="(curNode.attachments||[]).length">
                <a v-for="(a,i) in curNode.attachments" :key="i" class="att" :href="a.url || 'javascript:;'" target="_blank">
                  <el-image v-if="isImg(a) && a.url" :src="a.url" fit="cover" class="att-img" :preview-src-list="[a.url]" />
                  <span v-else class="att-file"><el-icon><Document /></el-icon> {{ a.name }}</span>
                </a>
              </div>
              <div v-else class="muted">无</div>
            </div>
          </template>
          <div v-else class="muted" style="padding:12px">请选择左侧节点查看处理内容</div>
        </div>
      </div>
    </el-card>

    <el-card v-if="t.rdHubId" class="block" shadow="never"><template #header><b>研发进展</b></template>
      <el-descriptions :column="2" border>
        <el-descriptions-item label="研发状态">{{ t.rdStatus || '-' }}</el-descriptions-item>
        <el-descriptions-item label="处理人">{{ t.rdHandler || '-' }}</el-descriptions-item>
        <el-descriptions-item label="说明" :span="2">{{ t.rdStatusNote || '-' }}</el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<style scoped>
.detail { position: relative; }
/* 操作栏容器：白色卡片、右对齐、粘性吸顶 */
.action-bar { position: sticky; top: -14px; z-index: 20; display: flex; flex-wrap: wrap; gap: 10px;
              justify-content: flex-end; background: #fff; border: 1px solid #ebeef5; border-radius: 8px;
              padding: 10px 14px; margin: -6px 0 14px; box-shadow: 0 1px 4px rgba(0,0,0,.04); }

/* 标题容器：白色卡片 */
.title-block { background: #fff; border: 1px solid #ebeef5; border-radius: 8px; padding: 14px 16px; margin-bottom: 16px; }
.title { margin: 0; font-size: 20px; font-weight: 700; color: #1f2937; }
.subtitle { display: flex; align-items: center; flex-wrap: wrap; gap: 12px; margin-top: 6px; }
.sub-no { font-size: 13px; color: #909399; }
.tag-slot { display: flex; flex-wrap: wrap; gap: 6px; }

/* 通用容器 */
.block { margin-bottom: 16px; }
.muted { color: #909399; }
.field { margin-top: 14px; }
.lbl { color: #909399; font-size: 13px; margin-bottom: 4px; }
.content-text { white-space: pre-wrap; line-height: 1.7; color: #1f2937; }

/* 联系人一行：3 字段均衡分布、与容器左右对齐、左右各留 10px */
.contact-row { display: flex; padding: 0 10px; }
.contact-row .cell { flex: 1; display: flex; gap: 8px; align-items: center; }
.contact-row .cell:nth-child(2) { justify-content: center; }
.contact-row .cell:nth-child(3) { justify-content: flex-end; }
.contact-row .lbl { margin: 0; }

/* 附件 */
.atts { display: flex; flex-wrap: wrap; gap: 10px; }
.att { display: inline-flex; }
.att-img { width: 84px; height: 84px; border-radius: 6px; border: 1px solid #ebeef5; }
.att-file { display: inline-flex; align-items: center; gap: 4px; padding: 6px 10px; background: #f4f6fa; border-radius: 6px; color: #0052d9; font-size: 13px; }

/* 处理说明 左右结构：仅左侧节点区独立上下滚动，右侧内容随页面正常显示 */
.handle-wrap { display: flex; gap: 16px; align-items: flex-start; }
.nodes { width: 300px; flex-shrink: 0; border-right: 1px solid #ebeef5; padding-right: 8px; max-height: 460px; overflow-y: auto; }
.node-count { margin-left: 10px; font-weight: 400; font-size: 12px; color: #909399; }
.node { display: flex; gap: 10px; padding: 10px 8px; border-radius: 6px; cursor: pointer; }
.node:hover { background: #f5f8ff; }
.node.active { background: #e9f1ff; }
.node-main { min-width: 0; }
/* 节点标题加小框 */
.node-op { display: inline-block; font-weight: 600; color: #1f2937; font-size: 13px;
           border: 1px solid #dcdfe6; border-radius: 4px; padding: 1px 8px; background: #f5f7fa; }
.node.active .node-op { border-color: #0052d9; color: #0052d9; background: #eaf1ff; }
.node-meta { color: #909399; font-size: 12px; margin-top: 2px; }
.dot { width: 11px; height: 11px; border-radius: 50%; margin-top: 5px; flex-shrink: 0; }
.dot-green { background: #36d1a0; }              /* 已处理历史节点 */
.dot-orange { background: #ff9900; }             /* 当前处理节点（橙色填充）*/
.dot.blink { animation: blink 1s ease-in-out infinite; }
@keyframes blink {
  0%, 100% { box-shadow: 0 0 0 0 rgba(255,153,0,.6); opacity: 1; }
  50% { box-shadow: 0 0 0 6px rgba(255,153,0,0); opacity: .55; }
}
.node-detail { flex: 1; min-width: 0; }
/* 打标编辑行：产品线/问题模块/责任田负责人 横向均分 */
.tag-row { display: flex; gap: 16px; margin-bottom: 14px; padding-bottom: 14px; border-bottom: 1px dashed #ebeef5; }
.tag-cell { flex: 1; min-width: 0; }
.tag-cell .lbl { margin-bottom: 6px; }
.auto-hint { color: #c0c4cc; font-size: 12px; }
.owner-val { font-weight: 600; color: #0052d9; padding-top: 7px; }
/* 处理说明录入框：在 rows=6 基础上整体加高 30px */
.reply-ta :deep(.el-textarea__inner) { min-height: calc(6em * 1.5 + 30px) !important; }
</style>
