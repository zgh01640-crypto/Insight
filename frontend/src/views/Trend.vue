<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { getTrend } from '@/api'
import { use } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
use([BarChart, LineChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const loading = ref(false)
const metric  = ref('contract')
const data    = ref(null)
const LABEL   = { contract: '合同', revenue: '收入', payment: '回款' }
const MONTHS  = ['1月','2月','3月','4月','5月','6月','7月','8月','9月','10月','11月','12月']

async function load() {
  loading.value = true
  const res = await getTrend(metric.value)
  data.value = res?.data || null
  loading.value = false
}
onMounted(load)
watch(metric, load)

const yearBarOption = computed(() => {
  if (!data.value) return {}
  const units = data.value.matrix.map(r => r.business_unit_name.replace('事业部',''))
  const [y1, y2] = data.value.years
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#7a8fa6', fontSize: 11 }, top: 0 },
    grid: { left: 70, right: 20, top: 35, bottom: 20 },
    xAxis: { type: 'category', data: units, axisLabel: { color: '#7a8fa6' }, splitLine: { show: false } },
    yAxis: { type: 'value', axisLabel: { color: '#7a8fa6', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    series: [
      { name: y1+'年', type: 'bar', barGap: '5%', data: data.value.matrix.map(r => r.years[y1]?.ytd || 0), itemStyle: { color: 'rgba(59,130,246,.5)', borderRadius: [3,3,0,0] } },
      { name: y2+'年', type: 'bar', data: data.value.matrix.map(r => r.years[y2]?.ytd || 0), itemStyle: { color: 'rgba(240,165,0,.8)', borderRadius: [3,3,0,0] } },
    ]
  }
})

const monthlyOption = computed(() => {
  if (!data.value) return {}
  const [y1, y2] = data.value.years
  const cm = data.value.cur_month
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { textStyle: { color: '#7a8fa6', fontSize: 11 }, top: 0 },
    grid: { left: 50, right: 20, top: 35, bottom: 20 },
    xAxis: { type: 'category', data: MONTHS, axisLabel: { color: '#7a8fa6', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    yAxis: { type: 'value', axisLabel: { color: '#7a8fa6', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    series: [
      { name: y1+'年', type: 'line', smooth: true, data: data.value.center_monthly[y1], lineStyle: { color: 'rgba(59,130,246,.7)', type: 'dashed' }, itemStyle: { color: '#3b82f6' }, symbolSize: 3 },
      { name: y2+'年', type: 'line', smooth: true, data: data.value.center_monthly[y2].map((v, i) => i < cm ? v : null), lineStyle: { color: '#f0a500', width: 2 }, itemStyle: { color: '#f0a500' }, symbolSize: 4 },
    ]
  }
})

const rankOption = computed(() => {
  if (!data.value) return {}
  const sorted = [...data.value.matrix].sort((a, b) => (b.yoy_rate || 0) - (a.yoy_rate || 0))
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', formatter: p => `${p[0].name}<br/>${p[0].value}%` },
    grid: { left: 90, right: 30, top: 10, bottom: 20 },
    xAxis: { type: 'value', axisLabel: { color: '#7a8fa6', formatter: '{value}%', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    yAxis: { type: 'category', data: sorted.map(r => r.business_unit_name.replace('事业部','')), axisLabel: { color: '#7a8fa6', fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{
      type: 'bar', barMaxWidth: 22,
      data: sorted.map(r => ({ value: r.yoy_rate ?? 0, itemStyle: { color: (r.yoy_rate ?? 0) >= 0 ? '#10b981' : '#ef4444', borderRadius: [0,3,3,0] } })),
      label: { show: true, position: 'right', color: '#7a8fa6', fontSize: 10, formatter: p => p.value + '%' }
    }]
  }
})
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:16px">
      <span style="font-size:16px;font-weight:600">同比 · 趋势分析</span>
      <el-radio-group v-model="metric" size="small">
        <el-radio-button value="contract">合同</el-radio-button>
        <el-radio-button value="revenue">收入</el-radio-button>
        <el-radio-button value="payment">回款</el-radio-button>
      </el-radio-group>
    </div>

    <div class="card" style="margin-bottom:14px" v-if="data">
      <div class="card-title">年度完成总量对比（{{ LABEL[metric] }}·YTD，万元）</div>
      <v-chart :option="yearBarOption" style="height:260px" autoresize />
    </div>

    <div class="two-col" style="margin-bottom:14px" v-if="data">
      <div class="card">
        <div class="card-title">月度走势双年对比（全中心·{{ LABEL[metric] }}）</div>
        <v-chart :option="monthlyOption" style="height:200px" autoresize />
      </div>
      <div class="card">
        <div class="card-title">各事业部增长率排行</div>
        <v-chart :option="rankOption" style="height:200px" autoresize />
      </div>
    </div>

    <div class="card" v-if="data">
      <div class="card-title">年度全景矩阵（{{ LABEL[metric] }}，万元）</div>
      <el-table :data="data.matrix" size="small" style="width:100%">
        <el-table-column prop="business_unit_name" label="事业部" width="140" />
        <el-table-column v-for="y in data.years" :key="y" :label="`${y}年全年`" align="right">
          <template #default="{ row }">{{ (row.years[y]?.total || 0).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column v-for="y in data.years" :key="`ytd-${y}`" :label="`${y}年YTD`" align="right">
          <template #default="{ row }">{{ (row.years[y]?.ytd || 0).toLocaleString() }}</template>
        </el-table-column>
        <el-table-column label="同比增长率" align="center">
          <template #default="{ row }">
            <span :style="{ color: (row.yoy_rate ?? 0) >= 0 ? 'var(--green)' : 'var(--red)', fontFamily: 'var(--mono)', fontWeight: 600 }">
              {{ row.yoy_rate !== null ? ((row.yoy_rate >= 0 ? '+' : '') + row.yoy_rate + '%') : '—' }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-empty v-if="!loading && !data" description="暂无趋势数据" />
  </div>
</template>

<style scoped>
.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:18px 20px; }
.card-title { font-size:11px; letter-spacing:1.5px; color:var(--text-sec); text-transform:uppercase; margin-bottom:14px; display:flex; align-items:center; gap:8px; }
.card-title::before { content:''; display:block; width:3px; height:12px; border-radius:2px; background:var(--accent); }
.two-col { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
</style>
