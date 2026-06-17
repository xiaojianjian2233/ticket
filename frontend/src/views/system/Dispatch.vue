<script setup>
// 派单规则管理：规则持久化(后端 t_dispatch_rule) + 4列配置弹窗。
// 数据源：产品线/模块=模块责任人、SLA=服务等级、处理人=启用用户。约束：同(产品线,模块)在同类型规则中唯一。
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { dispatchApi, moduleOwnerApi, userApi, ticketApi } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const productLines = ref([])
const modulesByProduct = ref({})
const slaOptions = ref([])
const activeUsers = ref([])
const SOURCE_OPTIONS = ['全部来源（不限）', 'KSM', '智齿', '内部提单', '外部提单']

const RULES = ref([])
const kw = ref('')
const list = computed(() => RULES.value.filter((r) => !kw.value
  || `${r.name}${(r.products || []).join()}${(r.sources || []).join()}`.toLowerCase().includes(kw.value.toLowerCase())))
const overflowRules = computed(() => RULES.value.filter((r) => r.ruleType === '溢出规则'))

const loadRules = async () => { try { const d = await dispatchApi.rules(); RULES.value = d.items || [] } catch (e) { /* */ } }
onMounted(async () => {
  try {
    const mo = await moduleOwnerApi.list({})
    const byp = {}
    ;(mo.items || []).filter((r) => r.isActive).forEach((r) => { (byp[r.productTag] ||= new Set()).add(r.funcModule) })
    productLines.value = Object.keys(byp)
    modulesByProduct.value = Object.fromEntries(Object.entries(byp).map(([k, v]) => [k, [...v]]))
  } catch (e) { /* */ }
  try { const sl = await ticketApi.serviceLevels(); slaOptions.value = (sl || []).map((x) => x.name) } catch (e) { /* */ }
  try { const u = await userApi.list({ page_no: 1, page_size: 500 }); activeUsers.value = (u.items || []).filter((x) => x.isActive).map((x) => x.name) } catch (e) { /* */ }
  await loadRules()
})

// 展示用：数组 → 文本
const srcText = (r) => ((r.sources || []).includes('全部来源（不限）') ? '全部来源（不限）' : ((r.sources || []).join('、') || '-'))
const asgText = (r) => ((r.assignees || []).map((a) => `${a.name}:${a.value}`).join('，') || '-')

// —— 弹窗 ——
const dialog = ref(false)
const editingId = ref(null)
const takenByProduct = ref({})   // 同类型已占用 {产品线:[模块]}
const blankForm = () => ({ name: '', type: '正式规则', sla: [], sources: ['全部来源（不限）'], products: [], modules: [],
  mode: '按数量', assignees: [{ name: '', value: 1 }], fallback: '', overflowRuleId: '' })
const form = reactive(blankForm())

const fetchTaken = async () => {
  try { takenByProduct.value = await dispatchApi.rulesTaken({ rule_type: form.type, exclude_id: editingId.value || undefined }) } catch (e) { takenByProduct.value = {} }
}
// 当前查看模块的产品线（点击产品名切换；勾选框才是选中/取消）
const activeProduct = ref('')
const toggleProduct = (p, checked) => {
  if (checked) {
    if (!form.products.includes(p)) form.products.push(p)
    if (!activeProduct.value) activeProduct.value = p
  } else {
    form.products = form.products.filter((x) => x !== p)
    if (activeProduct.value === p) activeProduct.value = form.products[0] || ''
  }
}
// 仅展示「当前查看产品线」的模块，剔除同类型已占用
const availableModules = computed(() => {
  const p = activeProduct.value
  if (!p) return []
  const taken = new Set(takenByProduct.value[p] || [])
  return (modulesByProduct.value[p] || []).filter((m) => !taken.has(m))
})
// 产品线变化：剔除不属于任一已选产品线的模块；校正当前查看产品线
watch(() => form.products.slice(), () => {
  const allowed = new Set()
  form.products.forEach((p) => (modulesByProduct.value[p] || []).forEach((m) => allowed.add(m)))
  form.modules = form.modules.filter((m) => allowed.has(m))
  if (activeProduct.value && !form.products.includes(activeProduct.value)) activeProduct.value = form.products[0] || activeProduct.value
})
// 模块模糊搜索（仅影响展示）
const moduleKw = ref('')
const filteredModules = computed(() => {
  const k = moduleKw.value.trim().toLowerCase()
  return k ? availableModules.value.filter((m) => m.toLowerCase().includes(k)) : availableModules.value
})
// 卡片展示：值截断到 10 字符
const clip = (s, n = 10) => { s = s || ''; return s.length > n ? `${s.slice(0, n)}…` : s }
watch(() => form.type, fetchTaken)   // 切换正式/溢出 → 重新取占用并重算可选模块

