<script setup>
import { onMounted, ref } from 'vue'
import { faqApi } from '@/api'
const q = ref(''); const items = ref([])
const search = async () => { const d = await faqApi.search({ query: q.value }); items.value = d.items }
onMounted(async () => { const d = await faqApi.browse({ page_no: 1, page_size: 30 }); items.value = d.items })
</script>
<template>
  <el-card>
    <div style="display:flex;gap:8px;margin-bottom:16px"><el-input v-model="q" placeholder="语义搜索 FAQ" @keyup.enter="search"/><el-button type="primary" @click="search">搜索</el-button></div>
    <el-row :gutter="16">
      <el-col :span="8" v-for="f in items" :key="f.id" style="margin-bottom:16px">
        <el-card shadow="hover">
          <div style="font-weight:600">{{ f.title }}</div>
          <div style="color:#888;font-size:13px;margin:8px 0;height:54px;overflow:hidden">{{ f.content }}</div>
          <el-tag size="small">{{ f.productTag }}</el-tag>
          <span v-if="f.similarity!=null" style="float:right;color:#1677ff">{{ (f.similarity*100).toFixed(0) }}%</span>
        </el-card>
      </el-col>
    </el-row>
  </el-card>
</template>
