<script setup>
import { ref, nextTick, computed, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import { aiParseFile } from '@/api'

const store    = useAppStore()
const open     = ref(false)
const input    = ref('')
const thinking = ref(false)
const messages = ref([])
const bodyRef  = ref(null)
const chatWidth = ref(440)
const selectedModel = ref('deepseek')
const fileUploading = ref(false)
const availableModels = ref([
  { id: 'deepseek', label: 'DeepSeek',      model: 'deepseek-chat' },
  { id: 'kimi',     label: 'Kimi',          model: 'kimi-k2.5' },
  { id: 'glm',      label: 'GLM',           model: 'glm-5' },
  { id: 'claude',   label: 'Claude Sonnet', model: 'anthropic/claude-sonnet-4.6' },
])
const currentModel = computed(() => availableModels.value.find(m => m.id === selectedModel.value))

// ── 工具调用可视化 ─────────────────────────────────────
const activeCalls = ref([])   // 当前轮次调用过的工具列表

const TOOL_LABELS = {
  get_overview: '年度仪表盘', get_division: '事业部详情',
  get_quarterly: '季度看板', get_monthly: '月度看板',
  get_opp_support: '商机分析', get_opportunities: '商机列表',
  get_collections: '催收明细', get_collection_dashboard: '催收总览',
  get_targets: '年度目标', get_trend: '同比趋势',
  detect_anomalies: '异常检测', analyze_root_cause: '根因分析',
  import_actuals: '导入月度数据', import_opportunities: '导入商机',
  import_collections: '导入催收', create_opportunity: '新增商机',
  update_opportunity: '更新商机', rollback_import: '撤销导入',
}

// ── 记忆系统：会话状态 ────────────────────────────────
const sessionId    = ref(null)
const sessions     = ref([])
const showHistory  = ref(false)

async function loadSessions() {
  try {
    const res = await fetch('/api/conversations/')
    const data = await res.json()
    sessions.value = data.data || []
  } catch {}
}

async function newSession() {
  // 只清空当前对话，不预创建 session（发第一条消息时自动创建并设置标题）
  sessionId.value = null
  messages.value  = []
}

async function loadSession(sid) {
  try {
    const res = await fetch(`/api/conversations/${sid}/messages`)
    const data = await res.json()
    messages.value = (data.data || []).map(m => ({ role: m.role, content: m.content }))
    sessionId.value = sid
    showHistory.value = false
    scrollBottom()
  } catch {}
}

async function deleteSession(sid, e) {
  e.stopPropagation()
  await fetch(`/api/conversations/${sid}`, { method: 'DELETE' })
  if (sessionId.value === sid) {
    sessionId.value = null
    messages.value  = []
  }
  await loadSessions()
}

function fmtTime(iso) {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  const diffMs = now - d
  const diffMins = Math.floor(diffMs / 60000)
  if (diffMins < 1)   return '刚刚'
  if (diffMins < 60)  return `${diffMins}分钟前`
  const diffH = Math.floor(diffMins / 60)
  if (diffH < 24)     return `${diffH}小时前`
  const diffD = Math.floor(diffH / 24)
  if (diffD < 7)      return `${diffD}天前`
  return `${d.getMonth()+1}/${d.getDate()}`
}

onMounted(loadSessions)

// 拖拽左侧边缘横向拉伸
function startResize(e) {
  e.preventDefault()
  const startX = e.clientX
  const startW = chatWidth.value
  function onMove(e) {
    const delta = startX - e.clientX
    chatWidth.value = Math.min(780, Math.max(300, startW + delta))
  }
  function onUp() {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

function scrollBottom() {
  nextTick(() => {
    if (bodyRef.value) bodyRef.value.scrollTop = bodyRef.value.scrollHeight
  })
}

async function send() {
  const text = input.value.trim()
  if (!text || thinking.value) return
  input.value = ''
  messages.value.push({ role: 'user', content: text })
  thinking.value = true
  activeCalls.value = []
  scrollBottom()

  // 首条消息时自动创建会话
  if (!sessionId.value) {
    try {
      const res = await fetch('/api/conversations/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          model_id: selectedModel.value,
          year: store.year,
          title: text.slice(0, 20),
        }),
      })
      const data = await res.json()
      sessionId.value = data.data?.id || null
      loadSessions()
    } catch {}
  }

  const idx = messages.value.length
  messages.value.push({ role: 'assistant', content: '' })
  scrollBottom()

  try {
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: messages.value.slice(0, -1).map(m => ({ role: m.role, content: m.content })),
        year: store.year,
        model_id: selectedModel.value,
        session_id: sessionId.value,
      }),
    })

    const reader = res.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop()
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const payload = line.slice(6)
        if (payload === '[DONE]') break
        try {
          const chunk = JSON.parse(payload)
          if (chunk.tool_call) {
            // 工具调用可视化：追加到 activeCalls
            const label = TOOL_LABELS[chunk.tool_call] || chunk.tool_call
            activeCalls.value.push(label)
            scrollBottom()
          } else if (chunk.text) {
            messages.value[idx].content += chunk.text
            scrollBottom()
          }
        } catch {}
      }
    }
  } catch (e) {
    messages.value[idx].content = '请求失败，请检查网络或 API Key 配置。'
  } finally {
    thinking.value = false
    activeCalls.value = []
    scrollBottom()
  }
}

function onKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    send()
  }
}

function clearMessages() {
  messages.value = []
  sessionId.value = null
}

async function selectFileDialog() {
  return new Promise((resolve) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = '.xlsx,.xls,.csv'
    input.addEventListener('change', (e) => {
      const file = e.target.files?.[0]
      if (file) {
        resolve(file)
      } else {
        resolve(null)
      }
    })
    input.click()
  })
}

async function handleAttachClick() {
  const file = await selectFileDialog()
  if (file) {
    await handleFile(file)
  }
}

function onFileDrop(e) {
  e.preventDefault()
  const file = e.dataTransfer.files?.[0]
  if (!file) return
  handleFile(file)
}

async function handleFile(file) {
  fileUploading.value = true
  try {
    const res = await aiParseFile(file)
    if (!res?.success || !res.data) {
      messages.value.push({ role: 'system-error', content: res?.message || '文件解析失败，请检查文件格式。' })
      scrollBottom()
      return
    }
    const data = res.data
    // 插入文件预览卡片（特殊消息类型）
    messages.value.push({
      role: 'file-preview',
      content: '',
      fileInfo: {
        filename: data.filename,
        importType: data.import_type,
        rowCount: data.row_count,
        columns: data.columns,
        sampleRows: data.sample_rows,
        pendingId: data.pending_id,
      }
    })
    scrollBottom()
  } catch(err) {
    messages.value.push({ role: 'system-error', content: '上传出错：' + (err?.message || '网络错误') })
    scrollBottom()
  } finally {
    fileUploading.value = false
  }
}

function confirmImport(fileInfo) {
  // 点确认后构造发送消息
  const text = `请帮我导入文件「${fileInfo.filename}」，pending_id=${fileInfo.pendingId}`
  input.value = text
  send()
}

