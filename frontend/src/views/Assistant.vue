<script setup>
import { nextTick, ref } from 'vue'
import { assistantApi } from '@/api'
import { ElMessage } from 'element-plus'

const input = ref('')
const sending = ref(false)
const msgs = ref([{ role: 'bot', text: '你好，我可以帮你统计工单数据，或提交工单。试试「统计各状态工单数量」。' }])
const box = ref(null)

const scroll = async () => { await nextTick(); box.value && (box.value.scrollTop = box.value.scrollHeight) }

const send = async () => {
  const q = input.value.trim()
  if (!q) return
  msgs.value.push({ role: 'me', text: q })
  input.value = ''
  sending.value = true
  await scroll()
  try {
    const data = await assistantApi.chat({ nl_query: q })
    msgs.value.push({ role: 'bot', type: 'query', sql: data.sql, rows: data.result, rowCount: data.rowCount })
  } catch (e) {
    msgs.value.push({ role: 'bot', text: e?.message || '查询失败，换种问法试试' })
  } finally {
    sending.value = false
    await scroll()
  }
}

const submitVisible = ref(false)
const form = ref({ title: '', description: '' })
const submit = async () => {
  try {
    const data = await assistantApi.submit({ ...form.value })
    ElMessage.success(`工单已创建 #${data.ticketNo}`)
    submitVisible.value = false
    msgs.value.push({ role: 'bot', text: `已为你创建工单 ${data.ticketNo}` })
  } catch (e) { ElMessage.error(e?.message || '提单失败') }
}
const cols = (rows) => (rows && rows.length ? Object.keys(rows[0]) : [])
</script>

<template>
  <el-card style="height: calc(100vh - 110px); display: flex; flex-direction: column">
    <template #header>
      <span>智能助手（只读统计 + 提单）</span>
      <el-button size="small" style="float: right" @click="submitVisible = true">提交工单</el-button>
    </template>
    <div ref="box" style="flex: 1; overflow: auto; padding: 8px">
      <div v-for="(m, i) in msgs" :key="i" :style="{ textAlign: m.role === 'me' ? 'right' : 'left', margin: '10px 0' }">
        <div :style="{ display: 'inline-block', maxWidth: '80%', padding: '10px 14px', borderRadius: '8px', background: m.role === 'me' ? '#1677ff' : '#f0f2f5', color: m.role === 'me' ? '#fff' : '#000', textAlign: 'left' }">
          <template v-if="m.type === 'query'">
            <div v-if="m.sql" style="font-family: monospace; font-size: 12px; color: #888; margin-bottom: 6px">SQL: {{ m.sql }}</div>
            <el-table v-if="m.rows && m.rows.length" :data="m.rows" size="small" border max-height="320">
              <el-table-column v-for="c in cols(m.rows)" :key="c" :prop="c" :label="c" />
            </el-table>
            <div v-else>无数据</div>
            <div style="color: #999; font-size: 12px; margin-top: 4px">共 {{ m.rowCount }} 条</div>
          </template>
          <span v-else>{{ m.text }}</span>
        </div>
      </div>
    </div>
    <div style="display: flex; gap: 8px; padding-top: 8px; border-top: 1px solid #eee">
      <el-input v-model="input" placeholder="用自然语言提问统计…" @keyup.enter="send" :disabled="sending" />
      <el-button type="primary" :loading="sending" @click="send">发送</el-button>
    </div>
  </el-card>

  <el-dialog v-model="submitVisible" title="提交工单" width="500px">
    <el-form :model="form" label-width="60px">
      <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="描述"><el-input type="textarea" :rows="4" v-model="form.description" placeholder="至少15字" /></el-form-item>
    </el-form>
    <template #footer><el-button @click="submitVisible = false">取消</el-button><el-button type="primary" @click="submit">提交</el-button></template>
  </el-dialog>
</template>
