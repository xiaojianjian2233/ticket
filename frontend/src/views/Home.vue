<script setup>
// 概览：全局概览(公司维度) / 个人概览(自己)。数据源=工单列表(后端 /overview/stats)。
import { computed, onMounted, ref, watch } from 'vue'
import { ticketApi } from '@/api'
import EChart from '@/components/EChart.vue'
import { HUB_STATUS, dict } from '@/dicts'

const mode = ref('global')
const loading = ref(false)
const _empty = () => ({ ticket: { total: 0, processing: 0, closed: 0, thisWeek: 0, lastWeek: 0, closeRate: 0, timelyCloseRate: 0 }, trend: [], closeTrend: [], rd: { total: 0, pending: 0, developing: 0, testing: 0, released: 0 }, metrics: { greenStrategic: 0, overdueUnclosed: 0, soonOverdue: 0, pendingManual: 0, yesterdayNew: 0 }, productModules: [] })
const real = ref({ global: null, personal: null })

const fetchStats = async () => {
  const m = mode.value
  loading.value = true
  try { real.value[m] = await ticketApi.overview({ personal: m === 'personal' }) } catch (e) { real.value[m] = _empty() } finally { loading.value = false }
}
onMounted(fetchStats)
watch(mode, () => { if (!real.value[mode.value]) fetchStats() })

// 生成近 n 天，每天按来源拆分(KSM/智齿/内部提单/外部提单)，总数=四者之和（确定性样本）
// 5 条线（总数 + 四来源），不同颜色
const SERIES_META = [
  { key: 'total', name: '总数', color: '#0052d9' },
  { key: 'ksm', name: 'KSM工单', color: '#36d1a0' },
  { key: 'zhichi', name: '智齿工单', color: '#e6a23c' },
  { key: 'internal', name: '内部提单', color: '#9b59b6' },
  { key: 'external', name: '外部提单', color: '#f56c6c' },
]

const d = computed(() => real.value[mode.value] || _empty())

const wow = computed(() => {
  const t = d.value.ticket
  const diff = t.thisWeek - t.lastWeek
  const pct = t.lastWeek ? Math.round((diff / t.lastWeek) * 1000) / 10 : 0
  return { diff, pct, up: diff >= 0 }
})

const lineOption = computed(() => ({
  color: SERIES_META.map((s) => s.color),
  legend: { top: 0, itemWidth: 14, itemHeight: 8, textStyle: { fontSize: 11 }, data: SERIES_META.map((s) => s.name) },
  tooltip: { trigger: 'axis' },
  grid: { left: 36, right: 18, top: 36, bottom: 48 },
  xAxis: { type: 'category', boundaryGap: false, data: d.value.trend.map((x) => x.date) },
  yAxis: { type: 'value' },
  dataZoom: [
    { type: 'inside', start: 54, end: 100 },          // 默认近14天(30天里最后14天)
    { type: 'slider', start: 54, end: 100, height: 16, bottom: 10 },
  ],
  series: SERIES_META.map((s) => ({
    name: s.name, type: 'line', smooth: true, showSymbol: true, symbolSize: 4,
    data: d.value.trend.map((x) => x[s.key]),
    lineStyle: { width: s.key === 'total' ? 2.5 : 1.5 },
    emphasis: { focus: 'series' },
    // 每条线每个节点都显示数值
    label: { show: true, position: 'top', fontSize: 9, color: s.color },
    z: s.key === 'total' ? 5 : 2,
  })),
}))

// 个人关单走势（单线，默认14天）
const closeTrendOption = computed(() => ({
  tooltip: { trigger: 'axis' },
  grid: { left: 6, right: 16, top: 24, bottom: 48, containLabel: true },   // 自动贴边，左侧不留多余空白
  xAxis: { type: 'category', boundaryGap: false, data: d.value.closeTrend.map((x) => x.date) },
  yAxis: { type: 'value' },
  dataZoom: [
    { type: 'inside', start: 54, end: 100 },
    { type: 'slider', start: 54, end: 100, height: 16, bottom: 10 },
  ],
  series: [{
    name: '关单数', type: 'line', smooth: true, showSymbol: true, symbolSize: 5,
    data: d.value.closeTrend.map((x) => x.closed),
    lineStyle: { color: '#67c23a', width: 2 }, itemStyle: { color: '#67c23a' },
    areaStyle: { color: 'rgba(103,194,58,0.12)' },
    label: { show: true, position: 'top', fontSize: 10, color: '#67c23a' },
  }],
}))

