<script setup>
import { onMounted, ref } from 'vue'
import { faqApi } from '@/api'
import { useAuth } from '@/stores/auth'
import { REVIEW, dict } from '@/dicts'
import { ElMessage, ElMessageBox } from 'element-plus'
const auth = useAuth(); const rows = ref([]); const kw = ref('')
const load = async () => { const d = await faqApi.list({ keyword: kw.value, page_no: 1, page_size: 50 }); rows.value = d.items }
const del = async (id) => { await ElMessageBox.confirm('删除后不再被检索，确认？','提示'); await faqApi.remove(id); ElMessage.success('已删除'); load() }
onMounted(load)
</script>
<template>
  <el-card>
    <el-form :inline="true"><el-form-item label="关键词"><el-input v-model="kw" clearable style="width:200px"/></el-form-item><el-form-item><el-button type="primary" @click="load">查询</el-button></el-form-item></el-form>
    <el-table :data="rows" stripe>
      <el-table-column prop="faqNo" label="编号" width="160"/>
      <el-table-column prop="title" label="标题" show-overflow-tooltip/>
      <el-table-column prop="productTag" label="产品线" width="130"/>
      <el-table-column label="审核" width="90"><template #default="{row}"><el-tag size="small" :type="dict(REVIEW,row.reviewStatus).type">{{ dict(REVIEW,row.reviewStatus).label }}</el-tag></template></el-table-column>
      <el-table-column prop="hitCount" label="命中" width="80"/>
      <el-table-column v-if="auth.can('admin')" label="操作" width="100"><template #default="{row}"><el-button size="small" type="danger" @click="del(row.id)">删除</el-button></template></el-table-column>
    </el-table>
  </el-card>
</template>
