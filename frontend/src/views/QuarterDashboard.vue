<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useAppStore } from '@/stores/app'
import { getQuarterly, getReports, saveReport, getReport, deleteReport } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const store   = useAppStore()
const loading = ref(false)
const data    = ref(null)
const quarter = ref('Q1')

const QUARTERS     = ['Q1', 'Q2', 'Q3', 'Q4']
const METRIC_LABEL = { contract: '合同', revenue: '收入', payment: '回款' }
const METRIC_COLOR = { contract: 'var(--blue)', revenue: 'var(--green)', payment: 'var(--accent)' }
const METRIC_CLS   = { contract: 'k-contract', revenue: 'k-revenue', payment: 'k-payment' }

// 初始化为当前季度
const curQ = (() => {
  const m = new Date().getMonth() + 1
  return m <= 3 ? 'Q1' : m <= 6 ? 'Q2' : m <= 9 ? 'Q3' : 'Q4'
})()
quarter.value = curQ

async function load() {
  loading.value = true
  const res = await getQuarterly(store.year, quarter.value)
  data.value = res?.data || null
  loading.value = false
}
onMounted(load)
watch([() => store.year, quarter], load)

function rateClass(r) { return r >= 80 ? 'good' : r >= 60 ? 'warn' : 'bad' }
function fmt(n) {
  const v = Number(n)
  return isNaN(v) ? '—' : v.toLocaleString('zh-CN')
}

// ── AI 季度经营分析报告 ───────────────────────────────
const report       = ref('')
const generating   = ref(false)
const reportModel  = ref('deepseek')
const saving       = ref(false)
const savedReports = ref([])
const showHistory  = ref(false)

const REPORT_MODELS = [
  { id: 'deepseek', label: 'DeepSeek' },
  { id: 'kimi',     label: 'Kimi' },
  { id: 'glm',      label: 'GLM' },
  { id: 'claude',   label: 'Claude Sonnet' },
]
const reportModelLabel = computed(() =>
  REPORT_MODELS.find(m => m.id === reportModel.value)?.label || reportModel.value
)

async function loadReports() {
  const res = await getReports()
  const all = res?.data || []
  // 只显示季度报告（标题含"季度"）
  savedReports.value = all.filter(r => r.title.includes('季度'))
}

