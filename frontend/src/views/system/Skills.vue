<script setup>
import { onMounted, ref } from 'vue'
import { skillApi } from '@/api'
import { ElMessage } from 'element-plus'
const list = ref([]); const cur = ref(null); const content = ref(''); const saving = ref(false)
const load = async () => { const d = await skillApi.list(); list.value = d.items }
const open = async (s) => { const d = await skillApi.get(s.name); cur.value = d; content.value = d.contentMd }
const save = async () => { saving.value = true; try { await skillApi.edit(cur.value.name, { content_md: content.value }); ElMessage.success('已保存并热生效'); load() } finally { saving.value = false } }
onMounted(load)
</script>
<template>
  <el-row :gutter="16">
    <el-col :span="7"><el-card header="Skill 列表">
      <el-table :data="list" @row-click="open" style="cursor:pointer" size="small">
        <el-table-column prop="name" label="名称"/>
        <el-table-column prop="type" label="类型" width="70"/>
        <el-table-column prop="version" label="版本" width="60"/>
      </el-table>
    </el-card></el-col>
    <el-col :span="17"><el-card>
      <template #header>{{ cur ? cur.name + ' (v' + cur.version + ')' : 'SKILL.md 编辑' }}</template>
      <div v-if="cur">
        <el-alert v-if="!cur.editable" type="info" :closable="false" title="代码逻辑型，不可编辑" style="margin-bottom:8px"/>
        <el-input type="textarea" v-model="content" :rows="22" :disabled="!cur.editable" style="font-family:monospace"/>
        <el-button v-if="cur.editable" type="primary" :loading="saving" style="margin-top:12px" @click="save">保存（热生效）</el-button>
      </div>
      <el-empty v-else description="选择左侧 Skill 编辑"/>
    </el-card></el-col>
  </el-row>
</template>
