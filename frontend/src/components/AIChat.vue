<script setup>
import { ref, nextTick } from 'vue'
import { useAppStore } from '@/stores/app'

const store   = useAppStore()
const open    = ref(false)
const input   = ref('')
const thinking = ref(false)
const messages = ref([])
const bodyRef  = ref(null)

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

  // 先占位 assistant 消息
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

// 简单 markdown：**bold** 和换行
function renderMd(text) {
  return text
    .replace(/\*\*(.*?)\*\*/g, '<b>$1</b>')
    .replace(/\n/g, '<br>')
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
    <div v-if="open" class="ai-chat">
      <div class="chat-header">
        <span class="chat-title">AI 分析助手</span>
        <span class="chat-sub">{{ store.year }}年 · DeepSeek</span>
      </div>

      <div class="chat-body" ref="bodyRef">
        <div v-if="!messages.length" class="chat-empty">
          <p>你好！我可以帮你分析经营数据。</p>
          <p>试试问我：</p>
          <ul>
            <li @click="input = '产品中心今年整体完成率怎么样？'">产品中心今年整体完成率怎么样？</li>
            <li @click="input = '哪个事业部合同达成率最低？'">哪个事业部合同达成率最低？</li>
            <li @click="input = '本季度商机支撑情况如何？'">本季度商机支撑情况如何？</li>
          </ul>
        </div>

        <div
          v-for="(msg, i) in messages" :key="i"
          :class="['chat-msg', msg.role]"
        >
          <div class="bubble" v-html="renderMd(msg.content || (thinking && i === messages.length - 1 ? '···' : ''))"></div>
        </div>
      </div>

      <div class="chat-input">
        <textarea
          v-model="input"
          placeholder="输入问题，Enter 发送"
          rows="2"
          @keydown="onKeydown"
          :disabled="thinking"
        />
        <button @click="send" :disabled="thinking || !input.trim()" class="send-btn">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
            <path d="M2 21l21-9L2 3v7l15 2-15 2z"/>
          </svg>
        </button>
      </div>
    </div>
  </transition>
</template>

<style scoped>
/* 悬浮按钮 */
.ai-fab {
  position: fixed; bottom: 28px; right: 28px; z-index: 1000;
  width: 48px; height: 48px; border-radius: 50%;
  background: var(--accent, #f0a500); border: none; cursor: pointer;
  display: flex; align-items: center; justify-content: center;
  color: #000; box-shadow: 0 4px 16px rgba(0,0,0,.4);
  transition: transform .15s, box-shadow .15s;
}
.ai-fab:hover { transform: scale(1.08); box-shadow: 0 6px 20px rgba(0,0,0,.5); }

/* 对话框容器 */
.ai-chat {
  position: fixed; bottom: 88px; right: 28px; z-index: 999;
  width: 380px; max-height: 520px;
  background: var(--bg-card, #0f1923); border: 1px solid var(--bg-border, #1e2a38);
  border-radius: 14px; display: flex; flex-direction: column;
  box-shadow: 0 8px 32px rgba(0,0,0,.5); overflow: hidden;
}

/* 动画 */
.chat-slide-enter-active, .chat-slide-leave-active { transition: opacity .2s, transform .2s; }
.chat-slide-enter-from, .chat-slide-leave-to { opacity: 0; transform: translateY(12px) scale(.97); }

/* 头部 */
.chat-header {
  padding: 12px 16px; border-bottom: 1px solid var(--bg-border, #1e2a38);
  display: flex; align-items: baseline; gap: 8px;
}
.chat-title { font-size: 13px; font-weight: 600; }
.chat-sub { font-size: 11px; color: var(--text-sec, #7a8fa6); }

/* 消息区 */
.chat-body {
  flex: 1; overflow-y: auto; padding: 14px 14px 6px;
  display: flex; flex-direction: column; gap: 10px;
  scrollbar-width: thin;
}

.chat-empty { color: var(--text-sec, #7a8fa6); font-size: 12px; line-height: 1.8; }
.chat-empty ul { padding-left: 0; list-style: none; margin-top: 8px; }
.chat-empty li {
  padding: 5px 10px; background: var(--bg-border, #1e2a38);
  border-radius: 6px; margin-bottom: 5px; cursor: pointer;
  transition: background .1s;
}
.chat-empty li:hover { background: rgba(240,165,0,.15); }

/* 气泡 */
.chat-msg { display: flex; }
.chat-msg.user { justify-content: flex-end; }
.chat-msg.assistant { justify-content: flex-start; }

.bubble {
  max-width: 85%; padding: 9px 13px;
  border-radius: 12px; font-size: 13px; line-height: 1.65;
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

/* 输入区 */
.chat-input {
  padding: 10px 12px; border-top: 1px solid var(--bg-border, #1e2a38);
  display: flex; gap: 8px; align-items: flex-end;
}
.chat-input textarea {
  flex: 1; background: transparent; border: 1px solid var(--bg-border, #1e2a38);
  border-radius: 8px; padding: 7px 10px; color: var(--text-main, #e2e8f0);
  font-size: 13px; resize: none; outline: none; font-family: inherit;
  transition: border-color .15s;
}
.chat-input textarea:focus { border-color: var(--accent, #f0a500); }
.chat-input textarea:disabled { opacity: .5; }

.send-btn {
  width: 34px; height: 34px; border-radius: 8px; border: none; cursor: pointer;
  background: var(--accent, #f0a500); color: #000;
  display: flex; align-items: center; justify-content: center;
  transition: opacity .15s; flex-shrink: 0;
}
.send-btn:disabled { opacity: .4; cursor: not-allowed; }
.send-btn:not(:disabled):hover { opacity: .85; }
</style>
