<script setup>
import { ref, nextTick, computed } from 'vue'
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
const fileInputRef = ref(null)
const availableModels = ref([
  { id: 'deepseek', label: 'DeepSeek',      model: 'deepseek-chat' },
  { id: 'kimi',     label: 'Kimi',          model: 'kimi-k2.5' },
  { id: 'glm',      label: 'GLM',           model: 'glm-5' },
  { id: 'claude',   label: 'Claude Sonnet', model: 'anthropic/claude-sonnet-4.6' },
])
const currentModel = computed(() => availableModels.value.find(m => m.id === selectedModel.value))

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
  scrollBottom()

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
          if (chunk.text) {
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
}

async function handleFileSelect(e) {
  alert('✓ 文件选择事件被触发')
  const file = e.target.files?.[0]
  console.log('handleFileSelect triggered, file:', file)
  if (!file) {
    alert('❌ 没有选中文件')
    return
  }
  alert(`✓ 文件已选择: ${file.name}`)
  await handleFile(file)
}

function onFileDrop(e) {
  e.preventDefault()
  const file = e.dataTransfer.files?.[0]
  if (!file) return
  handleFile(file)
}

async function handleFile(file) {
  console.log('handleFile called with:', file.name)
  fileUploading.value = true
  try {
    console.log('Calling aiParseFile...')
    const res = await aiParseFile(file)
    console.log('aiParseFile full response:', JSON.stringify(res, null, 2))
    console.log('res type:', typeof res, 'is object:', res && typeof res === 'object')
    console.log('res.success:', res?.success)
    console.log('res.data:', res?.data)
    console.log('res.data.sample_rows:', res?.data?.sample_rows)

    if (!res || typeof res !== 'object' || !res.success) {
      const msg = res?.message || (typeof res === 'string' ? res : '未知错误')
      alert('文件解析失败：' + msg)
      return
    }

    if (!res.data) {
      alert('服务器返回数据无效：data 字段为空')
      console.error('res:', res)
      return
    }

    const data = res.data
    console.log('data object:', data)
    console.log('data.sample_rows:', data.sample_rows, 'type:', typeof data.sample_rows)

    if (!Array.isArray(data.sample_rows)) {
      alert('样本数据格式错误，期望数组但得到：' + typeof data.sample_rows)
      return
    }

    const sample = data.sample_rows.map(r => JSON.stringify(r)).join('\n')
    input.value =
      `我上传了文件「${data.filename}」，类型：${data.import_type}，共 ${data.row_count} 行。\n` +
      `列名：${data.columns.join('、')}\n` +
      `前3行样本：\n${sample}\n\n` +
      `pending_id=${data.pending_id}\n\n` +
      `请确认数据无误后帮我导入数据库。`
    console.log('About to send message...')
    await send()
  } catch(err) {
    console.error('Error in handleFile:', err)
    console.error('Error stack:', err?.stack)
    alert('上传文件出错：' + (err?.message || '网络错误，请检查浏览器控制台'))
  } finally {
    fileUploading.value = false
    if (fileInputRef.value) fileInputRef.value.value = ''
  }
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
    .replace(/\n/g, '<br>')
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
          <button v-if="messages.length" class="clear-btn" @click="clearMessages" title="清空对话">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14H6L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4h6v2"/>
            </svg>
          </button>
        </div>
      </div>

      <!-- 消息区 -->
      <div class="chat-body" ref="bodyRef" @dragover.prevent @drop.prevent="onFileDrop">
        <div v-if="!messages.length" class="chat-empty">
          <div class="empty-icon">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity=".4">
              <path d="M12 2l2.4 7.4H22l-6.2 4.5 2.4 7.4L12 17l-6.2 4.3 2.4-7.4L2 9.4h7.6z"/>
            </svg>
          </div>
          <p class="empty-title">你好，我是经营分析智能体</p>
          <p class="empty-sub">试试这些问题：</p>
          <div class="suggestions">
            <button v-for="q in suggestions" :key="q" class="suggestion" @click="input = q; send()">{{ q }}</button>
          </div>
        </div>

        <div v-for="(msg, i) in messages" :key="i" :class="['chat-msg', msg.role]">
          <template v-if="!(thinking && i === messages.length - 1 && msg.role === 'assistant' && !msg.content)">
            <div v-if="msg.role === 'assistant'" class="avatar">AI</div>
            <div class="bubble" v-html="renderMd(msg.content)"></div>
          </template>
        </div>

        <!-- 实时状态提示 -->
        <div v-if="thinking" class="status-toast">
          <span class="dot-wave"><span/><span/><span/></span>
          <span>{{ currentModel?.label }}（{{ currentModel?.model }}）正在思考...</span>
        </div>
      </div>

      <!-- 输入区 -->
      <div class="chat-input">
        <input type="file" ref="fileInputRef" name="file" id="fileInput" accept=".xlsx,.xls,.csv"
               style="display:none" @change="handleFileSelect" />
        <textarea
          v-model="input"
          placeholder="输入问题，Enter 发送，Shift+Enter 换行"
          rows="2"
          @keydown="onKeydown"
          :disabled="thinking"
        />
        <button class="attach-btn" @click="fileInputRef?.click()"
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
// 示例问题（放在 Options API 方便单独维护）
export default {
  data: () => ({
    suggestions: [
      '产品中心今年整体完成率怎么样？',
      '哪个事业部合同达成率最低？',
      '本季度商机完成情况如何？',
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
.chat-empty { display: flex; flex-direction: column; align-items: center; padding-top: 20px; }
.empty-icon { margin-bottom: 12px; }
.empty-title { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.empty-sub { font-size: 11px; color: var(--text-sec, #7a8fa6); margin-bottom: 12px; }
.suggestions { display: flex; flex-direction: column; gap: 6px; width: 100%; }
.suggestion {
  text-align: left; padding: 8px 12px; font-size: 12px;
  background: var(--bg-border, #1e2a38); border: 1px solid transparent;
  border-radius: 8px; cursor: pointer; color: var(--text-main, #e2e8f0);
  transition: border-color .15s, background .15s;
}
.suggestion:hover { border-color: var(--accent, #f0a500); background: rgba(240,165,0,.08); }

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
  border-radius: 14px; font-size: 13px; line-height: 1.7;
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
.bubble :deep(.md-h1) { font-size: 15px; font-weight: 700; margin: 8px 0 4px; }
.bubble :deep(.md-h2) { font-size: 14px; font-weight: 700; margin: 6px 0 3px; color: var(--accent, #f0a500); }
.bubble :deep(.md-h3) { font-size: 13px; font-weight: 600; margin: 4px 0 2px; color: var(--text-sec, #9ab); }
.bubble :deep(.md-li) {
  padding-left: 14px; position: relative; margin: 2px 0;
}
.bubble :deep(.md-li)::before { content: '•'; position: absolute; left: 2px; color: var(--accent, #f0a500); }
.bubble :deep(.md-oli) { padding-left: 4px; margin: 2px 0; }
.bubble :deep(.inline-code) {
  background: rgba(255,255,255,.1); padding: 1px 5px;
  border-radius: 4px; font-family: monospace; font-size: 12px;
}
.bubble :deep(pre) {
  background: rgba(0,0,0,.3); border-radius: 6px; padding: 10px 12px;
  margin: 6px 0; overflow-x: auto;
}
.bubble :deep(pre code) { font-size: 11px; font-family: monospace; }
.bubble :deep(.md-hr) { border: none; border-top: 1px solid var(--bg-border, #1e2a38); margin: 8px 0; }
.bubble :deep(.md-table) { border-collapse:collapse; width:100%; margin:8px 0; font-size:12px; }
.bubble :deep(.md-table th) { background:rgba(255,255,255,.08); color:var(--text-sec, #9ab); padding:6px 10px; text-align:left; font-weight:600; }
.bubble :deep(.md-table td) { padding:6px 10px; border-top:1px solid rgba(255,255,255,.06); font-family:monospace; }
.bubble :deep(.md-table tr:hover td) { background:rgba(255,255,255,.04); }

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
</style>
