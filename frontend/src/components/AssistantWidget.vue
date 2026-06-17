<script setup>
// 全局悬浮「工单助手」：跳动机器人 → 右侧推出对话框（可拖动 / 可调大小）
// 左侧会话列表（新增会话 / 管理-删除-完成 / 查看历史），右侧对话区。会话持久化 localStorage。
import { nextTick, onMounted, reactive, ref } from 'vue'
import { assistantApi } from '@/api'
import { ElMessage } from 'element-plus'

const GREETING = { role: 'bot', text: '你好，我是工单助手。可以帮你统计工单数据或提交工单，试试「统计各状态工单数量」。' }
const SKEY = 'assistant-sessions'
const PKEY = 'assistant-panel'

const open = ref(false)
const sessions = ref([])
const activeId = ref(null)
const input = ref('')
const sending = ref(false)
const manage = ref(false)
const checked = ref([])
const box = ref(null)

// —— 面板位置 / 尺寸（可拖动、可调整、持久化）——
const pos = reactive({ top: 0, left: 0, width: 560, height: 600 })

const loadSessions = () => {
  try {
    const s = JSON.parse(localStorage.getItem(SKEY) || 'null')
    if (Array.isArray(s) && s.length) { sessions.value = s; activeId.value = s[0].id; return }
  } catch (e) { /* ignore */ }
  newSession(true)
}
const persist = () => localStorage.setItem(SKEY, JSON.stringify(sessions.value))
const active = () => sessions.value.find((s) => s.id === activeId.value)

let _seq = 0
const genId = () => `s${sessions.value.length}_${(_seq += 1)}`

function newSession(silent) {
  const s = { id: genId(), title: '新会话', msgs: [{ ...GREETING }] }
  sessions.value.unshift(s)
  activeId.value = s.id
  if (!silent) { persist(); scroll() }
}
const selectSession = (id) => { if (manage.value) return; activeId.value = id; scroll() }

const exitManage = () => { manage.value = false; checked.value = [] }
const toggleCheck = (id, v) => {
  if (v) checked.value.push(id)
  else checked.value = checked.value.filter((x) => x !== id)
}
const delChecked = () => {
  if (!checked.value.length) return ElMessage.warning('请先勾选要删除的会话')
  sessions.value = sessions.value.filter((s) => !checked.value.includes(s.id))
  if (!sessions.value.length) newSession(true)
  else if (!sessions.value.find((s) => s.id === activeId.value)) activeId.value = sessions.value[0].id
  checked.value = []
  persist()
}

const scroll = async () => { await nextTick(); box.value && (box.value.scrollTop = box.value.scrollHeight) }
const cols = (rows) => (rows && rows.length ? Object.keys(rows[0]) : [])

const send = async () => {
  const q = input.value.trim()
  if (!q || sending.value) return
  const s = active()
  s.msgs.push({ role: 'me', text: q })
  if (s.title === '新会话') s.title = q.slice(0, 18)
  input.value = ''
  sending.value = true
  await scroll()
  try {
    const data = await assistantApi.chat({ nl_query: q })
    s.msgs.push({ role: 'bot', type: 'query', sql: data.sql, rows: data.result, rowCount: data.rowCount })
  } catch (e) {
    s.msgs.push({ role: 'bot', text: e?.message || '查询失败，换种问法试试' })
  } finally {
    sending.value = false
    persist()
    await scroll()
  }
}

// —— 会话右键菜单：删除 / 重命名 ——
const ctx = reactive({ visible: false, x: 0, y: 0, id: null })
const editingId = ref(null)
const editText = ref('')
const openCtx = (e, id) => { ctx.visible = true; ctx.x = e.clientX; ctx.y = e.clientY; ctx.id = id }
const closeCtx = () => { ctx.visible = false }
const delSession = (id) => {
  sessions.value = sessions.value.filter((s) => s.id !== id)
  if (!sessions.value.length) newSession(true)
  else if (activeId.value === id) activeId.value = sessions.value[0].id
  persist()
}
const ctxDelete = () => { const id = ctx.id; closeCtx(); delSession(id) }
const ctxRename = () => {
  const s = sessions.value.find((x) => x.id === ctx.id)
  closeCtx()
  if (!s) return
  editingId.value = s.id
  editText.value = s.title
}
const commitRename = () => {
  if (!editingId.value) return
  const s = sessions.value.find((x) => x.id === editingId.value)
  if (s) { const t = editText.value.trim().slice(0, 50); s.title = t || s.title; persist() }
  editingId.value = null
}