const allSla = computed({
  get: () => slaOptions.value.length > 0 && form.sla.length === slaOptions.value.length,
  set: (v) => { form.sla = v ? [...slaOptions.value] : [] },
})
const allProducts = computed({
  get: () => productLines.value.length > 0 && form.products.length === productLines.value.length,
  set: (v) => { form.products = v ? [...productLines.value] : [] },
})
const allModules = computed({
  get: () => availableModules.value.length > 0 && availableModules.value.every((m) => form.modules.includes(m)),
  set: (v) => {
    const cur = new Set(form.modules)
    availableModules.value.forEach((m) => (v ? cur.add(m) : cur.delete(m)))
    form.modules = [...cur]
  },
})

const openAdd = async () => {
  editingId.value = null
  moduleKw.value = ''
  Object.assign(form, blankForm())
  if (productLines.value.length) form.products = [productLines.value[0]]
  activeProduct.value = form.products[0] || ''
  await fetchTaken()
  dialog.value = true
}
const openEdit = async (r) => {
  editingId.value = r.id
  moduleKw.value = ''
  Object.assign(form, {
    name: r.name, type: r.ruleType, sla: [...(r.sla || [])], sources: [...(r.sources || ['全部来源（不限）'])],
    products: [...(r.products || [])], modules: [...(r.modules || [])], mode: r.dispatchMode || '按数量',
    assignees: (r.assignees && r.assignees.length) ? JSON.parse(JSON.stringify(r.assignees)) : [{ name: '', value: 1 }],
    fallback: r.fallback || '', overflowRuleId: r.overflowRuleId || '',
  })
  activeProduct.value = form.products[0] || productLines.value[0] || ''
  await fetchTaken()
  dialog.value = true
}
const addAssignee = () => form.assignees.push({ name: '', value: 1 })
const save = async () => {
  if (!form.name) return ElMessage.warning('请填写规则名称')
  const body = {
    name: form.name, rule_type: form.type, is_active: true,
    sla: form.sla, sources: form.sources, products: form.products, modules: form.modules,
    dispatch_mode: form.mode, assignees: form.assignees.filter((a) => a.name),
    fallback: form.fallback || null, overflow_rule_id: form.type === '正式规则' ? (form.overflowRuleId || null) : null,
  }
  try {
    if (editingId.value) await dispatchApi.updateRule(editingId.value, body)
    else await dispatchApi.createRule(body)
    dialog.value = false; ElMessage.success('已保存'); loadRules()
  } catch (e) { /* 冲突等错误由拦截器提示 */ }
}
const ruleBody = (r) => ({ name: r.name, rule_type: r.ruleType, is_active: r.isActive, sla: r.sla, sources: r.sources,
  products: r.products, modules: r.modules, dispatch_mode: r.dispatchMode, assignees: r.assignees, fallback: r.fallback, overflow_rule_id: r.overflowRuleId })
const toggle = async (r) => { await dispatchApi.updateRule(r.id, { ...ruleBody(r), is_active: !r.isActive }); loadRules() }
const remove = async (r) => {
  await ElMessageBox.confirm(`确认删除规则「${r.name}」？`, '删除派单规则', { type: 'warning' })
  await dispatchApi.deleteRule(r.id); ElMessage.success('已删除'); loadRules()
}
</script>