async function generateReport() {
  report.value = ''
  generating.value = true
  const prompt = `请根据当前数据，生成${store.year}年${quarter.value}季度产品中心经营分析报告。请严格按以下格式输出：

## 总体情况
产品中心本季度合同/收入/回款的目标与完成情况，达成率评价。

## 各事业部分析
逐个分析4个事业部，每个事业部说明三项指标的季度完成情况，突出最强和最弱的指标。

## 主要风险
列出本季度达成率低于60%的事业部/指标，以及商机覆盖不足的领域。

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
        try { const chunk = JSON.parse(payload); if (chunk.text) report.value += chunk.text } catch {}
      }
    }
  } catch {
    report.value = '> 生成失败，请检查 API Key 配置或网络连接。'
  } finally {
    generating.value = false
  }
}

async function onSaveReport() {
  if (!report.value) return
  saving.value = true
  await saveReport({ year: store.year, title: `${store.year}年${quarter.value}季度经营分析报告`, content: report.value, model_id: reportModel.value })
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
    .replace(/\n\n+/g, '</p><p>')
    .replace(/\n/g, '<br>')
  text = '<p>' + text + '</p>'
  text = text.replace(/%%C(\d+)%%/g, (_, i) => `<pre><code>${codeBlocks[+i]}</code></pre>`)
  return text
}

onMounted(loadReports)

const centerMap = computed(() => {
  if (!data.value) return {}
  return Object.fromEntries(data.value.center.map(c => [c.metric_type, c]))
})

// 三个指标各自的横向完成率对比图
function makeBarOption(metric) {
  if (!data.value?.divisions) return {}
  const divs = data.value.divisions
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>${p[0].marker}${p[0].value}%` },
    grid: { left: 90, right: 40, top: 8, bottom: 8 },
    xAxis: { type: 'value', max: 130, axisLabel: { color: '#7a8fa6', fontSize: 10, formatter: '{value}%' }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    yAxis: { type: 'category', data: divs.map(d => d.business_unit_name.replace('事业部','')), axisLabel: { color: '#7a8fa6', fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{
      type: 'bar', barMaxWidth: 20,
      data: divs.map(d => {
        const r = d.metrics[metric]?.rate ?? 0
        return { value: r, itemStyle: { color: r >= 80 ? '#10b981' : r >= 60 ? '#f59e0b' : '#ef4444', borderRadius: [0,3,3,0] } }
      }),
      label: { show: true, position: 'right', color: '#7a8fa6', fontSize: 10, formatter: '{c}%' }
    }]
  }
}
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">

    <!-- Header -->
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px;flex-wrap:wrap">
      <span style="font-size:16px;font-weight:600">经营季度仪表盘</span>
      <el-radio-group v-model="quarter" size="small">
        <el-radio-button v-for="q in QUARTERS" :key="q" :value="q">{{ q }}</el-radio-button>
      </el-radio-group>
      <span v-if="data" style="font-size:12px;color:var(--text-sec)">
        {{ store.year }}年{{ quarter }} · 已过 {{ data.elapsed_months }}/3 个月
      </span>
    </div>

    <!-- 产品中心季度总览 -->
    <div class="section-label">产品中心季度目标完成情况</div>
    <div class="kpi-grid" v-if="data" style="margin-bottom:20px">
      <div
        v-for="metric in ['contract','revenue','payment']"
        :key="metric"
        class="kpi-card"
        :class="METRIC_CLS[metric]"
      >
        <div class="kpi-label">{{ METRIC_LABEL[metric] }} · {{ quarter }}</div>
        <div class="kpi-row">
          <span class="kpi-value">{{ fmt(centerMap[metric]?.quarter_actual) }}</span>
          <span class="kpi-unit">万元</span>
        </div>
        <div class="kpi-meta">
          <span class="kpi-rate" :class="rateClass(centerMap[metric]?.rate ?? 0)">
            {{ centerMap[metric]?.rate ?? 0 }}%
          </span>
          <span class="kpi-sub">季度目标 <b>{{ fmt(centerMap[metric]?.quarter_target) }}</b> 万</span>
        </div>
        <div class="kpi-progress">
          <div class="kpi-bar" :style="{ width: Math.min(centerMap[metric]?.rate ?? 0, 100) + '%' }" />
        </div>
        <div class="kpi-annual">年度目标 {{ fmt(centerMap[metric]?.annual_target) }} 万</div>
      </div>
    </div>

    <!-- 事业部经营指标完成情况表 -->
    <div class="section-label" v-if="data" style="margin-top:4px">事业部经营指标完成情况</div>
    <div class="summary-table-wrap" v-if="data" style="margin-bottom:20px">
      <table class="summary-table">
        <thead>
          <tr>
            <th>事业部</th>
            <th>合同（万元）</th><th>合同目标</th><th>合同完成率</th>
            <th>收入（万元）</th><th>收入目标</th><th>收入完成率</th>
            <th>回款（万元）</th><th>回款目标</th><th>回款完成率</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="div in data.divisions" :key="div.business_unit_id">
            <td class="td-name">{{ div.business_unit_name }}</td>
            <td>{{ fmt(div.metrics.contract?.quarter_actual) }}</td>
            <td class="td-target">{{ fmt(div.metrics.contract?.quarter_target) }}</td>
            <td><span :class="rateClass(div.metrics.contract?.rate ?? 0)">{{ div.metrics.contract?.rate ?? 0 }}%</span></td>
            <td>{{ fmt(div.metrics.revenue?.quarter_actual) }}</td>
            <td class="td-target">{{ fmt(div.metrics.revenue?.quarter_target) }}</td>
            <td><span :class="rateClass(div.metrics.revenue?.rate ?? 0)">{{ div.metrics.revenue?.rate ?? 0 }}%</span></td>
            <td>{{ fmt(div.metrics.payment?.quarter_actual) }}</td>
            <td class="td-target">{{ fmt(div.metrics.payment?.quarter_target) }}</td>
            <td><span :class="rateClass(div.metrics.payment?.rate ?? 0)">{{ div.metrics.payment?.rate ?? 0 }}%</span></td>
          </tr>
        </tbody>
        <tfoot>
          <tr class="total-row">
            <td>合计</td>
            <td>{{ fmt(centerMap.contract?.quarter_actual) }}</td>
            <td class="td-target">{{ fmt(centerMap.contract?.quarter_target) }}</td>
            <td><span :class="rateClass(centerMap.contract?.rate ?? 0)">{{ centerMap.contract?.rate ?? 0 }}%</span></td>
            <td>{{ fmt(centerMap.revenue?.quarter_actual) }}</td>
            <td class="td-target">{{ fmt(centerMap.revenue?.quarter_target) }}</td>
            <td><span :class="rateClass(centerMap.revenue?.rate ?? 0)">{{ centerMap.revenue?.rate ?? 0 }}%</span></td>
            <td>{{ fmt(centerMap.payment?.quarter_actual) }}</td>
            <td class="td-target">{{ fmt(centerMap.payment?.quarter_target) }}</td>
            <td><span :class="rateClass(centerMap.payment?.rate ?? 0)">{{ centerMap.payment?.rate ?? 0 }}%</span></td>
          </tr>
        </tfoot>
      </table>
    </div>

    <!-- AI 季度经营分析报告 -->
    <div class="ai-report-block" v-if="data">
      <div class="report-header">
        <div class="report-header-left">
          <div class="section-label" style="margin-bottom:0">AI 季度经营分析报告</div>
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

    <!-- 事业部完成率横向对比 -->
    <div class="section-label" v-if="data">各事业部指标完成率对比</div>
    <div class="three-col" v-if="data" style="margin-bottom:20px">
      <div v-for="metric in ['contract','revenue','payment']" :key="metric" class="card">
        <div class="chart-metric-title" :style="{ color: METRIC_COLOR[metric] }">{{ METRIC_LABEL[metric] }}</div>
        <v-chart :option="makeBarOption(metric)" style="height:160px" autoresize />
      </div>
    </div>

    <!-- 各事业部季度明细 -->
    <div class="section-label">各事业部季度指标完成情况</div>
    <div class="div-grid" v-if="data">
      <div v-for="div in data.divisions" :key="div.business_unit_id" class="div-card">
        <div class="div-name">{{ div.business_unit_name.replace('事业部','') }}</div>
        <div class="metrics-row">
          <div v-for="metric in ['contract','revenue','payment']" :key="metric" class="metric-block">
            <div class="mb-label" :style="{ color: METRIC_COLOR[metric] }">{{ METRIC_LABEL[metric] }}</div>
            <div class="mb-actual">{{ fmt(div.metrics[metric]?.quarter_actual) }}</div>
            <div class="mb-target">/ {{ fmt(div.metrics[metric]?.quarter_target) }} 万</div>
            <div class="mb-rate-bar">
              <div
                class="mb-bar"
                :style="{
                  width: Math.min(div.metrics[metric]?.rate ?? 0, 100) + '%',
                  background: METRIC_COLOR[metric]
                }"
              />
            </div>
            <div class="mb-rate" :class="rateClass(div.metrics[metric]?.rate ?? 0)">
              {{ div.metrics[metric]?.rate ?? 0 }}%
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-if="!loading && !data" description="暂无数据" />
  </div>
