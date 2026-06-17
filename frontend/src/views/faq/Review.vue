<script setup>
import { onMounted, ref } from 'vue'
import { faqApi } from '@/api'
import { REVIEW, dict } from '@/dicts'
import { ElMessage } from 'element-plus'
const items = ref([])
const load = async () => { const d = await faqApi.reviewList({ page_size: 50 }); items.value = d.items }
const review = async (id, result) => { await faqApi.review(id, { result }); ElMessage.success('已处理'); load() }
onMounted(load)
</script>
<template>
  <el-card header="FAQ 审核（驳回置顶）">
    <el-table :data="items" stripe>
      <el-table-column prop="faqNo" label="编号" width="160"/>
      <el-table-column prop="title" label="标题" show-overflow-tooltip/>
      <el-table-column label="状态" width="90"><template #default="{row}"><el-tag size="small" :type="dict(REVIEW,row.reviewStatus).type">{{ dict(REVIEW,row.reviewStatus).label }}</el-tag></template></el-table-column>
      <el-table-column label="操作" width="160"><template #default="{row}">
        <el-button size="small" type="success" @click="review(row.id,'approved')">通过</el-button>
        <el-button size="small" type="danger" @click="review(row.id,'rejected')">驳回</el-button>
      </template></el-table-column>
    </el-table>
  </el-card>
</template>