function cancelImport(idx) {
  messages.value.splice(idx, 1)
}
function renderMd(text) {
  if (!text) return ''
  const codeBlocks = []
  text = text.replace(/```([\s\S]*?)```/g, (_, c) => { codeBlocks.push(c); return `%%C${codeBlocks.length - 1}%%` })
  text = text.replace(/((?:\|.+\n?)+)/g, block => {
    const lines = block.trim().split('\n').map(l => l.trim()).filter(l => l.startsWith('|'))
    if (lines.length < 2 || !/^\|[-| :]+\|$/.test(lines[1])) return block
    let t = '<table class="md-table">'
    lines.forEach((l, i) => {
      if (i === 1) return
      const cells = l.split('|').slice(1, -1).map(c => c.trim())
      const tag = i === 0 ? 'th' : 'td'
      t += '<tr>' + cells.map(c => `<${tag}>${c}</${tag}>`).join('') + '</tr>'
    })
    return t + '</table>\n'
  })
  text = text
    .replace(/^### (.+)$/gm, '<div class="md-h3">$1</div>')
    .replace(/^## (.+)$/gm,  '<div class="md-h2">$1</div>')
    .replace(/^# (.+)$/gm,   '<div class="md-h1">$1</div>')
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/\*\*\*(.+?)\*\*\*/g, '<b><em>$1</em></b>')
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    .replace(/^[-•] (.+)$/gm, '<div class="md-li">$1</div>')
    .replace(/^\d+\. (.+)$/gm, '<div class="md-oli">$1</div>')
    .replace(/^---$/gm, '<hr class="md-hr">')
    .replace(/\n\n+/g, '</p><p>')  // 段落分隔
    .replace(/\n/g, '<br>')
  text = '<p>' + text + '</p>'
  text = text.replace(/%%C(\d+)%%/g, (_, i) => `<pre><code>${codeBlocks[+i]}</code></pre>`)
  return text
}
</script>

<template>
  <!-- 悬浮触发按钮 -->
  <button class="ai-fab" @click="open = !open" :title="open ? '关闭助手' : '打开 AI 分析助手'">
    <svg v-if="!open" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/>
    </svg>
    <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
      <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
    </svg>
  </button>

  <!-- 对话框 -->
  <transition name="chat-slide">
    <div v-if="open" class="ai-chat" :style="{ width: chatWidth + 'px' }">
      <div class="resize-handle" @mousedown="startResize" title="拖拽调整宽度"></div>
      <!-- 头部 -->
      <div class="chat-header">
        <div class="chat-header-left">
          <span class="chat-title">小助</span>
          <select v-model="selectedModel" class="model-select" :disabled="thinking">
            <option v-for="m in availableModels" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
          <span class="model-name-badge">{{ currentModel?.model }}</span>
          <span v-if="thinking" class="chat-status thinking">
            <span class="dot-wave"><span/><span/><span/></span>思考中
          </span>
          <span v-else-if="messages.length" class="chat-status ready">● 就绪</span>
        </div>
        <div class="chat-header-right">
          <span class="chat-year">{{ store.year }}年</span>
          <!-- 历史记录按钮 -->
          <button class="clear-btn" @click="showHistory = !showHistory" :title="showHistory ? '关闭历史' : '历史记录'" :style="{ color: showHistory ? 'var(--accent)' : '' }">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/>
            </svg>
          </button>
          <button v-if="messages.length" class="clear-btn" @click="clearMessages" title="新建对话">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- 历史会话侧边栏 -->
      <transition name="history-slide">
        <div v-if="showHistory" class="history-panel">
          <div class="history-header">
            <span>历史对话</span>
            <button class="history-new-btn" @click="newSession">＋ 新建</button>
          </div>
          <div class="history-list">
            <div v-if="!sessions.length" class="history-empty">暂无历史记录</div>
            <div
              v-for="s in sessions" :key="s.id"
              class="history-item"
              :class="{ active: s.id === sessionId }"
              @click="loadSession(s.id)"
            >
              <div class="history-item-info">
                <span class="history-title">{{ s.title }}</span>
                <span class="history-time">{{ fmtTime(s.updated_at) }}</span>
              </div>
              <button class="history-del" @click="deleteSession(s.id, $event)" title="删除">×</button>
            </div>
          </div>
        </div>
      </transition>

      <!-- 消息区 -->
      <div class="chat-body" ref="bodyRef" @dragover.prevent @drop.prevent="onFileDrop">
        <div v-if="!messages.length" class="chat-empty">
          <div class="empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".4">
              <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/>
            </svg>
          </div>
          <p class="empty-title">你好，我是经营分析智能体「小助」</p>
          <div class="quick-grid">
            <div v-for="group in quickGroups" :key="group.label" class="quick-group">
              <div class="quick-group-label">{{ group.label }}</div>
              <button
                v-for="item in group.items" :key="item.text || item.label"
                class="quick-item"
                :class="{ 'quick-item--upload': item.upload }"
                @click="item.upload ? handleAttachClick() : (input = item.text, send())"
              >
                <span class="quick-item-icon">{{ item.icon }}</span>
                <span>{{ item.label }}</span>
              </button>
            </div>
          </div>
        </div>

        <template v-for="(msg, i) in messages" :key="i">
          <!-- 文件预览卡片 -->
          <div v-if="msg.role === 'file-preview'" class="file-card">
            <div class="file-card-header">
              <span class="file-card-icon">📄</span>
              <span class="file-card-name">{{ msg.fileInfo.filename }}</span>
              <span class="file-card-badge">{{ msg.fileInfo.importType }}</span>
            </div>
            <div class="file-card-meta">
              共 <b>{{ msg.fileInfo.rowCount }}</b> 行 &nbsp;·&nbsp;
              列名：{{ msg.fileInfo.columns.join('、') }}
            </div>
            <div class="file-card-sample">
              <div v-for="(row, ri) in msg.fileInfo.sampleRows.slice(0,2)" :key="ri" class="file-card-row">
                {{ Object.values(row).join(' | ') }}
              </div>
            </div>
            <div class="file-card-actions">
              <button class="file-card-btn file-card-btn--primary" @click="confirmImport(msg.fileInfo)">确认导入</button>
              <button class="file-card-btn" @click="cancelImport(i)">取消</button>
            </div>
          </div>
          <!-- 系统错误提示 -->
          <div v-else-if="msg.role === 'system-error'" class="system-error">⚠ {{ msg.content }}</div>
          <!-- 普通消息气泡 -->
          <div v-else :class="['chat-msg', msg.role]">
            <template v-if="!(thinking && i === messages.length - 1 && msg.role === 'assistant' && !msg.content)">
              <div v-if="msg.role === 'assistant'" class="avatar">AI</div>
              <div class="bubble" v-html="renderMd(msg.content)"></div>
            </template>
          </div>
        </template>

        <!-- 实时状态提示 -->
        <div v-if="thinking" class="status-toast">
          <span class="dot-wave"><span/><span/><span/></span>
          <div class="status-toast-inner">
            <span>{{ currentModel?.label }} 思考中...</span>
            <div v-if="activeCalls.length" class="tool-calls">
              <span v-for="(call, ci) in activeCalls" :key="ci" class="tool-call-tag">⚡ {{ call }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="chat-input">
        <textarea
          v-model="input"
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          rows="2"
          @keydown="onKeydown"
          :disabled="thinking"
        />
        <button class="attach-btn" @click="handleAttachClick"
                :disabled="fileUploading || thinking" title="上传 Excel 文件">
          {{ fileUploading ? '⏳' : '📎' }}
        </button>
        <button @click="send" :disabled="thinking || !input.trim()" class="send-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2 21l21-9L2 3v7l15 2-15 2z"/>
          </svg>
        </button>
      </div>
    </div>
  </transition>
</template>

<script>
// 快捷操作分组（放在 Options API 方便单独维护）
export default {
  data: () => ({
    quickGroups: [
      {
        label: '📊 数据查询',
        items: [
          { icon: '📈', label: '今年整体完成率',     text: '今年产品中心整体完成率怎么样？' },
          { icon: '🏆', label: '各事业部达成排名',   text: '各事业部合同达成率排名如何？' },
          { icon: '🎯', label: '本季度商机覆盖',     text: '本季度商机覆盖情况如何？' },
          { icon: '💰', label: '催收回款情况',       text: '今年催收回款率是多少？' },
        ]
      },
      {
        label: '📥 数据导入',
        items: [
          { icon: '📋', label: '上传月度数据', upload: true },
          { icon: '💼', label: '上传商机数据', upload: true },
          { icon: '🔖', label: '上传催收数据', upload: true },
        ]
      },
      {
        label: '🔍 异常分析',
        items: [
          { icon: '🩺', label: '整体健康体检',       text: '帮我做产品中心整体健康体检，有哪些异常？' },
          { icon: '📉', label: '大数据事业部分析',   text: '大数据事业部最近表现如何，有没有问题？' },
          { icon: '📊', label: '同比趋势分析',       text: '今年合同收入与去年同比趋势如何？' },
        ]
      },
      {
        label: '⚡ 快捷操作',
        items: [
          { icon: '🗓', label: '查看年度目标',       text: '今年各事业部年度目标是多少？' },
          { icon: '➕', label: '新增商机',           text: '我想新增一条商机，请引导我填写信息。' },
          { icon: '📅', label: '本月完成情况',       text: '本月各事业部完成情况怎么样？' },
        ]
      },
    ]
  })
}
</script>

<style scoped>
/* 悬浮按钮 */
.ai-fab {
  position: fixed; bottom: 28px; right: 28px; z-index: 1000;
  width: 50px; height: 50px; border-radius: 50%;
  background: var(--accent, #f0a500); border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: #000; box-shadow: 0 4px 20px rgba(240,165,0,.4);
  transition: transform .15s, box-shadow .15s;
}
.ai-fab:hover { transform: scale(1.08); box-shadow: 0 6px 24px rgba(240,165,0,.5); }

/* 对话框 */
.ai-chat {
  position: fixed; bottom: 92px; right: 28px; z-index: 999;
  height: 600px;
  background: var(--bg-card, #0f1923); border: 1px solid var(--bg-border, #1e2a38);
  border-radius: 16px; display: flex; flex-direction: column;
  box-shadow: 0 12px 40px rgba(0,0,0,.6); overflow: hidden;
}

/* 左侧拖拽把手 */
.resize-handle {
  position: absolute; left: 0; top: 0; bottom: 0; width: 5px;
  cursor: ew-resize; z-index: 10;
  border-radius: 16px 0 0 16px;
  transition: background .15s;
}
.resize-handle:hover { background: rgba(240,165,0,.3); }

.chat-slide-enter-active, .chat-slide-leave-active { transition: opacity .2s, transform .2s; }
.chat-slide-enter-from, .chat-slide-leave-to { opacity: 0; transform: translateY(14px) scale(.97); }

/* 头部 */
.chat-header {
  padding: 12px 16px; border-bottom: 1px solid var(--bg-border, #1e2a38);
  display: flex; align-items: center; justify-content: space-between;
  flex-shrink: 0;
}
.chat-header-left { display: flex; align-items: center; gap: 8px; }
.chat-header-right { display: flex; align-items: center; gap: 8px; }
.chat-title { font-size: 13px; font-weight: 600; }
.model-select {
  font-size: 11px; padding: 2px 6px; border-radius: 4px;
  background: rgba(240,165,0,.12); color: var(--accent, #f0a500);
  border: 1px solid rgba(240,165,0,.25); cursor: pointer; outline: none;
  font-weight: 500; transition: border-color .15s;
}
.model-select:hover:not(:disabled) { border-color: var(--accent, #f0a500); }
.model-select:disabled { opacity: .5; cursor: not-allowed; }
.model-name-badge {
  font-size: 10px; color: var(--text-sec, #7a8fa6);
  font-family: monospace; padding: 1px 0;
}
.chat-year { font-size: 11px; color: var(--text-sec, #7a8fa6); }
.chat-status { font-size: 10px; display: flex; align-items: center; gap: 4px; }
.status-toast {
  display: flex; align-items: center; gap: 7px;
  font-size: 11px; color: var(--accent, #f0a500);
  padding: 6px 10px; border-radius: 8px;
  background: rgba(240,165,0,.08); border: 1px solid rgba(240,165,0,.2);
  align-self: center; width: fit-content; margin: 0 auto;
}
.chat-status.ready { color: var(--green, #10b981); }

.clear-btn {
  background: none; border: none; cursor: pointer;
  color: var(--text-sec, #7a8fa6); padding: 3px;
  border-radius: 4px; display: flex; align-items: center;
  transition: color .15s;
}
.clear-btn:hover { color: var(--red, #ef4444); }

/* 消息区 */
.chat-body {
  flex: 1; overflow-y: auto; padding: 16px 14px 8px;
  display: flex; flex-direction: column; gap: 12px;
  scrollbar-width: thin;
}

/* 空状态 */
.chat-empty { display: flex; flex-direction: column; align-items: center; padding-top: 12px; width: 100%; }
.empty-icon { margin-bottom: 8px; }
.empty-title { font-size: 13px; font-weight: 600; margin-bottom: 12px; }

/* 快捷卡片网格 */
.quick-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 8px; width: 100%; }
.quick-group { background: var(--bg-base); border: 1px solid var(--bg-border); border-radius: 8px; padding: 10px; }
.quick-group-label { font-size: 10px; color: var(--text-sec); font-weight: 600; letter-spacing: 1px; margin-bottom: 6px; }
.quick-item {
  display: flex; align-items: center; gap: 6px; width: 100%;
  padding: 6px 8px; font-size: 12px; text-align: left;
  background: none; border: 1px solid transparent;
  border-radius: 6px; cursor: pointer; color: var(--text-main);
  transition: background .15s, border-color .15s; margin-bottom: 2px;
}
.quick-item:hover { background: rgba(240,165,0,.08); border-color: rgba(240,165,0,.3); }
.quick-item--upload { color: var(--accent); }
.quick-item-icon { font-size: 13px; flex-shrink: 0; }

/* 工具调用状态 */
.status-toast {
  display: flex; align-items: flex-start; gap: 7px;
  font-size: 11px; color: var(--accent, #f0a500);
  padding: 8px 10px; border-radius: 8px;
  background: rgba(240,165,0,.08); border: 1px solid rgba(240,165,0,.2);
  align-self: center; width: fit-content; margin: 0 auto; max-width: 90%;
}
.status-toast-inner { display: flex; flex-direction: column; gap: 4px; }
.tool-calls { display: flex; flex-wrap: wrap; gap: 4px; margin-top: 2px; }
.tool-call-tag {
  font-size: 10px; background: rgba(240,165,0,.12);
  border: 1px solid rgba(240,165,0,.2); border-radius: 4px;
  padding: 1px 6px; color: var(--accent);
}

/* 文件预览卡片 */
.file-card {
  background: rgba(16, 185, 129, .05); border: 1px solid rgba(16,185,129,.25);
  border-radius: 10px; padding: 12px 14px; font-size: 12px;
}
.file-card-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.file-card-icon { font-size: 16px; }
.file-card-name { font-weight: 600; flex: 1; color: var(--text-main); }
.file-card-badge {
  font-size: 10px; background: rgba(16,185,129,.15); color: var(--green);
  border-radius: 4px; padding: 1px 7px; border: 1px solid rgba(16,185,129,.3);
}
.file-card-meta { color: var(--text-sec); margin-bottom: 6px; }
.file-card-meta b { color: var(--text-main); font-family: var(--mono); }
.file-card-sample { background: rgba(0,0,0,.2); border-radius: 5px; padding: 6px 8px; margin-bottom: 8px; }
.file-card-row { font-family: var(--mono); font-size: 10px; color: var(--text-sec); line-height: 1.6; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-card-actions { display: flex; gap: 8px; }
.file-card-btn {
  padding: 5px 14px; border-radius: 6px; border: 1px solid var(--bg-border);
  font-size: 12px; cursor: pointer; background: var(--bg-base); color: var(--text-main);
  transition: background .15s;
}
.file-card-btn:hover { background: rgba(255,255,255,.07); }
.file-card-btn--primary {
  background: var(--green); color: #000; border-color: var(--green); font-weight: 600;
}
.file-card-btn--primary:hover { opacity: .85; }

/* 系统错误 */
.system-error {
  font-size: 12px; color: var(--red, #ef4444);
  background: rgba(239,68,68,.08); border: 1px solid rgba(239,68,68,.2);
  border-radius: 7px; padding: 7px 12px;
}

/* 气泡 */
.chat-msg { display: flex; align-items: flex-start; gap: 8px; }
.chat-msg.user { justify-content: flex-end; }
.chat-msg.assistant { justify-content: flex-start; }

.avatar {
  width: 26px; height: 26px; border-radius: 50%; flex-shrink: 0;
  background: var(--accent, #f0a500); color: #000;
  font-size: 9px; font-weight: 700;
  display: flex; align-items: center; justify-content: center;
  margin-top: 2px;
}

.bubble {
  max-width: 82%; padding: 10px 14px;
  border-radius: 14px; font-size: 13px; line-height: 1.3;
  word-break: break-word;
}
.user .bubble {
  background: var(--accent, #f0a500); color: #000;
  border-bottom-right-radius: 3px;
}
.assistant .bubble {
  background: var(--bg-border, #1e2a38); color: var(--text-main, #e2e8f0);
  border-bottom-left-radius: 3px;
}
.bubble.typing { padding: 12px 16px; }

/* Markdown 样式 */
.bubble :deep(p) { margin: 0; }
.bubble :deep(p + p) { margin-top: 2px; }
.bubble :deep(.md-h1) { font-size: 15px; font-weight: 700; margin: 2px 0 1px; }
.bubble :deep(.md-h2) { font-size: 14px; font-weight: 700; margin: 2px 0 0px; color: var(--accent, #f0a500); }
.bubble :deep(.md-h3) { font-size: 13px; font-weight: 600; margin: 2px 0 0px; color: var(--text-sec, #9ab); }
.bubble :deep(.md-li) {
  padding-left: 14px; position: relative; margin: 0px 0;
}
.bubble :deep(.md-li)::before { content: '•'; position: absolute; left: 2px; color: var(--accent, #f0a500); }
.bubble :deep(.md-oli) { padding-left: 4px; margin: 0px 0; }
.bubble :deep(.inline-code) {
  background: rgba(255,255,255,.1); padding: 1px 5px;
  border-radius: 4px; font-family: monospace; font-size: 12px;
}
.bubble :deep(pre) {
  background: rgba(0,0,0,.3); border-radius: 6px; padding: 8px 10px;
  margin: 2px 0; overflow-x: auto;
}
.bubble :deep(pre code) { font-size: 11px; font-family: monospace; }
.bubble :deep(.md-hr) { border: none; border-top: 1px solid var(--bg-border, #1e2a38); margin: 2px 0; }
.bubble :deep(.md-table) { border-collapse:collapse; width:100%; margin:2px 0; font-size:12px; }
.bubble :deep(.md-table th) { background:rgba(255,255,255,.08); color:var(--text-sec, #9ab); padding:4px 8px; text-align:left; font-weight:600; }
.bubble :deep(.md-table td) { padding:4px 8px; border-top:1px solid rgba(255,255,255,.06); font-family:monospace; }
.bubble :deep(.md-table tr:hover td) { background:rgba(255,255,255,.04); }
.bubble :deep(br) { display: none; }

/* 打字动画 */
.dot-wave { display: inline-flex; gap: 3px; align-items: center; }
.dot-wave span {
  width: 5px; height: 5px; border-radius: 50%;
  background: var(--accent, #f0a500); display: inline-block;
  animation: dotBounce 1.2s infinite ease-in-out;
}
.dot-wave span:nth-child(2) { animation-delay: .2s; }
.dot-wave span:nth-child(3) { animation-delay: .4s; }
@keyframes dotBounce {
  0%, 80%, 100% { transform: translateY(0); opacity: .4; }
  40% { transform: translateY(-5px); opacity: 1; }
}

/* 输入区 */
.chat-input {
  padding: 10px 12px 12px; border-top: 1px solid var(--bg-border, #1e2a38);
  display: flex; gap: 8px; align-items: flex-end; flex-shrink: 0;
}
.chat-input textarea {
  flex: 1; background: rgba(255,255,255,.04); border: 1px solid var(--bg-border, #1e2a38);
  border-radius: 10px; padding: 8px 12px; color: var(--text-main, #e2e8f0);
  font-size: 13px; resize: none; outline: none; font-family: inherit;
  transition: border-color .15s; line-height: 1.5;
}
.chat-input textarea:focus { border-color: var(--accent, #f0a500); }
.chat-input textarea:disabled { opacity: .5; }

.attach-btn {
  width: 36px; height: 36px; border: none; background: none; cursor: pointer;
  font-size: 18px; opacity: 0.7; padding: 0;
  display: flex; align-items: center; justify-content: center;
  transition: opacity .15s; flex-shrink: 0;
}
.attach-btn:disabled { opacity: 0.35; cursor: not-allowed; }
.attach-btn:not(:disabled):hover { opacity: 1; }

.send-btn {
  width: 36px; height: 36px; border-radius: 10px; border: none; cursor: pointer;
  background: var(--accent, #f0a500); color: #000;
  display: flex; align-items: center; justify-content: center;
  transition: opacity .15s; flex-shrink: 0;
}
.send-btn:disabled { opacity: .35; cursor: not-allowed; }
.send-btn:not(:disabled):hover { opacity: .85; }

/* 历史侧边栏 */
.history-panel {
  position: absolute; top: 48px; right: 0; width: 220px;
  background: var(--bg-card, #0f1923); border-left: 1px solid var(--bg-border, #1e2a38);
  border-bottom: 1px solid var(--bg-border, #1e2a38); border-radius: 0 0 0 8px;
  z-index: 10; display: flex; flex-direction: column; max-height: 320px;
}
.history-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border-bottom: 1px solid var(--bg-border, #1e2a38);
  font-size: 11px; color: var(--text-sec, #7a8fa6); font-weight: 600; letter-spacing: 1px;
}
.history-new-btn {
  font-size: 11px; color: var(--accent, #f0a500); background: none; border: none;
  cursor: pointer; padding: 2px 4px; border-radius: 3px;
}
.history-new-btn:hover { background: rgba(240,165,0,.12); }
.history-list { overflow-y: auto; flex: 1; }
.history-empty { padding: 16px 12px; font-size: 11px; color: var(--text-dim, #4a5568); text-align: center; }
.history-item {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; cursor: pointer; font-size: 12px; color: var(--text-main, #e2e8f0);
  border-bottom: 1px solid rgba(255,255,255,.04); gap: 6px;
}
.history-item:hover { background: rgba(255,255,255,.04); }
.history-item.active { background: rgba(240,165,0,.08); color: var(--accent, #f0a500); }
.history-item-info { flex: 1; overflow: hidden; display: flex; flex-direction: column; gap: 2px; }
.history-title { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 12px; }
.history-time  { font-size: 10px; color: var(--text-dim, #4a5568); }
.history-del {
  flex-shrink: 0; background: none; border: none; color: var(--text-dim, #4a5568);
  cursor: pointer; font-size: 14px; line-height: 1; padding: 0 2px; border-radius: 2px;
}
.history-del:hover { color: var(--red, #ef4444); }
.history-slide-enter-active, .history-slide-leave-active { transition: opacity .15s, transform .15s; }
.history-slide-enter-from, .history-slide-leave-to { opacity: 0; transform: translateY(-8px); }
</style>