</template>

<style scoped>
.section-label {
  font-size: 11px; letter-spacing: 1.5px; color: var(--text-sec);
  text-transform: uppercase; margin-bottom: 12px;
  display: flex; align-items: center; gap: 8px;
}
.section-label::before { content:''; display:block; width:3px; height:12px; border-radius:2px; background:var(--accent); }
.card { background: var(--bg-card); border: 1px solid var(--bg-border); border-radius: 10px; padding: 18px 20px; }

/* KPI cards */
.kpi-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 14px; }
.kpi-card { background: var(--bg-card); border: 1px solid var(--bg-border); border-radius: 10px; padding: 16px 18px; position: relative; overflow: hidden; }
.kpi-card::after { content:''; position:absolute; top:0; left:0; right:0; height:2px; }
.kpi-card.k-contract::after { background: var(--blue); }
.kpi-card.k-revenue::after  { background: var(--green); }
.kpi-card.k-payment::after  { background: var(--accent); }
.kpi-label { font-size: 11px; color: var(--text-sec); letter-spacing: 1px; margin-bottom: 8px; }
.kpi-row   { display: flex; align-items: baseline; gap: 4px; }
.kpi-value { font-family: var(--mono); font-size: 28px; font-weight: 700; }
.kpi-unit  { font-size: 12px; color: var(--text-sec); }
.kpi-meta  { display: flex; align-items: center; gap: 10px; margin-top: 8px; }
.kpi-rate  { font-family: var(--mono); font-size: 13px; font-weight: 600; }
.kpi-rate.good { color: var(--green); } .kpi-rate.warn { color: var(--amber); } .kpi-rate.bad { color: var(--red); }
.kpi-sub   { font-size: 11px; color: var(--text-sec); }
.kpi-progress { height: 3px; background: var(--bg-border); border-radius: 2px; margin-top: 10px; overflow: hidden; }
.kpi-bar   { height: 100%; border-radius: 2px; transition: width 1.2s ease; }
.k-contract .kpi-bar { background: var(--blue); }
.k-revenue  .kpi-bar { background: var(--green); }
.k-payment  .kpi-bar { background: var(--accent); }
.kpi-annual { font-size: 10px; color: var(--text-dim); margin-top: 6px; }

