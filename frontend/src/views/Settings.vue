<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

const templates = [
  { name: '年度目标导入模板', desc: '批量设置年度目标及月度分解', type: 'targets' },
  { name: '月度完成数据导入模板', desc: '录入各事业部月度实际完成数据', type: 'actuals' },
  { name: '商机数据导入模板', desc: '批量录入商机明细', type: 'opps' },
]
const threshold = ref(60)

// ── API Key 管理 ──────────────────────────────────────
const apiKeyStatus  = ref({ enabled: false, preview: '' })
const newKeyVisible = ref(false)
const newKeyValue   = ref('')
const keyLoading    = ref(false)

async function loadApiKeyStatus() {
  try {
    const res = await fetch('/api/settings/apikey')
    apiKeyStatus.value = await res.json()
  } catch {}
}

async function generateKey() {
  await ElMessageBox.confirm(
    '生成新 API Key 后旧 Key 立即失效，外部调用需更新。确定继续？',
    '生成 API Key',
    { type: 'warning', confirmButtonText: '确定生成', cancelButtonText: '取消' }
  )
  keyLoading.value = true
  try {
    const res = await fetch('/api/settings/apikey/generate', { method: 'POST' })
    const data = await res.json()
    newKeyValue.value  = data.key
    newKeyVisible.value = true
    await loadApiKeyStatus()
    ElMessage.success('新 API Key 已生成')
  } finally {
    keyLoading.value = false
  }
}

async function clearKey() {
  await ElMessageBox.confirm(
    '清除后所有外部调用无需认证，确定关闭 API Key 认证？',
    '关闭认证',
    { type: 'warning', confirmButtonText: '确定关闭', cancelButtonText: '取消' }
  )
  await fetch('/api/settings/apikey', { method: 'DELETE' })
  newKeyVisible.value = false
  await loadApiKeyStatus()
  ElMessage.success('API Key 已清除，认证已关闭')
}

function copyKey() {
  navigator.clipboard.writeText(newKeyValue.value)
  ElMessage.success('已复制到剪贴板')
}

onMounted(loadApiKeyStatus)
</script>

<template>
  <div>
    <div style="font-size:16px;font-weight:600;margin-bottom:16px">设置 &amp; 模板</div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">
      <div class="card">
        <div class="card-title">导入模板下载</div>
        <div style="display:flex;flex-direction:column;gap:10px">
          <div v-for="t in templates" :key="t.type" class="tmpl-row">
            <div>
              <div style="font-size:13px;font-weight:500;color:var(--text-pri)">{{ t.name }}</div>
              <div style="font-size:11px;color:var(--text-sec);margin-top:2px">{{ t.desc }}</div>
            </div>
            <a :href="`/api/import/template/${t.type}`" download>
              <el-button size="small">↓ 下载</el-button>
            </a>
          </div>
        </div>
      </div>

      <div class="card">
        <div class="card-title">系统配置</div>
        <el-form label-width="120px" size="small">
          <el-form-item label="完成率预警阈值">
            <el-input-number v-model="threshold" :min="0" :max="100" />
            <span style="margin-left:8px;color:var(--text-sec)">%（当前：{{ threshold }}%）</span>
          </el-form-item>
          <el-form-item label="后端 API">
            <span style="font-family:var(--mono);color:var(--text-sec)">http://localhost:8010</span>
            <a href="http://localhost:8010/docs" target="_blank" style="margin-left:10px;color:var(--accent);font-size:12px">查看 API 文档 →</a>
          </el-form-item>
        </el-form>
      </div>

      <!-- API Key 管理（横跨两列） -->
      <div class="card" style="grid-column: 1 / -1">
        <div class="card-title" style="--dot-color: var(--accent)">Insight API Key 管理</div>

        <!-- 状态行 -->
        <div class="key-status-row">
          <div class="key-status-info">
            <span class="key-dot" :class="{ enabled: apiKeyStatus.enabled }" />
            <span v-if="apiKeyStatus.enabled" style="font-size:13px">
              认证已开启 &nbsp;·&nbsp;
              <span class="mono key-preview">{{ apiKeyStatus.preview }}</span>
            </span>
            <span v-else style="font-size:13px;color:var(--text-sec)">
              认证未开启，外部调用无需 API Key
            </span>
          </div>
          <div style="display:flex;gap:8px">
            <el-button size="small" type="primary" :loading="keyLoading" @click="generateKey">
              {{ apiKeyStatus.enabled ? '重新生成' : '生成 API Key' }}
            </el-button>
            <el-button v-if="apiKeyStatus.enabled" size="small" type="danger" plain @click="clearKey">
              关闭认证
            </el-button>
          </div>
        </div>

        <!-- 新 Key 展示（生成后显示） -->
        <div v-if="newKeyVisible" class="new-key-box">
          <div class="new-key-label">新 API Key（只显示一次，请立即复制保存）</div>
          <div class="new-key-row">
            <span class="mono new-key-value">{{ newKeyValue }}</span>
            <el-button size="small" @click="copyKey">复制</el-button>
            <el-button size="small" plain @click="newKeyVisible = false">关闭</el-button>
          </div>
        </div>

        <!-- 使用说明 -->
        <div class="key-usage">
          <div class="usage-title">外部调用示例（openclaw / curl）</div>
          <div class="code-block">curl -H "X-API-Key: &lt;your_key&gt;" "http://localhost:8010/api/dashboard/overview?year=2026"</div>
          <div class="code-block">Invoke-RestMethod -Headers @{"X-API-Key"="&lt;your_key&gt;"} -Uri "http://localhost:8010/api/..."</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:6px">内部前端（localhost:5173）自动豁免，无需携带 Key</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:18px 20px; }
.card-title {
  font-size:11px; letter-spacing:1.5px; color:var(--text-sec);
  margin-bottom:14px; display:flex; align-items:center; gap:8px;
}
.card-title::before { content:''; display:block; width:3px; height:12px; border-radius:2px; background:var(--dot-color, var(--accent)); }
.tmpl-row { display:flex; align-items:center; justify-content:space-between; padding:10px 12px; background:var(--bg-base); border-radius:7px; border:1px solid var(--bg-border); }

/* API Key */
.key-status-row { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.key-status-info { display:flex; align-items:center; gap:8px; }
.key-dot { width:8px; height:8px; border-radius:50%; background:var(--text-dim); display:inline-block; transition:.3s; }
.key-dot.enabled { background:var(--green); box-shadow:0 0 6px var(--green); }
.key-preview { font-size:13px; color:var(--text-sec); letter-spacing:1px; }
.mono { font-family:var(--mono); }

.new-key-box { background:rgba(240,165,0,.06); border:1px solid rgba(240,165,0,.2); border-radius:7px; padding:12px 14px; margin-bottom:12px; }
.new-key-label { font-size:11px; color:var(--amber, #f0a500); margin-bottom:8px; font-weight:600; }
.new-key-row { display:flex; align-items:center; gap:8px; }
.new-key-value { flex:1; font-size:12px; color:var(--text-main); word-break:break-all; }

.key-usage { background:var(--bg-base); border:1px solid var(--bg-border); border-radius:7px; padding:12px 14px; }
.usage-title { font-size:11px; color:var(--text-sec); font-weight:600; margin-bottom:8px; letter-spacing:1px; }
.code-block { font-family:var(--mono); font-size:11px; color:var(--text-sec); padding:5px 8px; background:rgba(0,0,0,.2); border-radius:4px; margin-bottom:4px; word-break:break-all; }
</style>
