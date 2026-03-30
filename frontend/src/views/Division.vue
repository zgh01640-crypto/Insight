<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { getDivisionDetail } from '@/api'
import { use } from 'echarts/core'
import { LineChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent, MarkLineComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, MarkLineComponent, CanvasRenderer])

const route  = useRoute()
const router = useRouter()
const store  = useAppStore()
const loading = ref(false)
const detail  = ref(null)

const METRICS = ['contract', 'revenue', 'payment']
const LABEL   = { contract: '合同', revenue: '收入', payment: '回款' }
const COLOR   = { contract: '#3b82f6', revenue: '#10b981', payment: '#f0a500' }
const MONTHS  = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']

async function load() {
  loading.value = true
  const res = await getDivisionDetail(route.params.id, store.year)
  detail.value = res?.data || null
  loading.value = false
}

onMounted(load)
watch([() => route.params.id, () => store.year], load)

function rateClass(r) { return r >= 80 ? 'good' : r >= 60 ? 'warn' : 'bad' }
function fmt(n) { return n != null ? n.toLocaleString('zh-CN') : '—' }

const curMonth = computed(() => detail.value?.cur_month || store.curMonth)

const trendOption = computed(() => {
  if (!detail.value) return {}
  const m = detail.value.metrics
  const datasets = METRICS.map(k => ({
    name: LABEL[k],
    type: 'line', smooth: true,
    data: m[k].monthly_actual.map((v, i) => i < curMonth.value ? v : null),
    lineStyle: { color: COLOR[k], width: 2 },
    itemStyle: { color: COLOR[k] },
    areaStyle: k === 'contract' ? { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(59,130,246,.2)' }, { offset: 1, color: 'transparent' }] } } : undefined,
    symbol: 'circle', symbolSize: 4,
  }))
  datasets.push({
    name: '合同目标', type: 'line',
    data: m.contract.monthly_target.map((v, i) => i < curMonth.value ? v : null),
    lineStyle: { color: 'rgba(59,130,246,.4)', type: 'dashed', width: 1 },
    itemStyle: { color: 'rgba(59,130,246,.4)' },
    symbol: 'none',
  })
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#7a8fa6', fontSize: 11 }, top: 0 },
    grid: { left: 50, right: 20, top: 35, bottom: 20 },
    xAxis: { type: 'category', data: MONTHS, axisLabel: { color: '#7a8fa6', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    yAxis: { type: 'value', axisLabel: { color: '#7a8fa6', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    series: datasets,
  }
})

const rateOption = computed(() => {
  if (!detail.value) return {}
  const rates = detail.value.metrics.contract.monthly_actual.map((v, i) => {
    if (i >= curMonth.value) return null
    const t = detail.value.metrics.contract.monthly_target[i]
    return t > 0 ? +(v / t * 100).toFixed(1) : 0
  })
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>${p[0].marker}${p[0].value}%` },
    grid: { left: 40, right: 20, top: 20, bottom: 20 },
    xAxis: { type: 'category', data: MONTHS, axisLabel: { color: '#7a8fa6', fontSize: 10 }, splitLine: { show: false } },
    yAxis: { type: 'value', axisLabel: { color: '#7a8fa6', formatter: '{value}%', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    series: [{
      type: 'bar', barMaxWidth: 28,
      data: rates.map(r => ({
        value: r,
        itemStyle: { color: r === null ? 'transparent' : r >= 80 ? '#10b981' : r >= 60 ? '#f59e0b' : '#ef4444', borderRadius: [3, 3, 0, 0] }
      })),
      markLine: {
        silent: true,
        symbol: 'none',
        data: [{ yAxis: 60, lineStyle: { color: '#ef4444', type: 'dashed', width: 1 }, label: { formatter: '60%', color: '#ef4444', fontSize: 10 } }]
      }
    }]
  }
})
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <div class="back-btn" @click="router.push('/overview')">← 返回总览</div>

    <div class="section-header" v-if="detail">
      <span class="section-title">{{ detail.business_unit_name }}</span>
      <span class="section-sub">{{ store.year }}年</span>
    </div>

    <!-- KPI Cards -->
    <div class="kpi-grid" v-if="detail">
      <div
        v-for="m in METRICS" :key="m"
        class="kpi-card" :class="`k-${m}`"
      >
        <div class="kpi-label">{{ LABEL[m] }} · YTD</div>
        <div class="kpi-row">
          <span class="kpi-value">{{ fmt(detail.metrics[m].ytd_actual) }}</span>
          <span class="kpi-unit">万元</span>
        </div>
        <div class="kpi-meta">
          <span class="kpi-rate" :class="rateClass(detail.metrics[m].rate)">{{ detail.metrics[m].rate }}%</span>
          <span class="kpi-yoy">年度目标 <b>{{ fmt(detail.metrics[m].annual_target) }}</b> 万</span>
        </div>
        <div class="kpi-progress"><div class="kpi-bar" :style="{width: Math.min(detail.metrics[m].rate, 100) + '%'}" /></div>
      </div>
    </div>

    <!-- Charts -->
    <div class="two-col" style="margin-bottom:14px" v-if="detail">
      <div class="card">
        <div class="card-title">月度完成趋势（实际 vs 目标）</div>
        <v-chart :option="trendOption" style="height:280px" autoresize />
      </div>
      <div class="card">
        <div class="card-title">月度完成率（含60%预警线）</div>
        <v-chart :option="rateOption" style="height:280px" autoresize />
      </div>
    </div>

    <!-- Gap + Opp -->
    <div class="two-col" v-if="detail">
      <div class="card">
        <div class="card-title">目标缺口分析</div>
        <div class="gap-list">
          <div v-for="m in METRICS" :key="m" class="gap-row">
            <div>
              <div class="gap-metric">{{ LABEL[m] }} · 目标缺口</div>
              <div class="gap-sub">剩余{{ 12 - curMonth }}月均需 <span class="amber-num">{{ fmt(detail.metrics[m].per_month_needed) }}</span> 万元</div>
            </div>
            <div class="gap-val" :style="{ color: detail.metrics[m].gap > 0 ? 'var(--red)' : 'var(--green)' }">
              {{ detail.metrics[m].gap > 0 ? '' : '-' }}{{ fmt(Math.abs(detail.metrics[m].gap)) }} 万
            </div>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">本年度商机支撑</div>
        <div class="gap-list">
          <div v-for="m in METRICS" :key="m" class="gap-row">
            <div>
              <div class="gap-metric">{{ LABEL[m] }} · 商机支撑</div>
              <div class="gap-sub">进行中商机合计</div>
            </div>
            <div class="gap-val" :style="{ color: detail.metrics[m].opp_cover_rate >= 100 ? 'var(--green)' : detail.metrics[m].opp_cover_rate >= 60 ? 'var(--amber)' : 'var(--red)' }">
              {{ detail.metrics[m].opp_cover_rate >= 999 ? '100+' : detail.metrics[m].opp_cover_rate }}%
            </div>
          </div>
        </div>
      </div>
    </div>

    <el-empty v-if="!loading && !detail" description="暂无该事业部数据" />
  </div>
</template>

<style scoped>
.back-btn { display: inline-flex; align-items: center; gap: 6px; color: var(--text-sec); cursor: pointer; font-size: 12px; margin-bottom: 16px; padding: 5px 10px; border-radius: 6px; border: 1px solid var(--bg-border); transition: all .15s; }
.back-btn:hover { color: var(--accent); border-color: var(--accent); }
.section-header { display: flex; align-items: baseline; gap: 10px; margin-bottom: 16px; }
.section-title { font-size: 16px; font-weight: 600; }
.section-sub { font-size: 12px; color: var(--text-sec); }
.kpi-grid { display: grid; grid-template-columns: repeat(3,1fr); gap: 14px; margin-bottom: 16px; }
.kpi-card { background: var(--bg-card); border: 1px solid var(--bg-border); border-radius: 10px; padding: 16px 18px; position: relative; overflow: hidden; }
.kpi-card::after { content:''; position:absolute; top:0; left:0; right:0; height:2px; }
.kpi-card.k-contract::after { background: var(--blue); }
.kpi-card.k-revenue::after  { background: var(--green); }
.kpi-card.k-payment::after  { background: var(--accent); }
.kpi-label { font-size: 11px; color: var(--text-sec); margin-bottom: 8px; }
.kpi-row { display: flex; align-items: baseline; gap: 4px; }
.kpi-value { font-family: var(--mono); font-size: 26px; font-weight: 700; }
.kpi-unit { font-size: 12px; color: var(--text-sec); }
.kpi-meta { display: flex; align-items: center; gap: 10px; margin-top: 8px; font-size: 11px; }
.kpi-rate { font-family: var(--mono); font-size: 13px; font-weight: 600; }
.kpi-rate.good { color: var(--green); } .kpi-rate.warn { color: var(--amber); } .kpi-rate.bad { color: var(--red); }
.kpi-yoy { color: var(--text-sec); }
.kpi-progress { height: 3px; background: var(--bg-border); border-radius: 2px; margin-top: 10px; overflow: hidden; }
.kpi-bar { height: 100%; border-radius: 2px; transition: width 1.2s ease; }
.k-contract .kpi-bar { background: var(--blue); }
.k-revenue  .kpi-bar { background: var(--green); }
.k-payment  .kpi-bar { background: var(--accent); }
.card { background: var(--bg-card); border: 1px solid var(--bg-border); border-radius: 10px; padding: 18px 20px; }
.card-title { font-size: 11px; letter-spacing: 1.5px; color: var(--text-sec); text-transform: uppercase; margin-bottom: 14px; display: flex; align-items: center; gap: 8px; }
.card-title::before { content:''; display:block; width:3px; height:12px; border-radius:2px; background:var(--accent); }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; }
.gap-list { display: flex; flex-direction: column; gap: 10px; }
.gap-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; background: var(--bg-base); border-radius: 7px; border: 1px solid var(--bg-border); }
.gap-metric { font-size: 12px; color: var(--text-sec); }
.gap-sub { font-size: 11px; color: var(--text-dim); margin-top: 2px; }
.gap-val { font-family: var(--mono); font-size: 14px; font-weight: 600; }
.amber-num { color: var(--amber); font-family: var(--mono); }
</style>