/* 事业部汇总表 */
.summary-table-wrap { border-radius:10px; overflow:hidden; border:1px solid var(--bg-border); }
.summary-table { width:100%; border-collapse:collapse; font-size:13px; }
.summary-table th { background:var(--bg-border); color:var(--text-sec); font-size:11px; font-weight:600; letter-spacing:.5px; padding:10px 14px; text-align:left; }
.summary-table td { padding:10px 14px; border-top:1px solid var(--bg-border); color:var(--text-main); font-family:var(--mono); }
.summary-table .td-name { font-family:inherit; color:var(--text-sec); }
.summary-table .td-target { color:var(--text-dim); font-size:12px; }
.summary-table .good { color:var(--green); font-weight:600; }
.summary-table .warn { color:var(--amber); font-weight:600; }
.summary-table .bad  { color:var(--red);   font-weight:600; }
.total-row td { font-weight:700; background:rgba(255,255,255,.03); border-top:2px solid var(--bg-border); }

/* Division cards */
.div-grid { display: grid; grid-template-columns: repeat(2,1fr); gap: 12px; }
.three-col { display: grid; grid-template-columns: repeat(3,1fr); gap: 14px; }
.chart-metric-title { font-size: 12px; font-weight: 600; letter-spacing: 1px; margin-bottom: 4px; }
.div-card { background: var(--bg-card); border: 1px solid var(--bg-border); border-radius: 10px; padding: 14px 16px; }
.div-name { font-size: 13px; font-weight: 600; color: var(--accent); margin-bottom: 12px; }
.metrics-row { display: grid; grid-template-columns: repeat(3,1fr); gap: 10px; }
.metric-block { display: flex; flex-direction: column; gap: 2px; }
.mb-label  { font-size: 10px; letter-spacing: 1px; font-weight: 600; margin-bottom: 4px; }
.mb-actual { font-family: var(--mono); font-size: 18px; font-weight: 700; color: var(--text-pri); }
.mb-target { font-size: 10px; color: var(--text-dim); }
.mb-rate-bar { height: 3px; background: var(--bg-border); border-radius: 2px; margin: 5px 0; overflow: hidden; }
.mb-bar    { height: 100%; border-radius: 2px; transition: width 1.2s ease; opacity: .7; }
.mb-rate   { font-family: var(--mono); font-size: 11px; font-weight: 600; }
.mb-rate.good { color: var(--green); } .mb-rate.warn { color: var(--amber); } .mb-rate.bad { color: var(--red); }