// —— 拖动 / 调整大小 ——
const persistPos = () => localStorage.setItem(PKEY, JSON.stringify(pos))
function startDrag(e) {
  const sx = e.clientX, sy = e.clientY, st = pos.top, sl = pos.left
  const move = (ev) => {
    pos.top = Math.max(0, Math.min(window.innerHeight - 60, st + ev.clientY - sy))
    pos.left = Math.max(0, Math.min(window.innerWidth - 120, sl + ev.clientX - sx))
  }
  const up = () => { document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up); persistPos() }
  document.addEventListener('mousemove', move); document.addEventListener('mouseup', up)
}
function startResize(e) {
  e.stopPropagation()
  const sx = e.clientX, sy = e.clientY, sw = pos.width, sh = pos.height, sl = pos.left
  const move = (ev) => {
    const dx = ev.clientX - sx, dy = ev.clientY - sy
    const nw = Math.max(380, sw - dx)            // 左下角手柄：向左拖变宽
    pos.left = sl + (sw - nw)
    pos.width = nw
    pos.height = Math.max(320, Math.min(window.innerHeight - pos.top, sh + dy))
  }
  const up = () => { document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up); persistPos() }
  document.addEventListener('mousemove', move); document.addEventListener('mouseup', up)
}

const toggleOpen = () => {
  open.value = !open.value
  if (open.value) {
    // 默认固定在右侧
    try {
      const p = JSON.parse(localStorage.getItem(PKEY) || 'null')
      if (p) Object.assign(pos, p)
      else Object.assign(pos, { width: 560, height: Math.round(window.innerHeight * 0.8), top: 0, left: window.innerWidth - 560 })
    } catch (e) { /* ignore */ }
    if (pos.left + pos.width > window.innerWidth) pos.left = Math.max(0, window.innerWidth - pos.width)
    scroll()
  }
}

onMounted(() => {
  loadSessions()
  document.addEventListener('click', closeCtx)
})
</script>

