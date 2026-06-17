<script setup>
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ticketApi } from '@/api'
import { BRANCH, dict } from '@/dicts'
import { ElMessage, ElMessageBox } from 'element-plus'
const router = useRouter()
const rows = ref([])
const load = async () => { const d = await ticketApi.myTickets({ page_no: 1, page_size: 50 }); rows.value = d.items }
const done = (m) => { ElMessage.success(m); load() }
const close = async (r) => { await ticketApi.close(r.id, {}); done('已关单') }
const toRd = async (r) => { await ElMessageBox.confirm('转研发？','确认'); await ticketApi.handle(r.id,{action:'to_rd'}); done('已转研发') }
const supply = async (r) => { const {value}=await ElMessageBox.prompt('需客户补充内容','补充资料',{inputType:'textarea'}); await ticketApi.handle(r.id,{action:'supply',reply_content:value}); done('已发补料') }
onMounted(load)
</script>
<template>
  <el-card header="我的待办（派到我名下的 B/C 工单）">
    <el-empty v-if="!rows.length" description="暂无派到你名下的待办（派单按处理人姓名匹配）"/>
    <el-table v-else :data="rows" stripe>
      <el-table-column prop="ticketNo" label="工单号" width="170"/>
      <el-table-column label="分支" width="86"><template #default="{row}"><el-tag v-if="row.answerBranch" size="small" :type="dict(BRANCH,row.answerBranch).type">{{ dict(BRANCH,row.answerBranch).label }}</el-tag></template></el-table-column>
      <el-table-column prop="title" label="标题" show-overflow-tooltip/>
      <el-table-column prop="productTag" label="产品线" width="120"/>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{row}">
          <el-button size="small" @click="router.push(`/tickets/${row.id}`)">详情</el-button>
          <el-button size="small" type="success" @click="close(row)">确认关单</el-button>
          <el-button size="small" type="warning" @click="supply(row)">补料</el-button>
          <el-button size="small" type="danger" @click="toRd(row)">转研发</el-button>
        </template>
      </el-table-column>
    </el-table>
  </el-card>
</template>