/* AI 报告区块 */
.ai-report-block { margin-bottom:16px; background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:16px 20px; }
.report-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:12px; }
.report-header-left { display:flex; align-items:center; gap:8px; }
.report-controls { display:flex; align-items:center; gap:8px; }
.history-badge { font-size:11px; padding:2px 8px; border-radius:10px; background:rgba(240,165,0,.15); color:var(--accent); cursor:pointer; border:1px solid rgba(240,165,0,.25); }
.history-badge:hover { background:rgba(240,165,0,.25); }
.model-select { font-size:11px; padding:3px 8px; border-radius:6px; background:rgba(240,165,0,.1); color:var(--accent); border:1px solid rgba(240,165,0,.25); outline:none; cursor:pointer; }
.model-select:disabled { opacity:.5; }
.model-select option { background:var(--bg-card); color:var(--text-main); }
.gen-btn { font-size:12px; padding:5px 14px; border-radius:6px; border:none; cursor:pointer; background:var(--accent); color:#000; font-weight:600; display:flex; align-items:center; gap:6px; }
.gen-btn:disabled { opacity:.5; cursor:not-allowed; }
.gen-btn:not(:disabled):hover { opacity:.85; }
.save-btn { font-size:12px; padding:5px 12px; border-radius:6px; border:1px solid var(--accent); background:transparent; color:var(--accent); cursor:pointer; }
.save-btn:not(:disabled):hover { background:rgba(240,165,0,.1); }
.save-btn:disabled { opacity:.5; cursor:not-allowed; }
.clear-btn { font-size:11px; padding:5px 10px; border-radius:6px; border:1px solid var(--bg-border); background:transparent; color:var(--text-sec); cursor:pointer; }
.clear-btn:hover { color:var(--red); border-color:var(--red); }
.history-panel { background:var(--bg-base); border:1px solid var(--bg-border); border-radius:8px; margin-bottom:12px; overflow:hidden; }
.history-item { display:flex; align-items:center; justify-content:space-between; padding:9px 14px; border-bottom:1px solid var(--bg-border); }
.history-item:last-child { border-bottom:none; }
.history-info { flex:1; cursor:pointer; }
.history-info:hover .history-title { color:var(--accent); }
.history-title { font-size:12px; color:var(--text-main); display:block; }
.history-meta { font-size:11px; color:var(--text-sec); }
.del-btn { background:none; border:none; color:var(--text-sec); cursor:pointer; font-size:16px; padding:0 4px; }
.del-btn:hover { color:var(--red); }
.report-thinking { display:flex; align-items:center; gap:8px; font-size:12px; color:var(--accent); padding:12px 0; }
.report-content { font-size:13px; line-height:1.3; color:var(--text-main); padding-top:4px; }
.report-content :deep(p) { margin: 0; }
.report-content :deep(p + p) { margin-top: 2px; }
.report-content :deep(.md-h2) { font-size:14px; font-weight:700; margin:2px 0 0px; color:var(--accent); }
.report-content :deep(.md-h3) { font-size:13px; font-weight:600; margin:2px 0 0px; color:var(--text-sec); }
.report-content :deep(.md-li) { padding-left:14px; position:relative; margin:0px 0; }
.report-content :deep(.md-li)::before { content:'•'; position:absolute; left:2px; color:var(--accent); }
.report-content :deep(.md-hr) { border:none; border-top:1px solid var(--bg-border); margin:2px 0; }
.report-content :deep(.md-table) { border-collapse:collapse; width:100%; margin:2px 0; font-size:12px; }
.report-content :deep(.md-table th) { background:var(--bg-border); color:var(--text-sec); padding:4px 8px; text-align:left; font-weight:600; }
.report-content :deep(.md-table td) { padding:4px 8px; border-top:1px solid var(--bg-border); color:var(--text-main); font-family:var(--mono); }
.report-content :deep(.md-table tr:hover td) { background:rgba(255,255,255,.03); }
.report-content :deep(pre) { background: rgba(0,0,0,.3); border-radius: 6px; padding: 8px 10px; margin: 2px 0; overflow-x: auto; }
.report-content :deep(pre code) { font-size: 11px; font-family: monospace; }
.report-content :deep(.inline-code) { background:rgba(255,255,255,.1); padding:1px 5px; border-radius:4px; font-family:monospace; font-size:12px; }
.report-content :deep(br) { display: none; }
.dot-wave { display:inline-flex; gap:3px; align-items:center; }
.dot-wave span { width:5px; height:5px; border-radius:50%; background:var(--accent); display:inline-block; animation:dotBounce 1.2s infinite ease-in-out; }
.dot-wave span:nth-child(2) { animation-delay:.2s; } .dot-wave span:nth-child(3) { animation-delay:.4s; }
@keyframes dotBounce { 0%,80%,100%{transform:translateY(0);opacity:.4;} 40%{transform:translateY(-5px);opacity:1;} }
</style>