<template>
  <div>
    <div class="topbar">
      <el-input v-model="kw" placeholder="搜索规则名称、流转产品、工单来源" clearable style="width:320px">
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
      <el-button type="primary" color="#0052d9" @click="openAdd"><el-icon><Plus /></el-icon> 新增派单规则</el-button>
    </div>

    <el-row :gutter="16">
      <el-col v-for="r in list" :key="r.id" :span="12" style="margin-bottom:16px">
        <div class="rule">
          <div class="rule-hd">
            <div class="hd-left">
              <span class="code">{{ r.code }}</span>
              <span class="name">{{ r.name }}</span>
              <el-tag size="small" :type="r.ruleType === '正式规则' ? 'success' : 'danger'" effect="light">{{ r.ruleType }}</el-tag>
            </div>
            <el-tag size="small" :type="r.isActive ? 'success' : 'info'" effect="light" style="cursor:pointer" @click="toggle(r)">{{ r.isActive ? '已启用' : '已停用' }}</el-tag>
          </div>
          <div class="rule-bd">
            <div class="grid2 line">
              <div class="f"><div class="fl">触发服务等级 (SLA)</div>
                <el-tooltip placement="top" effect="light" popper-class="rule-tip" :content="(r.sla || []).join('、') || '-'" :disabled="((r.sla || []).join('、')).length <= 10 && (r.sla || []).length < 2">
                  <div class="fv multi"><span class="mtext">{{ clip((r.sla || []).join('、')) || '-' }}</span><span v-if="(r.sla || []).length > 1" class="mcnt">{{ (r.sla || []).length }}项</span></div>
                </el-tooltip>
              </div>
              <div class="f"><div class="fl">工单来源</div>
                <el-tooltip placement="top" effect="light" popper-class="rule-tip" :content="srcText(r)" :disabled="srcText(r).length <= 10">
                  <div class="fv mtext">{{ clip(srcText(r)) }}</div>
                </el-tooltip>
              </div>
              <div class="f"><div class="fl">产品线</div>
                <el-tooltip placement="top" effect="light" popper-class="rule-tip" :content="(r.products || []).join('、') || '-'" :disabled="((r.products || []).join('、')).length <= 10 && (r.products || []).length < 2">
                  <div class="fv multi"><span class="mtext">{{ clip((r.products || []).join('、')) || '-' }}</span><span v-if="(r.products || []).length > 1" class="mcnt">{{ (r.products || []).length }}项</span></div>
                </el-tooltip>
              </div>
              <div class="f"><div class="fl">问题模块</div>
                <el-tooltip placement="top" effect="light" popper-class="rule-tip" :content="(r.modules || []).join('、') || '-'" :disabled="((r.modules || []).join('、')).length <= 10 && (r.modules || []).length < 2">
                  <div class="fv multi"><span class="mtext">{{ clip((r.modules || []).join('、')) || '-' }}</span><span v-if="(r.modules || []).length > 1" class="mcnt">{{ (r.modules || []).length }}项</span></div>
                </el-tooltip>
              </div>
            </div>
            <div class="f"><div class="fl-row"><span class="fl">派单方式</span>
              <el-tag v-if="r.dispatchMode === '按数量'" size="small" type="primary" effect="light">按数量</el-tag>
              <el-tag v-else size="small" effect="light" style="color:#9b59b6;background:#f4ecfb;border-color:#e3d4f5">按比例</el-tag>
            </div></div>
            <div class="f"><div class="fl">指定处理人</div><div class="fv">{{ asgText(r) }}</div></div>
            <div class="f fb-row"><span class="fl">兜底指派人</span><span class="fb"><el-icon><User /></el-icon> {{ r.fallback || '-' }}</span></div>
          </div>
          <div class="rule-ft">
            <el-button size="small" plain @click="openEdit(r)"><el-icon><Edit /></el-icon> 编辑</el-button>
            <el-button size="small" plain @click="remove(r)"><el-icon><Delete /></el-icon> 删除</el-button>
          </div>
        </div>
      </el-col>
      <el-col v-if="!list.length" :span="24"><el-empty description="暂无派单规则，点右上角「新增派单规则」" /></el-col>
    </el-row>

    <!-- 4 列配置弹窗 -->
    <el-dialog v-model="dialog" :title="editingId ? '编辑派单规则配置' : '新增派单规则配置'" width="92%" top="4vh" class="disp-dlg">
      <div class="cfg-wrap">
      <div class="cfg">
        <div class="col">
          <div class="col-hd">基本属性与匹配条件</div>
          <div class="lbl">规则名称 <span class="req">*</span></div>
          <el-input v-model="form.name" placeholder="请输入规则名称..." />
          <div class="lbl mt">规则类型</div>
          <el-select v-model="form.type" style="width:100%">
            <el-option label="正式规则" value="正式规则" /><el-option label="溢出规则" value="溢出规则" />
          </el-select>
          <div class="lbl mt between">配置触发服务等级 (SLA) - 可多选 <el-checkbox v-model="allSla">一键全选</el-checkbox></div>
          <el-checkbox-group v-model="form.sla" class="chk-col">
            <el-checkbox v-for="s in slaOptions" :key="s" :value="s" :label="s" />
          </el-checkbox-group>
          <div class="lbl mt">配置工单来源 - 可多选</div>
          <el-checkbox-group v-model="form.sources" class="chk-2col">
            <el-checkbox v-for="s in SOURCE_OPTIONS" :key="s" :value="s" :label="s" />
          </el-checkbox-group>
        </div>

        <div class="col">
          <div class="col-hd between">所属产品线配置 <el-checkbox v-model="allProducts">一键全选</el-checkbox></div>
          <div class="lbl">勾选=选中本规则；点击名称=查看该产品线的问题模块</div>
          <div class="chk-scroll">
            <div v-for="p in productLines" :key="p" class="prod-row" :class="{ active: activeProduct === p }">
              <el-checkbox :model-value="form.products.includes(p)" @change="(v) => toggleProduct(p, v)" />
              <span class="prod-name" :title="p" @click="activeProduct = p">{{ p }}</span>
            </div>
          </div>
          <div class="cnt">共 {{ productLines.length }} 个产品线，已选 {{ form.products.length }} 个</div>
        </div>

        <div class="col">
          <div class="col-hd between">问题模块配置 <el-checkbox v-model="allModules" :disabled="!availableModules.length">一键全选</el-checkbox></div>
          <div class="lbl">当前产品线：<b style="color:#0052d9">{{ activeProduct || '— 请点击左侧产品线名称 —' }}</b></div>
          <el-input v-model="moduleKw" placeholder="搜索模块（模糊查询）" clearable size="small" style="margin-bottom:8px">
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
          <div class="chk-scroll">
            <el-checkbox-group v-model="form.modules" class="chk-col">
              <el-checkbox v-for="m in filteredModules" :key="m" :value="m" :label="m" />
            </el-checkbox-group>
            <div v-if="!availableModules.length" class="muted">无可选模块（请先勾选产品线，或该产品模块已被同类型规则占用）</div>
            <div v-else-if="!filteredModules.length" class="muted">无匹配「{{ moduleKw }}」的模块</div>
          </div>
          <div class="cnt">共 {{ availableModules.length }} 个可选模块，已选 {{ form.modules.length }} 个</div>
        </div>

        <div class="col">
          <div class="col-hd">分流派发规则与兜底策略</div>
          <div v-if="form.type === '正式规则'" class="overflow-box">
            <div class="lbl">溢出规则方案（单选）</div>
            <el-select v-model="form.overflowRuleId" placeholder="-- 无 (不配置溢出方案) --" clearable style="width:100%">
              <el-option v-for="r in overflowRules" :key="r.id" :label="`${r.code} ${r.name}`" :value="r.id" />
            </el-select>
            <div class="tip">提示：当本规则处理人额度满负荷时，将按此溢出规则方案进行分派。仅显示已启用的溢出规则。</div>
          </div>
          <div class="lbl mt">设置派单方式
            <el-radio-group v-model="form.mode" style="margin-left:12px">
              <el-radio value="按数量">按数量</el-radio><el-radio value="按比例">按比例</el-radio>
            </el-radio-group>
          </div>
          <div class="lbl mt between">配置指定处理人分配规则
            <el-button link type="primary" @click="addAssignee">+ 添加处理人</el-button>
          </div>
          <div v-for="(a, i) in form.assignees" :key="i" class="assignee">
            <el-select v-model="a.name" placeholder="处理人" filterable style="flex:1">
              <el-option v-for="u in activeUsers" :key="u" :label="u" :value="u" />
            </el-select>
            <el-input-number v-model="a.value" :min="1" :controls="false" style="width:64px" />
            <span class="unit">{{ form.mode === '按数量' ? '个' : '份' }}</span>
            <el-button link type="danger" :disabled="form.assignees.length <= 1" @click="form.assignees.splice(i, 1)"><el-icon><Delete /></el-icon></el-button>
          </div>
          <div class="lbl mt">配置兜底指派人（处理额度超限后承接）</div>
          <el-select v-model="form.fallback" placeholder="选择兜底指派人" filterable clearable style="width:100%">
            <el-option v-for="u in activeUsers" :key="u" :label="u" :value="u" />
          </el-select>
        </div>
      </div>
      </div>
      <template #footer><el-button @click="dialog = false">取消</el-button><el-button type="primary" color="#0052d9" @click="save">保存配置</el-button></template>
    </el-dialog>
  </div>
