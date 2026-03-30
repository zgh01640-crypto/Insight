<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'
import { getOverview } from '@/api'
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
    const items = data.value.summaries.filter(s => s.metric_type === m)
    const ytd    = items.reduce((a, s) => a + s.ytd_actual, 0)
    const target = items.reduce((a, s) => a + s.ytd_target, 0)
    const rate   = target > 0 ? +(ytd / target * 100).toFixed(1) : 0
    const prevYtd= items.reduce((a, s) => a + s.prev_ytd_actual, 0)
    const yoy    = prevYtd > 0 ? +((ytd - prevYtd) / prevYtd * 100).toFixed(1) : null
    return { metric: m, label: METRIC_LABEL[m], ytd, target, rate, yoy }
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
        <div class="kpi-label">{{ kpi.label }} · YTD完成</div>
        <div class="kpi-row">
          <span class="kpi-value">{{ fmt(kpi.ytd) }}</span>
          <span class="kpi-unit">万元</span>
        </div>
        <div class="kpi-meta">
          <span class="kpi-rate" :class="rateClass(kpi.rate)">{{ kpi.rate }}%</span>
          <span class="kpi-yoy">
            <template v-if="kpi.yoy !== null">
              <span :class="kpi.yoy >= 0 ? 'up' : 'down'">{{ kpi.yoy >= 0 ? '▲' : '▼' }}{{ Math.abs(kpi.yoy) }}%</span>
              同比
            </template>
            <template v-else>—</template>
          </span>
        </div>
        <div class="kpi-progress">
          <div class="kpi-bar" :style="{ width: Math.min(kpi.rate, 100) + '%' }" />
        </div>
      </div>
    </div>

    <!-- YoY Row -->
    <div class="card" style="margin-bottom:14px" v-if="data">
      <div class="card-title">各事业部同比增长率（合同·YTD）</div>
      <div class="yoy-grid">
        <div v-for="unit in byUnit" :key="unit.id" class="yoy-card" @click="goToDivision(unit)" style="cursor:pointer">
          <div class="yoy-div">{{ unit.name.replace('事业部', '') }}</div>
          <div class="yoy-val" :class="(unit.metrics.contract?.yoy_rate ?? 0) >= 0 ? 'up' : 'down'">
            {{ unit.metrics.contract?.yoy_rate !== null ? ((unit.metrics.contract?.yoy_rate ?? 0) >= 0 ? '+' : '') + (unit.metrics.contract?.yoy_rate ?? '—') + '%' : '—' }}
          </div>
          <div class="yoy-label">{{ fmt(unit.metrics.contract?.prev_ytd_actual) }} → {{ fmt(unit.metrics.contract?.ytd_actual) }} 万</div>
        </div>
      </div>
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
                  <span class="rate-cell" :class="rateClass(unit.metrics[m]?.rate ?? 0)">
                    {{ unit.metrics[m]?.rate ?? 0 }}%
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
