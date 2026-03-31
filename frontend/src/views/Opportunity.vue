<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useAppStore } from '@/stores/app'
import { getOppSupport } from '@/api'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
use([BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const store        = useAppStore()
const loading      = ref(false)
const data         = ref(null)
const activeMetric = ref('contract')
const quarter      = ref('Q1')

const METRIC_LABEL = { contract: '合同', revenue: '收入', payment: '回款' }
const METRICS      = ['contract', 'revenue', 'payment']
const QUARTERS     = ['Q1', 'Q2', 'Q3', 'Q4']

// 默认当前季度
const m0 = new Date().getMonth() + 1
quarter.value = m0 <= 3 ? 'Q1' : m0 <= 6 ? 'Q2' : m0 <= 9 ? 'Q3' : 'Q4'

async function load() {
  loading.value = true
  const res = await getOppSupport(store.year, quarter.value)
  data.value = res?.data || null
  loading.value = false
}
onMounted(load)
watch([() => store.year, quarter], load)

const EMPTY_METRIC = { quarter_actual: 0, quarter_target: 0, gap: 0, opp_active_total: 0, cover_rate: 0, funnel: [], div_dist: {}, count: 0 }

const cur = computed(() =>
  data.value?.metrics?.[activeMetric.value] ?? EMPTY_METRIC
)

const safeMetric = (m) => data.value?.metrics?.[m] || EMPTY_METRIC

const funnelMax = computed(() =>
  cur.value ? Math.max(...cur.value.funnel.map(f => f.total_amount), 1) : 1
)

// 事业部商机分布横向柱图
const divBarOption = computed(() => {
  const dist  = cur.value?.div_dist || {}
  const names = Object.keys(dist)
  const vals  = Object.values(dist)
  if (!names.length) return {}
  const maxVal = Math.max(...vals, 1)
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>${p[0].marker}${p[0].value.toLocaleString()} 万` },
    grid: { left: 110, right: 50, top: 8, bottom: 8 },
    xAxis: { type: 'value', axisLabel: { color: '#7a8fa6', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    yAxis: { type: 'category', data: names.map(n => n.replace('事业部','')), axisLabel: { color: '#7a8fa6', fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{
      type: 'bar', barMaxWidth: 20,
      data: vals.map((v, i) => ({ value: v, itemStyle: { color: ['#3b82f6','#10b981','#f0a500','#8b5cf6'][i % 4], borderRadius: [0,3,3,0] } })),
      label: { show: true, position: 'right', color: '#7a8fa6', fontSize: 10, formatter: p => p.value.toLocaleString() + ' 万' }
    }]
  }
})

const STAGE_COLORS = { '线索': '#3b82f6', '立项': '#8b5cf6', '报价': '#f59e0b', '签约跟进': '#10b981', '已完成': '#34d399' }

function rateColor(r) { return r >= 100 ? 'var(--green)' : r >= 60 ? 'var(--amber)' : 'var(--red)' }
function fmt(n) {
  const v = Number(n)
  return isNaN(v) ? '—' : v.toLocaleString('zh-CN')
}
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <div class="section-header">
      <span class="section-title">商机支撑分析</span>
      <el-radio-group v-model="quarter" size="small" @change="load">
        <el-radio-button v-for="q in QUARTERS" :key="q" :value="q">{{ q }}</el-radio-button>
      </el-radio-group>
      <el-radio-group v-model="activeMetric" size="small" style="margin-left:8px">
        <el-radio-button v-for="m in METRICS" :key="m" :value="m">{{ METRIC_LABEL[m] }}</el-radio-button>
      </el-radio-group>
      <span v-if="data" style="font-size:12px;color:var(--text-sec);margin-left:4px">
        {{ store.year }}年{{ data.quarter }} · {{ data.total_count }}条商机
      </span>
    </div>

    <!-- 三指标概览行 -->
    <div class="metric-overview" v-if="data && data.metrics" style="margin-bottom:14px">
      <div
        v-for="m in METRICS" :key="m"
        class="metric-card"
        :class="{ active: activeMetric === m }"
        @click="activeMetric = m"
      >
        <div class="mc-label">{{ METRIC_LABEL[m] }}</div>
        <div class="mc-row">
          <span class="mc-rate" :style="{ color: rateColor(safeMetric(m).cover_rate) }">
            {{ safeMetric(m).cover_rate >= 999 ? '100+' : safeMetric(m).cover_rate }}%
          </span>
          <span class="mc-sub">覆盖率</span>
        </div>
        <div class="mc-gap">缺口 <span class="mono">{{ fmt(safeMetric(m).gap) }}</span> 万</div>
        <div class="mc-opp">商机 <span class="mono">{{ fmt(safeMetric(m).opp_active_total) }}</span> 万（{{ safeMetric(m).count }}条）</div>
      </div>
    </div>

    <!-- 详细面板（按当前选中指标）-->
    <div v-if="data && data.metrics">
      <!-- KPI -->
      <div class="kpi-grid" style="margin-bottom:14px">
        <div class="kpi-card k-contract">
          <div class="kpi-label">{{ METRIC_LABEL[activeMetric] }} 进行中商机</div>
          <div class="kpi-row"><span class="kpi-value">{{ fmt(cur.opp_active_total) }}</span><span class="kpi-unit">万元</span></div>
          <div class="kpi-meta"><span class="kpi-yoy">共 <b>{{ cur.count }}</b> 条商机</span></div>
        </div>
        <div class="kpi-card k-revenue">
          <div class="kpi-label">{{ METRIC_LABEL[activeMetric] }} 缺口覆盖率</div>
          <div class="kpi-row">
            <span class="kpi-value" :style="{ color: rateColor(cur.cover_rate) }">
              {{ cur.cover_rate >= 999 ? '100+' : cur.cover_rate }}
            </span>
            <span class="kpi-unit">%</span>
          </div>
          <div class="kpi-meta"><span class="kpi-yoy">进行中商机 / 季度缺口</span></div>
        </div>
        <div class="kpi-card k-payment">
          <div class="kpi-label">{{ METRIC_LABEL[activeMetric] }} 季度缺口</div>
          <div class="kpi-row"><span class="kpi-value">{{ fmt(cur.gap) }}</span><span class="kpi-unit">万元</span></div>
          <div class="kpi-meta"><span class="kpi-yoy">季度目标 {{ fmt(cur.quarter_target) }} · 完成 {{ fmt(cur.quarter_actual) }}</span></div>
        </div>
      </div>

      <!-- 漏斗 + 季度分布 -->
      <div class="two-col">
        <div class="card">
          <div class="card-title">{{ METRIC_LABEL[activeMetric] }} · 商机阶段漏斗</div>
          <div class="funnel-list">
            <div v-for="f in cur.funnel" :key="f.stage" class="funnel-item">
              <span class="funnel-label">{{ f.stage }}</span>
              <div class="funnel-track">
                <div
                  class="funnel-bar"
                  :style="{ width: (f.total_amount / funnelMax * 100) + '%', background: STAGE_COLORS[f.stage] }"
                >{{ f.total_amount > 0 ? fmt(f.total_amount) + '万' : '' }}</div>
              </div>
              <span class="funnel-count">{{ f.count }}条</span>
            </div>
          </div>
        </div>
        <div class="card">
          <div class="card-title">{{ METRIC_LABEL[activeMetric] }} · 事业部商机分布</div>
          <v-chart :option="divBarOption" style="height:200px" autoresize />
        </div>
      </div>
    </div>

    <el-empty v-if="!loading && !data" description="暂无商机数据" />
  </div>
</template>

<style scoped>
.section-header { display:flex; align-items:center; gap:10px; margin-bottom:16px; flex-wrap:wrap; }
.section-title { font-size:16px; font-weight:600; }
.section-sub { font-size:12px; color:var(--text-sec); }

/* 三指标概览 */
.metric-overview { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; }
.metric-card {
  background:var(--bg-card); border:1px solid var(--bg-border);
  border-radius:10px; padding:14px 16px; cursor:pointer;
  transition: border-color .15s;
}
.metric-card:hover { border-color: var(--accent); }
.metric-card.active { border-color: var(--accent); background: rgba(240,165,0,.06); }
.mc-label { font-size:11px; color:var(--text-sec); margin-bottom:6px; letter-spacing:1px; }
.mc-row { display:flex; align-items:baseline; gap:6px; margin-bottom:4px; }
.mc-rate { font-family:var(--mono); font-size:22px; font-weight:700; }
.mc-sub { font-size:11px; color:var(--text-sec); }
.mc-gap { font-size:11px; color:var(--text-sec); margin-top:2px; }
.mc-opp { font-size:11px; color:var(--text-dim); margin-top:1px; }

/* KPI */
.kpi-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
.kpi-card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:16px 18px; position:relative; overflow:hidden; }
.kpi-card::after { content:''; position:absolute; top:0; left:0; right:0; height:2px; }
.kpi-card.k-contract::after { background:var(--blue); } .kpi-card.k-revenue::after { background:var(--green); } .kpi-card.k-payment::after { background:var(--accent); }
.kpi-label { font-size:11px; color:var(--text-sec); margin-bottom:8px; }
.kpi-row { display:flex; align-items:baseline; gap:4px; }
.kpi-value { font-family:var(--mono); font-size:26px; font-weight:700; }
.kpi-unit { font-size:12px; color:var(--text-sec); }
.kpi-meta { margin-top:8px; font-size:11px; color:var(--text-sec); }

.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:18px 20px; }
.card-title { font-size:11px; letter-spacing:1.5px; color:var(--text-sec); text-transform:uppercase; margin-bottom:14px; display:flex; align-items:center; gap:8px; }
.card-title::before { content:''; display:block; width:3px; height:12px; border-radius:2px; background:var(--accent); }
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
.funnel-list { display:flex; flex-direction:column; gap:10px; }
.funnel-item { display:flex; align-items:center; gap:10px; }
.funnel-label { width:65px; font-size:11px; color:var(--text-sec); flex-shrink:0; }
.funnel-track { flex:1; background:var(--bg-border); border-radius:3px; height:24px; overflow:hidden; }
.funnel-bar { height:100%; border-radius:3px; display:flex; align-items:center; padding-left:8px; font-family:var(--mono); font-size:11px; font-weight:600; color:#000; transition:width 1s ease; min-width:2%; }
.funnel-count { width:36px; text-align:right; font-family:var(--mono); font-size:11px; color:var(--text-sec); }
.mono { font-family:var(--mono); }
</style>