</template>

<style scoped>
.topbar { display: flex; align-items: center; justify-content: space-between; background: #fff; border: 1px solid #ebeef5; border-radius: 8px; padding: 12px 14px; margin-bottom: 16px; }
.rule { background: #fff; border: 1px solid #ebeef5; border-radius: 10px; }
.rule-hd { display: flex; align-items: center; justify-content: space-between; padding: 14px 16px; }
.hd-left { display: flex; align-items: center; gap: 10px; }
.hd-left .code { font-family: monospace; color: #c0c4cc; font-size: 13px; letter-spacing: .5px; }
.hd-left .name { font-weight: 600; color: #1f2937; }
.rule-bd { margin: 0 16px; border: 1px solid #f0f2f5; border-radius: 8px; padding: 14px 16px; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 14px 24px; }
.grid2.line { padding-bottom: 14px; border-bottom: 1px solid #f0f2f5; margin-bottom: 12px; }
.f { margin-bottom: 2px; }
.f + .f { margin-top: 12px; }
.fl { color: #909399; font-size: 12px; }
.fv { color: #1f2937; font-size: 14px; font-weight: 600; margin-top: 3px; }
/* 多值：单行省略 + 数量徽标 */
.fv.multi { display: flex; align-items: center; gap: 6px; min-width: 0; }
.mtext { min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mcnt { flex-shrink: 0; font-weight: 600; color: #0052d9; font-size: 11px; background: #eaf1ff; border-radius: 4px; padding: 1px 6px; cursor: default; }
.fl-row, .fb-row { display: flex; align-items: center; justify-content: space-between; }
.fb-row .fb { color: #1f2937; font-weight: 600; display: inline-flex; align-items: center; gap: 4px; }
.rule-ft { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 16px; }

.cfg-wrap { max-height: 76vh; overflow-y: auto; overflow-x: hidden; }
.cfg { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 0; }
.col { min-width: 0; padding: 0 14px; border-right: 1px solid #f0f2f5; }
.col:last-child { border-right: none; }
/* 长标签换行，避免撑出横向滚动 */
.col :deep(.el-checkbox) { white-space: normal; height: auto; align-items: flex-start; margin-right: 0; }
.col :deep(.el-checkbox__label) { white-space: normal; line-height: 1.4; word-break: break-word; }
.col-hd { font-weight: 600; color: #1f2937; padding-left: 8px; border-left: 3px solid #0052d9; margin-bottom: 18px; }
.col-hd.between, .lbl.between { display: flex; align-items: center; justify-content: space-between; }
.lbl { color: #606266; font-size: 13px; margin-bottom: 8px; }
.lbl.mt { margin-top: 22px; }
.req { color: #f56c6c; }
.chk-col { display: flex; flex-direction: column; gap: 8px; }
.chk-2col { display: grid; grid-template-columns: 1fr 1fr; row-gap: 8px; }
.chk-scroll { max-height: 460px; overflow: auto; border: 1px solid #f0f2f5; border-radius: 6px; padding: 10px 12px; }
.prod-row { display: flex; align-items: center; gap: 8px; padding: 4px 6px; border-radius: 6px; cursor: default; }
.prod-row + .prod-row { margin-top: 2px; }
.prod-row:hover { background: #f5f7fa; }
.prod-row.active { background: #eaf1ff; }
.prod-name { flex: 1; min-width: 0; cursor: pointer; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-size: 13px; }
.prod-row.active .prod-name { color: #0052d9; font-weight: 600; }
.cnt { color: #c0c4cc; font-size: 12px; margin-top: 10px; }
.muted { color: #c0c4cc; font-size: 13px; }
.overflow-box { border: 1px solid #faecd8; background: #fdf6ec; border-radius: 8px; padding: 12px; }
.overflow-box .tip { color: #e6a23c; font-size: 12px; margin-top: 8px; line-height: 1.5; }
.assignee { display: flex; align-items: center; gap: 6px; margin-bottom: 8px; }
.assignee .unit { color: #909399; font-size: 13px; }
</style>

<style>
/* 弹窗宽度自适应屏幕、上限 1340，永不超出视口（无横向拖动） */
.disp-dlg { max-width: 1340px; }
/* 卡片多值字段的悬浮浮窗：限宽换行展示完整内容 */
.rule-tip { max-width: 420px; line-height: 1.6; }
</style>
