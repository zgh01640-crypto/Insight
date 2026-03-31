<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { getOppSupport, getOpportunities } from '@/api'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
use([BarChart, GridComponent, TooltipComponent, MarkLineComponent, CanvasRenderer])

const store   = useAppStore()
const loading = ref(false)
const data    = ref(null)
const quarter = ref('Q1')

const METRIC_LABEL = { contract: '合同', revenue: '收入', payment: '回款' }
const METRICS      = ['contract', 'revenue', 'payment']
const QUARTERS     = ['Q1', 'Q2', 'Q3', 'Q4']
const METRIC_COLORS = { contract: '#3b82f6', revenue: '#10b981', payment: '#f0a500' }

const m0 = new Date().getMonth() + 1
quarter.value = m0 <= 3 ? 'Q1' : m0 <= 6 ? 'Q2' : m0 <= 9 ? 'Q3' : 'Q4'

const opps      = ref([])
const divMetric = ref({})
const getDivMetric = (name) => divMetric.value[name] || 'contract'
const setDivMetric = (name, m) => { divMetric.value = { ...divMetric.value, [name]: m } }

async function load() {
  loading.value = true
  const [suppRes, oppsRes] = await Promise.all([
    getOppSupport(store.year, quarter.value),
    getOpportunities({ year: store.year, quarter: quarter.value }),
  ])
  data.value = suppRes?.data || null
  opps.value = oppsRes?.data || []
  loading.value = false
}

const filteredOpps = (unitName) =>
  opps.value.filter(o => o.business_unit_name === unitName && o.metric_type === getDivMetric(unitName))

const STATUS_COLOR = { '进行中': 'var(--blue)', '已赢单': 'var(--green)', '已输单': 'var(--red)', '已搁置': 'var(--text-sec)' }
onMounted(load)
watch([() => store.year, quarter], load)

const EMPTY_METRIC = { quarter_actual: 0, quarter_target: 0, gap: 0, opp_active_total: 0, cover_rate: 0, div_coverage: [], count: 0 }
const safeMetric = (m) => data.value?.metrics?.[m] || EMPTY_METRIC

// 排名图（单指标）— 按完成率降序
function rankChartOption(metric) {
  const divs = [...(safeMetric(metric).div_coverage || [])]
    .filter(d => d.quarter_target > 0)
    .sort((a, b) => b.cover_rate - a.cover_rate)
  if (!divs.length) return {}
  const names = divs.map(d => d.name.replace('事业部', ''))
  const rates = divs.map(d => d.cover_rate)
  const color = METRIC_COLORS[metric]
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: p => {
        const d = divs[p[0].dataIndex]
        return `${d.name}<br/>商机 ${fmt(d.opp_total)} 万<br/>目标 ${fmt(d.quarter_target)} 万<br/>完成率 <b>${d.cover_rate}%</b>`
      }
    },
    grid: { left: 72, right: 60, top: 10, bottom: 4 },
    xAxis: {
      type: 'value', max: v => Math.max(v.max * 1.15, 120),
      axisLabel: { color: '#7a8fa6', fontSize: 10, formatter: v => v + '%' },
      splitLine: { lineStyle: { color: '#1e2a38' } },
    },
    yAxis: {
      type: 'category', data: names,
      axisLabel: { color: '#9ab', fontSize: 11 },
      axisLine: { show: false }, axisTick: { show: false },
    },
    series: [{
      type: 'bar', barMaxWidth: 18, data: rates,
      itemStyle: { color, borderRadius: [0, 3, 3, 0] },
      label: { show: true, position: 'right', color: '#9ab', fontSize: 10, formatter: p => p.value + '%' },
      markLine: {
        silent: true, symbol: 'none',
        data: [{ xAxis: 100, lineStyle: { color: '#f0a500', type: 'dashed', width: 1 } }],
        label: { show: false },
      },
    }]
  }
}

// 完成值排名图（单指标）— 按 opp_total 降序
function valueChartOption(metric) {
  const divs = [...(safeMetric(metric).div_coverage || [])]
    .sort((a, b) => b.opp_total - a.opp_total)
  if (!divs.length) return {}
  const names = divs.map(d => d.name.replace('事业部', ''))
  const vals  = divs.map(d => d.opp_total)
  const color = METRIC_COLORS[metric]
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: p => {
        const d = divs[p[0].dataIndex]
        return `${d.name}<br/>进行中商机 <b>${fmt(d.opp_total)} 万</b>`
      }
    },
    grid: { left: 72, right: 70, top: 10, bottom: 4 },
    xAxis: {
      type: 'value', max: v => Math.max(v.max * 1.15, 10),
      axisLabel: { color: '#7a8fa6', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1e2a38' } },
    },
    yAxis: {
      type: 'category', data: names,
      axisLabel: { color: '#9ab', fontSize: 11 },
      axisLine: { show: false }, axisTick: { show: false },
    },
    series: [{
      type: 'bar', barMaxWidth: 18, data: vals,
      itemStyle: { color: color + 'bb', borderRadius: [0, 3, 3, 0] },
      label: { show: true, position: 'right', color: '#9ab', fontSize: 10, formatter: p => fmt(p.value) + ' 万' },
    }]
  }
}