function barOption(items) {
  const data = [...items].reverse()   // echarts category 自底向上，反转让最大在顶部
  return {
    grid: { left: 6, right: 78, top: 8, bottom: 6, containLabel: true },
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: (ps) => `${ps[0].name}<br/>数量 ${ps[0].value} · 责任人 ${ps[0].data.owner}`,
    },
    xAxis: { type: 'value', axisLabel: { fontSize: 10 }, splitLine: { lineStyle: { color: '#f0f2f5' } } },
    yAxis: { type: 'category', data: data.map((x) => x.m), axisLabel: { fontSize: 11, width: 92, overflow: 'truncate' } },
    series: [{
      type: 'bar', barWidth: 13,
      data: data.map((x) => ({ value: x.c, owner: x.owner })),
      itemStyle: { color: '#4d8cff', borderRadius: [0, 4, 4, 0] },
      label: {
        show: true, position: 'right', fontSize: 11, color: '#606266',
        formatter: (p) => `${p.value} · ${p.data.owner}`,
      },
    }],
  }
}
</script>

<template>
  <div>
    <!-- 全局 / 个人 切换 -->
    <div style="margin-bottom:14px">
      <el-radio-group v-model="mode">
        <el-radio-button value="global">全局概览</el-radio-button>
        <el-radio-button value="personal">个人概览</el-radio-button>
      </el-radio-group>
      <span style="margin-left:10px;color:#909399;font-size:12px">{{ mode === 'global' ? '公司维度数据' : '我的数据（处理人=当前登录用户）' }} · 数据源：工单列表</span>
      <span v-if="loading" style="margin-left:8px;color:#c0c4cc;font-size:12px">加载中…</span>
    </div>

    <!-- ========== 全局概览 ========== -->
    <template v-if="mode === 'global'">
    <!-- 容器1：总数 | 副指标(垂直) | 折线趋势 -->
    <el-card class="blk" shadow="never">
      <template #header><b>工单概览</b><span class="sub">本周 vs 上周环比 · 趋势按天（默认近14天，可左右拖动）</span></template>
      <div class="c1">
        <!-- 总数（最左） -->
        <div class="total">
          <div class="t">总工单数</div>
          <div class="big">{{ d.ticket.total }}</div>
        </div>
        <!-- 3 个副指标，垂直分布 -->
        <div class="subs">
          <div class="sub-item"><span class="t">处理中工单</span><span class="v" style="color:#e6a23c">{{ d.ticket.processing }}</span></div>
          <div class="sub-item"><span class="t">已关闭工单</span><span class="v" style="color:#67c23a">{{ d.ticket.closed }}</span></div>
          <div class="sub-item">
            <span class="t">本周工单（环比）</span>
            <span class="v">{{ d.ticket.thisWeek }}
              <span class="wow" :class="wow.up ? 'up' : 'down'">{{ wow.up ? '▲' : '▼' }}{{ Math.abs(wow.pct) }}%</span>
            </span>
          </div>
        </div>
        <!-- 折线趋势（最右） -->
        <div class="trend"><EChart :option="lineOption" height="270px" /></div>
      </div>
    </el-card>

    <!-- 容器2：产研任务统计 -->
    <el-card class="blk" shadow="never">
      <template #header><b>产研任务统计</b></template>
      <el-row :gutter="16">
        <el-col :span="4"><div class="stat"><div class="t">产研总任务数</div><div class="n">{{ d.rd.total }}</div></div></el-col>
        <el-col :span="5"><div class="stat"><div class="t">{{ dict(HUB_STATUS,'pending_follow').label }}</div><div class="n" style="color:#909399">{{ d.rd.pending }}</div></div></el-col>
        <el-col :span="5"><div class="stat"><div class="t">{{ dict(HUB_STATUS,'developing').label }}</div><div class="n" style="color:#0052d9">{{ d.rd.developing }}</div></div></el-col>
        <el-col :span="5"><div class="stat"><div class="t">{{ dict(HUB_STATUS,'testing').label }}</div><div class="n" style="color:#e6a23c">{{ d.rd.testing }}</div></div></el-col>
        <el-col :span="5"><div class="stat"><div class="t">{{ dict(HUB_STATUS,'released').label }}</div><div class="n" style="color:#67c23a">{{ d.rd.released }}</div></div></el-col>
      </el-row>
    </el-card>

    <!-- 容器3：各产品线 问题模块 TOP5（横向条形，每行3个） -->
    <el-card class="blk" shadow="never">
      <template #header><b>各产品线 · 问题模块 TOP5</b><span class="sub">横轴=数量，条形后显示「数量 · 责任人」</span></template>
      <el-row :gutter="16">
        <el-col v-for="p in d.productModules" :key="p.product" :span="8" style="margin-bottom:14px">
          <div class="pm">
            <div class="pm-title">{{ p.product }}</div>
            <EChart :option="barOption(p.items)" height="200px" />
          </div>
        </el-col>
      </el-row>
    </el-card>
    </template>

    <!-- ========== 个人概览 ========== -->
    <template v-else>
      <!-- 容器1：统计小容器 + 关单走势 -->
      <el-card class="blk" shadow="never">
        <template #header><b>个人工单概览</b><span class="sub">处理人 = 当前登录用户 · 关单走势按天（默认近14天，可左右拖动）</span></template>
        <!-- 一行：总数 | 副指标 | 关单走势 -->
        <div class="c1">
          <div class="p-total">
            <div class="t">总工单数</div>
            <div class="big">{{ d.ticket.total }}</div>
            <div class="wow2" :class="wow.up ? 'up' : 'down'">周环比 {{ wow.up ? '▲' : '▼' }}{{ Math.abs(wow.pct) }}%</div>
          </div>
          <div class="p-subs">
            <div class="sub-item"><span class="t">处理中</span><span class="v" style="color:#e6a23c">{{ d.ticket.processing }}</span></div>
            <div class="sub-item"><span class="t">已关闭</span><span class="v" style="color:#67c23a">{{ d.ticket.closed }}</span></div>
            <div class="sub-item"><span class="t">关单率</span><span class="v" style="color:#0052d9">{{ d.ticket.closeRate }}%</span></div>
            <div class="sub-item"><span class="t">及时关单率</span><span class="v" style="color:#0052d9">{{ d.ticket.timelyCloseRate }}%</span></div>
          </div>
          <div class="trend"><EChart :option="closeTrendOption" height="260px" /></div>
        </div>
      </el-card>

      <!-- 容器2：监控指标 -->
      <el-card class="blk" shadow="never">
        <template #header><b>个人工单监控</b></template>
        <div class="metrics">
          <div class="metric"><div class="t">绿色战略客户工单</div><div class="n" style="color:#67c23a">{{ d.metrics.greenStrategic }}</div></div>
          <div class="metric"><div class="t">已超时未关闭</div><div class="n" style="color:#f56c6c">{{ d.metrics.overdueUnclosed }}</div></div>
          <div class="metric"><div class="t">即将超时(≤2h)</div><div class="n" style="color:#e6a23c">{{ d.metrics.soonOverdue }}</div></div>
          <div class="metric"><div class="t">待人工审</div><div class="n" style="color:#0052d9">{{ d.metrics.pendingManual }}</div></div>
          <div class="metric"><div class="t">昨日新增</div><div class="n" style="color:#909399">{{ d.metrics.yesterdayNew }}</div></div>
        </div>
      </el-card>
    </template>
  </div>
