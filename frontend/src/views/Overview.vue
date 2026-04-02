<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { getOverview, getReports, saveReport, getReport, deleteReport } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const router  = useRouter()
const store   = useAppStore()
const loading = ref(false)
const data    = ref(null)

const METRIC_LABEL = { contract: '合同', revenue: '收入', payment: '回款' }
const METRIC_COLOR = { contract: '#3b82f6', revenue: '#10b981', payment: '#f0a500' }

async function load() {
  loading.value = true
  const res = await getOverview(store.year)
  data.value = res?.data || null
  loading.value = false
}

onMounted(load)
watch(() => store.year, load)

function rateClass(r) {
  return r >= 80 ? 'good' : r >= 60 ? 'warn' : 'bad'
}
function fmt(n) {
  if (!n && n !== 0) return '—'
  return n >= 10000 ? (n / 10000).toFixed(1) + '亿' : n.toLocaleString('zh-CN')
}

// Summaries grouped by unit
const byUnit = computed(() => {
  if (!data.value) return []
  const map = {}
  for (const s of data.value.summaries) {
    if (!map[s.business_unit_id]) {
      map[s.business_unit_id] = { id: s.business_unit_id, name: s.business_unit_name, metrics: {} }
    }
    map[s.business_unit_id].metrics[s.metric_type] = s
  }
  return Object.values(map)
})

// Center-level KPI totals
const centerKpis = computed(() => {
  if (!data.value) return []
  return ['contract', 'revenue', 'payment'].map(m => {
    const items  = data.value.summaries.filter(s => s.metric_type === m)
    const ytd    = items.reduce((a, s) => a + s.ytd_actual, 0)
    const annual = items.reduce((a, s) => a + s.annual_target, 0)
    const rate   = annual > 0 ? +(ytd / annual * 100).toFixed(1) : 0
    return { metric: m, label: METRIC_LABEL[m], ytd, annual, rate }
  })
})