function rateColor(r) { return r >= 100 ? 'var(--green)' : r >= 60 ? 'var(--amber)' : 'var(--red)' }
function fmt(n) {
  const v = Number(n)
  return isNaN(v) ? '—' : v.toLocaleString('zh-CN')
}
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <!-- 标题栏 -->
    <div class="section-header">
      <span class="section-title">商机分析</span>
      <el-radio-group v-model="quarter" size="small" @change="load">
        <el-radio-button v-for="q in QUARTERS" :key="q" :value="q">{{ q }}</el-radio-button>
      </el-radio-group>
      <span v-if="data" style="font-size:12px;color:var(--text-sec)">
        {{ store.year }}年{{ data.quarter }} · {{ data.total_count }}条商机
      </span>
    </div>

    <template v-if="data && data.metrics">
      <!-- 产品中心三指标覆盖率概览 -->
      <div class="center-row">
        <div v-for="m in METRICS" :key="m" class="center-card">
          <div class="cc-label">{{ METRIC_LABEL[m] }}</div>
          <div class="cc-rate" :style="{ color: rateColor(safeMetric(m).cover_rate) }">
            {{ safeMetric(m).cover_rate >= 999 ? '100+' : safeMetric(m).cover_rate }}<span class="cc-pct">%</span>
          </div>
          <div class="cc-sub">商机完成率</div>
          <div class="cc-detail">
            商机 <b>{{ fmt(safeMetric(m).opp_active_total) }}</b> 万
            &nbsp;/&nbsp;
            目标 <b>{{ fmt(safeMetric(m).quarter_target) }}</b> 万
          </div>
        </div>
      </div>

      <!-- 三指标事业部完成率排名图 -->
      <div class="rank-grid" style="margin-bottom:12px">
        <div v-for="m in METRICS" :key="m" class="card">
          <div class="card-title" :style="{ '--dot-color': METRIC_COLORS[m] }">
            {{ METRIC_LABEL[m] }} · 事业部商机完成率排名
          </div>
          <v-chart :option="rankChartOption(m)" style="height:160px" autoresize />
        </div>
      </div>

      <!-- 三指标事业部完成值排名图 -->
      <div class="rank-grid" style="margin-bottom:12px">
        <div v-for="m in METRICS" :key="m" class="card">
          <div class="card-title" :style="{ '--dot-color': METRIC_COLORS[m] }">
            {{ METRIC_LABEL[m] }} · 事业部商机完成值排名
          </div>
          <v-chart :option="valueChartOption(m)" style="height:160px" autoresize />
        </div>
      </div>

      <!-- 商机列表 -->
      <div class="card">
        <div class="card-title">季度商机列表</div>
        <div v-for="div in (safeMetric('contract').div_coverage || [])" :key="div.name" class="div-section">
          <div class="div-section-header">
            <span class="div-section-title">{{ div.name.replace('事业部','') }}</span>
            <el-radio-group :model-value="getDivMetric(div.name)" size="small" @update:model-value="v => setDivMetric(div.name, v)">
              <el-radio-button v-for="m in METRICS" :key="m" :value="m">{{ METRIC_LABEL[m] }}</el-radio-button>
            </el-radio-group>
          </div>
          <el-table :data="filteredOpps(div.name)" size="small" :row-class-name="() => 'opp-row'">
            <el-table-column prop="name" label="商机名称" min-width="200" show-overflow-tooltip />
            <el-table-column prop="estimated_amount" label="预估金额(万)" width="110" align="right" sortable>
              <template #default="{ row }">{{ fmt(row.estimated_amount) }}</template>
            </el-table-column>
            <el-table-column prop="stage" label="阶段" width="90" />
            <el-table-column prop="status" label="状态" width="80">
              <template #default="{ row }">
                <span :style="{ color: STATUS_COLOR[row.status] }">{{ row.status }}</span>
              </template>
            </el-table-column>
          </el-table>
          <div class="div-total">
            合计 <span class="mono">{{ fmt(filteredOpps(div.name).reduce((s, o) => s + o.estimated_amount, 0)) }}</span> 万
          </div>
        </div>
      </div>
    </template>

    <el-empty v-if="!loading && !data" description="暂无商机数据" />
  </div>
</template>

<style scoped>
.section-header { display:flex; align-items:center; gap:10px; margin-bottom:16px; flex-wrap:wrap; }
.section-title  { font-size:16px; font-weight:600; }

/* 产品中心概览 */
.center-row  { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:16px; }
.center-card {
  background:var(--bg-card); border:1px solid var(--bg-border);
  border-radius:10px; padding:18px 20px;
}
.cc-label  { font-size:11px; color:var(--text-sec); letter-spacing:1px; margin-bottom:8px; }
.cc-rate   { font-family:var(--mono); font-size:32px; font-weight:700; line-height:1; }
.cc-pct    { font-size:16px; font-weight:400; margin-left:2px; }
.cc-sub    { font-size:11px; color:var(--text-sec); margin-top:4px; margin-bottom:8px; }
.cc-detail { font-size:11px; color:var(--text-dim); }
.cc-detail b { color:var(--text-main); font-family:var(--mono); }

/* 排名图区 */
.rank-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:16px 18px; }
.card-title {
  font-size:11px; letter-spacing:1.5px; color:var(--text-sec);
  margin-bottom:10px; display:flex; align-items:center; gap:8px;
}
.card-title::before {
  content:''; display:block; width:3px; height:12px; border-radius:2px;
  background: var(--dot-color, var(--accent));
}
.list-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:2px; }
.div-section { margin-top:16px; }
.div-section-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:6px; }
.div-section-title { font-size:11px; font-weight:600; color:var(--text-sec); letter-spacing:1px; padding-left:2px; }
.div-total { text-align:right; font-size:11px; color:var(--text-sec); padding:6px 4px 0; }
</style>