<template>
  <!-- 悬浮机器人（跳动效果） -->
  <div class="fab" :class="{ hidden: open }" @click="toggleOpen" title="工单助手">
    <span class="robot">
      <svg viewBox="0 0 64 64" class="robot-svg" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <linearGradient id="botBody" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0" stop-color="#4d8cff" />
            <stop offset="1" stop-color="#0052d9" />
          </linearGradient>
        </defs>
        <!-- 天线 -->
        <line x1="32" y1="6" x2="32" y2="14" stroke="#0052d9" stroke-width="2.6" stroke-linecap="round" />
        <circle cx="32" cy="5" r="3.2" fill="#36d1a0" />
        <!-- 耳朵 -->
        <rect x="8.5" y="23" width="4.5" height="11" rx="2.2" fill="#0052d9" />
        <rect x="51" y="23" width="4.5" height="11" rx="2.2" fill="#0052d9" />
        <!-- 头 -->
        <rect x="12" y="12" width="40" height="34" rx="15" fill="url(#botBody)" />
        <!-- 脸屏 -->
        <rect x="17" y="18.5" width="30" height="20" rx="10" fill="#eaf2ff" />
        <!-- 眼睛 -->
        <circle cx="26" cy="28" r="3.6" fill="#0052d9" />
        <circle cx="38" cy="28" r="3.6" fill="#0052d9" />
        <circle cx="27.3" cy="26.7" r="1.2" fill="#fff" />
        <circle cx="39.3" cy="26.7" r="1.2" fill="#fff" />
        <!-- 腮红 -->
        <circle cx="20.5" cy="31.5" r="2.2" fill="#ff9bb3" opacity=".7" />
        <circle cx="43.5" cy="31.5" r="2.2" fill="#ff9bb3" opacity=".7" />
        <!-- 微笑 -->
        <path d="M26.5 33.2 Q32 37.6 37.5 33.2" stroke="#0052d9" stroke-width="2" fill="none" stroke-linecap="round" />
        <!-- 脚下的云（发票云） -->
        <g>
          <ellipse cx="32" cy="51" rx="14" ry="6" fill="#fff" />
          <circle cx="23" cy="50" r="5.2" fill="#fff" />
          <circle cx="41" cy="50" r="5.2" fill="#fff" />
        </g>
      </svg>
    </span>
    <span class="fab-label">工单助手</span>
  </div>

  <!-- 右侧推出对话框 -->
  <Transition name="slide">
    <div v-if="open" class="panel" :style="{ top: pos.top+'px', left: pos.left+'px', width: pos.width+'px', height: pos.height+'px' }">
      <div class="panel-head" @mousedown="startDrag">
        <span><el-icon><ChatDotRound /></el-icon> 工单助手</span>
        <span class="head-actions">
          <el-icon class="close" @click="open=false"><Close /></el-icon>
        </span>
      </div>

      <div class="panel-body">
        <!-- 左：会话列表 -->
        <div class="side">
          <el-button class="new-btn" type="primary" color="#0052d9" @click="newSession()"><el-icon><Plus /></el-icon> 新增会话</el-button>
          <div class="side-head">
            <span>会话记录</span>
            <span v-if="!manage" class="link" @click="manage=true">管理</span>
            <span v-else class="manage-ops">
              <span class="link danger" @click="delChecked">删除</span>
              <span class="sep">|</span>
              <span class="link" @click="exitManage">完成</span>
            </span>
          </div>
          <div class="sess-list">
            <div v-for="s in sessions" :key="s.id" class="sess" :class="{ active: s.id===activeId }"
                 @click="selectSession(s.id)" @contextmenu.prevent="openCtx($event, s.id)">
              <el-checkbox v-if="manage" :model-value="checked.includes(s.id)" @change="(v)=>toggleCheck(s.id,v)" @click.stop />
              <el-input v-if="editingId===s.id" v-model="editText" size="small" maxlength="50" show-word-limit autofocus
                        @click.stop @keyup.enter="commitRename" @keyup.esc="editingId=null" @blur="commitRename" />
              <span v-else class="sess-title">{{ s.title }}</span>
            </div>
          </div>
        </div>

        <!-- 右：对话区 -->
        <div class="chat">
          <div ref="box" class="chat-box">
            <div v-for="(m,i) in active()?.msgs || []" :key="i" class="msg" :class="m.role">
              <div class="bubble" :class="m.role">
                <template v-if="m.type==='query'">
                  <div v-if="m.sql" class="sql">SQL: {{ m.sql }}</div>
                  <el-table v-if="m.rows && m.rows.length" :data="m.rows" size="small" border max-height="280">
                    <el-table-column v-for="c in cols(m.rows)" :key="c" :prop="c" :label="c" />
                  </el-table>
                  <div v-else>无数据</div>
                  <div class="cnt">共 {{ m.rowCount }} 条</div>
                </template>
                <span v-else>{{ m.text }}</span>
              </div>
            </div>
          </div>
          <div class="chat-input">
            <el-input v-model="input" placeholder="用自然语言提问统计…" @keyup.enter="send" :disabled="sending" />
            <el-button type="primary" color="#0052d9" :loading="sending" @click="send">发送</el-button>
          </div>
        </div>
      </div>

      <!-- 左下角调整大小手柄 -->
      <div class="resize-handle" @mousedown="startResize" title="拖动调整大小"></div>
    </div>
  </Transition>

  <!-- 会话右键菜单 -->
  <div v-if="ctx.visible" class="ctx-menu" :style="{ left: ctx.x+'px', top: ctx.y+'px' }" @click.stop>
    <div class="ctx-item danger" @click="ctxDelete">删除</div>
    <div class="ctx-item" @click="ctxRename">重命名</div>
  </div>
</template>

<style scoped>
/* 悬浮机器人 */
.fab { position: fixed; right: 26px; bottom: 30px; z-index: 2999; display: flex; flex-direction: column; align-items: center;
       cursor: pointer; user-select: none; animation: bounce 1.4s ease-in-out infinite; }