// Bar chart for contract completion rate per unit
const barOption = computed(() => {
  if (!byUnit.value.length) return {}
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>${p[0].marker}${p[0].value}%` },
    grid: { left: 110, right: 20, top: 10, bottom: 20 },
    xAxis: { type: 'value', max: 130, axisLabel: { color: '#7a8fa6', formatter: '{value}%', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    yAxis: { type: 'category', data: byUnit.value.map(u => u.name), axisLabel: { color: '#7a8fa6', fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{
      type: 'bar', barMaxWidth: 22,
      data: byUnit.value.map(u => {
        const s = u.metrics['contract']
        const r = s?.rate ?? 0
        return { value: r, itemStyle: { color: r >= 80 ? '#10b981' : r >= 60 ? '#f59e0b' : '#ef4444', borderRadius: [0, 3, 3, 0] } }
      }),
      label: { show: true, position: 'right', color: '#7a8fa6', fontSize: 10, formatter: '{c}%' }
    }]
  }
})

function goToDivision(unit) {
  router.push(`/division/${unit.id}`)
}

// ── AI 经营分析报告 ──────────────────────────────────
const report      = ref('')
const generating  = ref(false)
const reportModel = ref('deepseek')
const savedReports  = ref([])
const showHistory   = ref(false)
const saving        = ref(false)

async function loadReports() {
  const res = await getReports()
  savedReports.value = res?.data || []
}

async function onSaveReport() {
  if (!report.value) return
  saving.value = true
  const title = `${store.year}年度经营分析报告`
  await saveReport({ year: store.year, title, content: report.value, model_id: reportModel.value })
  ElMessage.success('报告已保存')
  saving.value = false
  await loadReports()
  showHistory.value = true
}

async function onDeleteReport(id) {
  await ElMessageBox.confirm('确认删除此报告？', '提示', { type: 'warning' })
  await deleteReport(id)
  ElMessage.success('已删除')
  await loadReports()
}

async function viewReport(item) {
  const res = await getReport(item.id)
  report.value = res?.data?.content || ''
  showHistory.value = false
}

onMounted(loadReports)

const REPORT_MODELS = [
  { id: 'deepseek', label: 'DeepSeek' },
  { id: 'kimi',     label: 'Kimi' },
  { id: 'glm',      label: 'GLM' },
  { id: 'claude',   label: 'Claude Sonnet' },
]

const reportModelLabel = computed(() =>
  REPORT_MODELS.find(m => m.id === reportModel.value)?.label || reportModel.value
)

async function generateReport() {
  report.value = ''
  generating.value = true
  const prompt = `请根据当前数据，生成${store.year}年度产品中心经营分析报告。请严格按以下格式输出：

## 总体情况
产品中心合同/收入/回款的年度目标与YTD完成情况，达成率评价。

## 各事业部分析
逐个分析4个事业部，每个事业部说明三项指标的完成情况，突出最强和最弱的指标。

## 主要风险
列出达成率低于60%的事业部/指标，以及商机覆盖不足的领域。

## 建议
针对主要风险，给出具体可执行的行动建议。`

  try {
    const res = await fetch('/api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        messages: [{ role: 'user', content: prompt }],
        year: store.year,
        model_id: reportModel.value,
      }),
    })
    const reader  = res.body.getReader()
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
          if (chunk.text) report.value += chunk.text
        } catch {}
      }
    }
  } catch {
    report.value = '> 生成失败，请检查 API Key 配置或网络连接。'
  } finally {
    generating.value = false
  }
}

// Markdown 渲染（同 AIChat.vue）
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
    .replace(/\*\*(.+?)\*\*/g, '<b>$1</b>')
    .replace(/^[-•] (.+)$/gm, '<div class="md-li">$1</div>')
    .replace(/^\d+\. (.+)$/gm, '<div class="md-oli">$1</div>')
    .replace(/^---$/gm, '<hr class="md-hr">')
    .replace(/\n/g, '<br>')
  text = text.replace(/%%C(\d+)%%/g, (_, i) => `<pre><code>${codeBlocks[+i]}</code></pre>`)
  return text
}
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <!-- KPI Row -->
    <div class="kpi-grid" v-if="data">
      <div
        v-for="kpi in centerKpis"
        :key="kpi.metric"
        class="kpi-card"
        :class="`k-${kpi.metric}`"
      >
        <div class="kpi-label">{{ kpi.label }} · 年累完成</div>
        <div class="kpi-row">
          <span class="kpi-value">{{ fmt(kpi.ytd) }}</span>
          <span class="kpi-unit">万元</span>
        </div>
        <div class="kpi-meta">
          <span class="kpi-rate" :class="rateClass(kpi.rate)">{{ kpi.rate }}%</span>
          <span class="kpi-yoy">年度总目标 <b style="color:var(--text-pri)">{{ fmt(kpi.annual) }}</b> 万</span>
        </div>
        <div class="kpi-progress">
          <div class="kpi-bar" :style="{ width: Math.min(kpi.rate, 100) + '%' }" />
        </div>
      </div>
    </div>

    <!-- 事业部经营指标完成情况 -->
    <div class="summary-table-wrap" v-if="data" style="margin-bottom:16px">
      <table class="summary-table">
        <thead>
          <tr>
            <th rowspan="2">事业部</th>
            <th colspan="3" class="th-group">合同</th>
            <th colspan="3" class="th-group">收入</th>
            <th colspan="3" class="th-group">回款</th>
          </tr>
          <tr>
            <th class="th-sub">目标(万)</th><th class="th-sub">完成(万)</th><th class="th-sub">完成率</th>
            <th class="th-sub">目标(万)</th><th class="th-sub">完成(万)</th><th class="th-sub">完成率</th>
            <th class="th-sub">目标(万)</th><th class="th-sub">完成(万)</th><th class="th-sub">完成率</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="unit in byUnit" :key="unit.id">
            <td class="td-name">{{ unit.name }}</td>
            <template v-for="m in ['contract','revenue','payment']" :key="m">
              <td>{{ fmt(unit.metrics[m]?.annual_target) }}</td>
              <td>{{ fmt(unit.metrics[m]?.ytd_actual) }}</td>
              <td><span class="rate-badge" :class="rateClass(unit.metrics[m]?.annual_rate ?? 0)">{{ unit.metrics[m]?.annual_rate ?? 0 }}%</span></td>
            </template>
          </tr>
        </tbody>
        <tfoot>
          <tr class="total-row">
            <td>合计</td>
            <template v-for="kpi in centerKpis" :key="kpi.metric">
              <td>{{ fmt(kpi.annual) }}</td>
              <td>{{ fmt(kpi.ytd) }}</td>
              <td><span class="rate-badge" :class="rateClass(kpi.rate)">{{ kpi.rate }}%</span></td>
            </template>
          </tr>
        </tfoot>
      </table>
    </div>

    <!-- AI 经营分析报告 -->
    <div class="ai-report-block" v-if="data">
      <div class="report-header">
        <div class="report-header-left">
          <div class="card-title" style="margin-bottom:0">AI 经营分析报告</div>
          <span v-if="savedReports.length" class="history-badge" @click="showHistory = !showHistory">
            历史记录 {{ savedReports.length }}
          </span>
        </div>
        <div class="report-controls">
          <select v-model="reportModel" class="model-select" :disabled="generating">
            <option v-for="m in REPORT_MODELS" :key="m.id" :value="m.id">{{ m.label }}</option>
          </select>
          <button class="gen-btn" @click="generateReport" :disabled="generating">
            <span v-if="generating"><span class="dot-wave"><span/><span/><span/></span> 生成中</span>
            <span v-else>生成报告</span>
          </button>
          <button v-if="report && !generating" class="save-btn" @click="onSaveReport" :disabled="saving">
            {{ saving ? '保存中...' : '保存报告' }}
          </button>
          <button v-if="report" class="clear-btn" @click="report = ''">清空</button>
        </div>
      </div>

      <!-- 历史记录列表 -->
      <div v-if="showHistory && savedReports.length" class="history-panel">
        <div v-for="item in savedReports" :key="item.id" class="history-item">
          <div class="history-info" @click="viewReport(item)">
            <span class="history-title">{{ item.title }}</span>
            <span class="history-meta">{{ item.model_id }} · {{ item.created_at }}</span>
          </div>
          <button class="del-btn" @click.stop="onDeleteReport(item.id)">×</button>
        </div>
      </div>

      <div v-if="generating && !report" class="report-thinking">
        <span class="dot-wave"><span/><span/><span/></span>
        {{ reportModelLabel }} 正在分析数据，请稍候...
      </div>
      <div v-if="report" class="report-content" v-html="renderMd(report)" />
    </div>

    <!-- Heatmap + Bar -->
    <div class="two-col" v-if="data">
      <div class="card">
        <div class="card-title">目标达成热力表</div>
        <table class="heatmap">
          <thead>
            <tr>
              <th style="text-align:left">事业部</th>
              <th v-for="m in ['contract','revenue','payment']" :key="m" colspan="2">{{ METRIC_LABEL[m] }}</th>
            </tr>
            <tr>
              <th></th>
              <template v-for="m in ['contract','revenue','payment']" :key="m">
                <th>完成率</th>
                <th>完成额(万)</th>
              </template>
            </tr>
          </thead>
          <tbody>
            <tr v-for="unit in byUnit" :key="unit.id">
              <td>
                <span class="div-link" @click="goToDivision(unit)">{{ unit.name }}</span>
              </td>
              <template v-for="m in ['contract','revenue','payment']" :key="m">
                <td>
                  <span class="rate-cell" :class="rateClass(unit.metrics[m]?.annual_rate ?? 0)">
                    {{ unit.metrics[m]?.annual_rate ?? 0 }}%
                  </span>
                </td>
                <td class="mono dim">{{ fmt(unit.metrics[m]?.ytd_actual) }}</td>
              </template>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="card">
        <div class="card-title">合同 YTD 完成率对比</div>
        <v-chart :option="barOption" style="height:240px" autoresize />
      </div>
    </div>

    <el-empty v-if="!loading && !data" description="暂无数据，请先导入目标和完成数据" />
  </div>
</template>

<style scoped>
.ai-report-block { margin-bottom: 16px; background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:16px 20px; }
.history-badge { font-size:11px; padding:2px 8px; border-radius:10px; background:rgba(240,165,0,.15); color:var(--accent); cursor:pointer; border:1px solid rgba(240,165,0,.25); }
.history-badge:hover { background:rgba(240,165,0,.25); }
.save-btn { font-size:12px; padding:5px 12px; border-radius:6px; border:1px solid var(--accent); background:transparent; color:var(--accent); cursor:pointer; transition:background .15s; }
.save-btn:not(:disabled):hover { background:rgba(240,165,0,.1); }
.save-btn:disabled { opacity:.5; cursor:not-allowed; }
.history-panel { background:var(--bg-base); border:1px solid var(--bg-border); border-radius:8px; margin-bottom:12px; overflow:hidden; }
.history-item { display:flex; align-items:center; justify-content:space-between; padding:9px 14px; border-bottom:1px solid var(--bg-border); }
.history-item:last-child { border-bottom:none; }
.history-info { flex:1; cursor:pointer; }
.history-info:hover .history-title { color:var(--accent); }
.history-title { font-size:12px; color:var(--text-main); display:block; }
.history-meta { font-size:11px; color:var(--text-sec); }
.del-btn { background:none; border:none; color:var(--text-sec); cursor:pointer; font-size:16px; padding:0 4px; line-height:1; }
.del-btn:hover { color:var(--red); }
.report-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.report-header-left { display:flex; align-items:center; gap:8px; }
.report-controls { display:flex; align-items:center; gap:8px; }
.model-select { font-size:11px; padding:3px 8px; border-radius:6px; background:rgba(240,165,0,.1); color:var(--accent); border:1px solid rgba(240,165,0,.25); outline:none; cursor:pointer; }
.model-select:disabled { opacity:.5; }
.model-select option { background:var(--bg-card); color:var(--text-main); }
.gen-btn { font-size:12px; padding:5px 14px; border-radius:6px; border:none; cursor:pointer; background:var(--accent); color:#000; font-weight:600; transition:opacity .15s; display:flex; align-items:center; gap:6px; }
.gen-btn:disabled { opacity:.5; cursor:not-allowed; }
.gen-btn:not(:disabled):hover { opacity:.85; }
.clear-btn { font-size:11px; padding:5px 10px; border-radius:6px; border:1px solid var(--bg-border); background:transparent; color:var(--text-sec); cursor:pointer; transition:color .15s; }
.clear-btn:hover { color:var(--red); border-color:var(--red); }
.report-thinking { display:flex; align-items:center; gap:8px; font-size:12px; color:var(--accent); padding:12px 0; }
.report-content { font-size:13px; line-height:1.8; color:var(--text-main); padding-top:4px; }
.report-content :deep(.md-h1) { font-size:16px; font-weight:700; margin:12px 0 6px; }
.report-content :deep(.md-h2) { font-size:14px; font-weight:700; margin:14px 0 6px; color:var(--accent); padding-bottom:4px; border-bottom:1px solid var(--bg-border); }
.report-content :deep(.md-h3) { font-size:13px; font-weight:600; margin:8px 0 4px; color:var(--text-sec); }
.report-content :deep(.md-li) { padding-left:14px; position:relative; margin:3px 0; }
.report-content :deep(.md-li)::before { content:'•'; position:absolute; left:2px; color:var(--accent); }
.report-content :deep(.md-oli) { padding-left:4px; margin:3px 0; }
.report-content :deep(.inline-code) { background:rgba(255,255,255,.1); padding:1px 5px; border-radius:4px; font-family:monospace; font-size:12px; }
.report-content :deep(.md-hr) { border:none; border-top:1px solid var(--bg-border); margin:10px 0; }
.report-content :deep(.md-table) { border-collapse:collapse; width:100%; margin:10px 0; font-size:12px; }
.report-content :deep(.md-table th) { background:var(--bg-border); color:var(--text-sec); padding:7px 12px; text-align:left; font-weight:600; }
.report-content :deep(.md-table td) { padding:7px 12px; border-top:1px solid var(--bg-border); color:var(--text-main); font-family:var(--mono); }
.report-content :deep(.md-table tr:hover td) { background:rgba(255,255,255,.03); }
.dot-wave { display:inline-flex; gap:3px; align-items:center; }
.dot-wave span { width:5px; height:5px; border-radius:50%; background:var(--accent); display:inline-block; animation:dotBounce 1.2s infinite ease-in-out; }
.dot-wave span:nth-child(2) { animation-delay:.2s; }
.dot-wave span:nth-child(3) { animation-delay:.4s; }
@keyframes dotBounce { 0%,80%,100% { transform:translateY(0);opacity:.4; } 40% { transform:translateY(-5px);opacity:1; } }

.summary-table-wrap { border-radius:10px; overflow:hidden; border:1px solid var(--bg-border); }
.summary-table { width:100%; border-collapse:collapse; font-size:12px; }
.summary-table th { background:var(--bg-border); color:var(--text-sec); font-size:11px; font-weight:600; padding:8px 12px; text-align:center; }
.summary-table th:first-child { text-align:left; }
.th-group { border-left:1px solid rgba(255,255,255,.06); letter-spacing:.5px; }
.th-sub { font-weight:400; font-size:10px; border-left:1px solid rgba(255,255,255,.04); }
.summary-table td { padding:9px 12px; border-top:1px solid var(--bg-border); color:var(--text-main); font-family:var(--mono); text-align:center; }
.summary-table .td-name { font-family:inherit; color:var(--text-sec); text-align:left; }
.total-row td { font-weight:700; background:rgba(255,255,255,.03); border-top:2px solid var(--bg-border); }
.rate-badge { font-size:11px; font-weight:600; padding:2px 6px; border-radius:4px; }
.rate-badge.good { color:var(--green); background:rgba(16,185,129,.12); }
.rate-badge.warn { color:var(--amber); background:rgba(245,158,11,.12); }
.rate-badge.bad  { color:var(--red);   background:rgba(239,68,68,.12); }

.kpi-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 14px; margin-bottom: 16px; }
.kpi-card { background: var(--bg-card); border: 1px solid var(--bg-border); border-radius: 10px; padding: 16px 18px; position: relative; overflow: hidden; transition: border-color .2s; }
.kpi-card:hover { border-color: var(--accent); }
.kpi-card::after { content:''; position:absolute; top:0; left:0; right:0; height:2px; }
.kpi-card.k-contract::after { background: var(--blue); }
.kpi-card.k-revenue::after  { background: var(--green); }
.kpi-card.k-payment::after  { background: var(--accent); }
.kpi-label { font-size: 11px; color: var(--text-sec); letter-spacing: 1px; margin-bottom: 8px; }
.kpi-row { display: flex; align-items: baseline; gap: 4px; }
.kpi-value { font-family: var(--mono); font-size: 28px; font-weight: 700; }
.kpi-unit { font-size: 12px; color: var(--text-sec); }
.kpi-meta { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.kpi-rate { font-family: var(--mono); font-size: 13px; font-weight: 600; }
.kpi-rate.good { color: var(--green); } .kpi-rate.warn { color: var(--amber); } .kpi-rate.bad { color: var(--red); }
.kpi-yoy { font-size: 11px; color: var(--text-sec); }
.kpi-yoy .up { color: var(--green); } .kpi-yoy .down { color: var(--red); }
.kpi-progress { height: 3px; background: var(--bg-border); border-radius: 2px; margin-top: 10px; overflow: hidden; }
.kpi-bar { height: 100%; border-radius: 2px; transition: width 1.2s ease; }
.k-contract .kpi-bar { background: var(--blue); }
.k-revenue  .kpi-bar { background: var(--green); }
.k-payment  .kpi-bar { background: var(--accent); }

.card { background: var(--bg-card); border: 1px solid var(--bg-border); border-radius: 10px; padding: 18px 20px; }
.card-title { font-size: 11px; letter-spacing: 1.5px; color: var(--text-sec); text-transform: uppercase; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.card-title::before { content:''; display:block; width:3px; height:12px; border-radius:2px; background:var(--accent); }

.yoy-grid { display: grid; grid-template-columns: repeat(5,1fr); gap: 10px; }
.yoy-card { background: var(--bg-base); border: 1px solid var(--bg-border); border-radius: 8px; padding: 12px 14px; transition: border-color .15s; }
.yoy-card:hover { border-color: var(--accent); }
.yoy-div { font-size: 11px; color: var(--text-sec); margin-bottom: 6px; }
.yoy-val { font-family: var(--mono); font-size: 18px; font-weight: 700; }
.yoy-val.up { color: var(--green); } .yoy-val.down { color: var(--red); }
.yoy-label { font-size: 10px; color: var(--text-dim); margin-top: 2px; }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.heatmap { width: 100%; border-collapse: collapse; font-size: 12px; }
.heatmap th { padding: 6px 10px; color: var(--text-sec); font-weight: 500; border-bottom: 1px solid var(--bg-border); text-align: center; font-size: 11px; }
.heatmap td { padding: 9px 10px; border-bottom: 1px solid rgba(30,42,56,.5); text-align: center; }
.div-link { cursor: pointer; color: var(--text-pri); font-weight: 500; transition: color .15s; }
.div-link:hover { color: var(--accent); text-decoration: underline; }
.rate-cell { font-family: var(--mono); font-size: 12px; font-weight: 600; padding: 3px 7px; border-radius: 4px; }
.rate-cell.good { color: var(--green); background: rgba(16,185,129,.12); }
.rate-cell.warn { color: var(--amber); background: rgba(245,158,11,.12); }
.rate-cell.bad  { color: var(--red);   background: rgba(239,68,68,.12); }
.mono { font-family: var(--mono); }
.dim  { color: var(--text-sec); }
</style>
