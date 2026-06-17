<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { moduleOwnerApi } from '@/api'
import { PRODUCT_LINES } from '@/dicts'
import { ElMessage } from 'element-plus'

const allRows = ref([])
const loading = ref(false)
const q = reactive({ products: [], funcModule: '', active: '' })   // active: ''全部 / true / false
const page = ref(1)
const pageSize = ref(20)

const load = async () => {
  loading.value = true
  try { const d = await moduleOwnerApi.list({}); allRows.value = d.items } finally { loading.value = false }
}
const productOptions = computed(() => [...new Set(allRows.value.map((r) => r.productTag).filter(Boolean))])
const filtered = computed(() => allRows.value.filter((r) => {
  if (q.products.length && !q.products.includes(r.productTag)) return false
  if (q.funcModule && !(r.funcModule || '').includes(q.funcModule)) return false
  if (q.active !== '' && r.isActive !== q.active) return false
  return true
}))
// 客户端分页
const paged = computed(() => filtered.value.slice((page.value - 1) * pageSize.value, page.value * pageSize.value))
watch([() => q.products, () => q.funcModule, () => q.active], () => { page.value = 1 })
const reset = () => { q.products = []; q.funcModule = ''; q.active = ''; page.value = 1 }

// —— 新增弹窗 ——
const dialog = ref(false)
const form = ref({ product_tag: '', func_module: '', trigger_words: '', dev_owner: '', row_type: 'module' })
const openAdd = () => { form.value = { product_tag: '', func_module: '', trigger_words: '', dev_owner: '', row_type: 'module' }; dialog.value = true }
const save = async () => {
  if (!form.value.product_tag) return ElMessage.warning('请选择产品线')
  if (!form.value.func_module) return ElMessage.warning('请输入功能模块')
  await moduleOwnerApi.create(form.value)        // 新记录默认 is_active=true(启用)
  ElMessage.success('已新增')
  dialog.value = false
  load()
}
const toggle = async (row) => {
  await moduleOwnerApi.toggle(row.id)
  ElMessage.success(row.isActive ? '已禁用' : '已启用')
  load()
}
onMounted(load)
</script>

<template>
  <el-card>
    <!-- 筛选 + 新增：滚动时固定 -->
    <div class="sticky-bar">
    <el-form :inline="true" @submit.prevent>
      <el-form-item label="产品线">
        <el-select v-model="q.products" multiple collapse-tags collapse-tags-tooltip placeholder="全部" clearable style="width:220px">
          <el-option v-for="p in productOptions" :key="p" :label="p" :value="p" />
        </el-select>
      </el-form-item>
      <el-form-item label="功能模块"><el-input v-model="q.funcModule" placeholder="功能模块" clearable style="width:160px" /></el-form-item>
      <el-form-item label="状态">
        <el-select v-model="q.active" placeholder="全部" clearable style="width:120px">
          <el-option label="启用" :value="true" /><el-option label="禁用" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item><el-button @click="reset">重置</el-button></el-form-item>
    </el-form>

    <!-- 工具条：新增 -->
    <div style="margin-bottom:12px">
      <el-button type="primary" color="#0052d9" @click="openAdd"><el-icon><Plus /></el-icon> 新增</el-button>
    </div>
    </div>

    <el-table :data="paged" v-loading="loading" stripe border max-height="calc(100vh - 330px)">
      <el-table-column prop="productTag" label="产品线" width="200" show-overflow-tooltip />
      <el-table-column prop="funcModule" label="功能模块" min-width="180" show-overflow-tooltip />
      <el-table-column prop="triggerWords" label="触发词" width="300" show-overflow-tooltip />
      <el-table-column prop="devOwner" label="责任人" width="120" />
      <el-table-column label="状态" width="100" align="center">
        <template #default="{row}"><el-tag size="small" :type="row.isActive ? 'success' : 'info'">{{ row.isActive ? '启用' : '禁用' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="110" fixed="right" align="center">
        <template #default="{row}">
          <el-button v-if="row.isActive" size="small" type="warning" plain @click="toggle(row)">禁用</el-button>
          <el-button v-else size="small" type="success" plain @click="toggle(row)">启用</el-button>
        </template>
      </el-table-column>
    </el-table>
    <el-pagination
      style="margin-top:14px;justify-content:flex-end"
      layout="total, sizes, prev, pager, next, jumper"
      :total="filtered.length"
      :page-size="pageSize"
      :current-page="page"
      :page-sizes="[20, 50, 100, 500, 1000]"
      @size-change="(s)=>{ pageSize = s; page = 1 }"
      @current-change="(p)=>{ page = p }" />

    <!-- 新增弹窗 -->
    <el-dialog v-model="dialog" title="新增模块责任人" width="480px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="产品线" required>
          <el-select v-model="form.product_tag" placeholder="请选择产品线" filterable style="width:100%">
            <el-option v-for="p in PRODUCT_LINES" :key="p" :label="p" :value="p" />
          </el-select>
        </el-form-item>
        <el-form-item label="功能模块" required>
          <el-input v-model="form.func_module" placeholder="手动输入功能模块（文本）" />
        </el-form-item>
        <el-form-item label="触发词">
          <el-input v-model="form.trigger_words" placeholder="可选，多个用 | 分隔" />
        </el-form-item>
        <el-form-item label="责任人">
          <el-input v-model="form.dev_owner" placeholder="手动录入责任人" />
        </el-form-item>
        <el-form-item label="状态">
          <el-tag type="success" size="small">启用（新增默认启用）</el-tag>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" color="#0052d9" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<style scoped>
/* 筛选+新增区域滚动时吸顶；表头由 el-table max-height 自带固定 */
.sticky-bar { position: sticky; top: -14px; z-index: 10; background: #fff; padding-top: 4px; }
</style>