.fab.hidden { display: none; }
.fab .robot { width: 60px; height: 60px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
       background: radial-gradient(circle at 50% 38%, #ffffff 0%, #eef4ff 100%);
       box-shadow: 0 6px 18px rgba(0,82,217,.32); border: 1px solid #e0eaff; }
.fab .robot-svg { width: 46px; height: 46px; display: block; }
.fab .fab-label { margin-top: 4px; font-size: 11px; color: #0052d9; background: #fff; padding: 1px 6px; border-radius: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.12); }
@keyframes bounce { 0%,100% { transform: translateY(0); } 50% { transform: translateY(-12px); } }

/* 面板 */
.panel { position: fixed; z-index: 3000; background: #fff; border: 1px solid #e4e7ed; border-radius: 10px;
         box-shadow: 0 12px 40px rgba(0,0,0,.22); display: flex; flex-direction: column; overflow: hidden; }
.panel-head { height: 42px; flex-shrink: 0; display: flex; align-items: center; justify-content: space-between;
              padding: 0 14px; background: linear-gradient(135deg, #0052d9, #4d8cff); color: #fff; cursor: move; font-weight: 600; }
.panel-head .el-button { color: #fff; }
.head-actions { display: flex; align-items: center; gap: 10px; }
.panel-head .close { cursor: pointer; font-size: 18px; }
.panel-body { flex: 1; display: flex; overflow: hidden; }

/* 左侧会话 */
.side { width: 150px; flex-shrink: 0; border-right: 1px solid #eee; display: flex; flex-direction: column; background: #fafbfc; }
.new-btn { margin: 10px; }
.side-head { display: flex; align-items: center; justify-content: space-between; padding: 4px 12px; font-size: 12px; color: #909399; }
.manage-ops { display: flex; align-items: center; gap: 4px; }
.link { cursor: pointer; color: #0052d9; }
.link.danger { color: #f56c6c; }
.sep { color: #dcdfe6; }
.sess-list { flex: 1; overflow: auto; }
.sess { display: flex; align-items: center; gap: 6px; padding: 8px 12px; font-size: 13px; cursor: pointer; color: #333; }
.sess:hover { background: #eef3ff; }
.sess.active { background: #e6efff; color: #0052d9; font-weight: 600; }
.sess-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* 右侧对话 */
.chat { flex: 1; display: flex; flex-direction: column; overflow: hidden; }
.chat-box { flex: 1; overflow: auto; padding: 10px; }
.msg { margin: 10px 0; display: flex; }
.msg.me { justify-content: flex-end; }
.bubble { display: inline-block; max-width: 82%; padding: 9px 13px; border-radius: 8px; font-size: 13px; line-height: 1.5; }
.bubble.bot { background: #f0f2f5; color: #000; }
.bubble.me { background: #0052d9; color: #fff; }
.sql { font-family: monospace; font-size: 12px; color: #888; margin-bottom: 6px; }
.cnt { color: #999; font-size: 12px; margin-top: 4px; }
.chat-input { display: flex; gap: 8px; padding: 8px; border-top: 1px solid #eee; }

/* 调整大小手柄（左下角） */
.resize-handle { position: absolute; left: 0; bottom: 0; width: 16px; height: 16px; cursor: nesw-resize;
                 background: linear-gradient(225deg, transparent 50%, #c0c4cc 50%); }

/* 会话右键菜单 */
.ctx-menu { position: fixed; z-index: 3001; min-width: 96px; background: #fff; border: 1px solid #e4e7ed;
            border-radius: 6px; box-shadow: 0 6px 20px rgba(0,0,0,.16); padding: 4px 0; }
.ctx-item { padding: 7px 16px; font-size: 13px; cursor: pointer; color: #333; }
.ctx-item:hover { background: #f0f5ff; }
.ctx-item.danger { color: #f56c6c; }
.ctx-item.danger:hover { background: #fef0f0; }

/* 右侧滑入动画 */
.slide-enter-active, .slide-leave-active { transition: transform .28s ease, opacity .28s ease; }
.slide-enter-from, .slide-leave-to { transform: translateX(40px); opacity: 0; }
</style>
