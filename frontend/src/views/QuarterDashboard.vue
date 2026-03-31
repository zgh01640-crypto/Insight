<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useAppStore } from '@/stores/app'
import { getQuarterly } from '@/api'
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
</style>