</template>

<style scoped>
.blk { margin-bottom: 16px; }
.sub { margin-left: 10px; font-weight: 400; font-size: 12px; color: #909399; }
/* 容器1：总数 | 副指标 | 折线 */
.c1 { display: flex; align-items: stretch; gap: 22px; }
.total { flex: 0 0 150px; display: flex; flex-direction: column; justify-content: center;
         border-right: 1px solid #f0f2f5; }
.total .t { color: #909399; font-size: 13px; }
.total .big { font-size: 46px; font-weight: 700; color: #0052d9; line-height: 1.1; margin-top: 6px; }
.subs { flex: 0 0 220px; display: flex; flex-direction: column; justify-content: center; gap: 16px;
        border-right: 1px solid #f0f2f5; padding-right: 18px; }
.sub-item { display: flex; align-items: baseline; justify-content: space-between; }
.sub-item .t { color: #909399; font-size: 13px; }
.sub-item .v { font-size: 22px; font-weight: 700; color: #1f2937; }
.trend { flex: 1; min-width: 0; }
.stat { padding: 6px 4px; }
.stat .t { color: #909399; font-size: 13px; }
.stat .n { font-size: 28px; font-weight: 700; margin-top: 6px; color: #1f2937; }
.stat .hint { color: #c0c4cc; font-size: 12px; margin-top: 2px; }
.wow { font-size: 13px; font-weight: 600; margin-left: 6px; }
.wow.up { color: #67c23a; }
.wow.down { color: #f56c6c; }
.chart-title { margin: 14px 0 4px; font-size: 13px; color: #606266; }
.pm { border: 1px solid #ebeef5; border-radius: 8px; padding: 8px 4px 4px; }
.pm-title { font-size: 13px; font-weight: 600; color: #1f2937; padding: 0 8px 4px; }
/* 个人概览：容器1 一行三段 */
.p-total { flex: 0 0 150px; display: flex; flex-direction: column; justify-content: center; border-right: 1px solid #f0f2f5; }
.p-total .t { color: #909399; font-size: 13px; }
.p-total .big { font-size: 44px; font-weight: 700; color: #0052d9; line-height: 1.05; margin: 6px 0 4px; }
.wow2 { font-size: 12px; font-weight: 600; }
.wow2.up { color: #67c23a; }
.wow2.down { color: #f56c6c; }
.p-subs { flex: 0 0 230px; display: flex; flex-direction: column; justify-content: center; gap: 14px;
          border-right: 1px solid #f0f2f5; padding-right: 18px; }
.metrics { display: flex; gap: 14px; }
.metric { flex: 1; border: 1px solid #ebeef5; border-radius: 8px; padding: 16px 12px; text-align: center; }
.metric .t { color: #909399; font-size: 13px; }
.metric .n { font-size: 30px; font-weight: 700; margin-top: 8px; }
</style>
