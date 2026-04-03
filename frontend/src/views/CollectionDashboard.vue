<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useAppStore } from '@/stores/app'
import { getCollectionDashboard } from '@/api'
import { use } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const store   = useAppStore()
const loading = ref(false)
const data    = ref(null)

const summary  = computed(() => data.value?.summary  || {})
const byUnit   = computed(() => data.value?.by_unit  || [])
const topItems = computed(() => data.value?.top_items || [])

async function load() {
  loading.value = true
  try {
    const res = await getCollectionDashboard(store.year)
    data.value = res?.data || null
  } finally {
    loading.value = false
  }
}
onMounted(load)
watch(() => store.year, load)

function fmt(n) {
  const v = Number(n)
  return isNaN(v) ? '—' : v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

// 各事业部欠款金额堆叠横向柱状图
const barOption = computed(() => {
  if (!byUnit.value.length) return {}
  const names = byUnit.value.map(d => d.business_unit_name.replace('事业部', ''))
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: params => {
        const d = byUnit.value[params[0].dataIndex]
        return `${d.business_unit_name}<br/>
          催收中 <b>${fmt(d.collecting_amount)}</b> 万（${d.collecting_count}项）<br/>
          已回款 <b>${fmt(d.recovered_amount)}</b> 万（${d.recovered_count}项）<br/>
          回款率 <b>${d.recovery_rate}%</b>`
      }
    },
    grid: { left: 72, right: 70, top: 16, bottom: 4 },
    xAxis: {
      type: 'value',
      axisLabel: { color: '#7a8fa6', fontSize: 10 },
      splitLine: { lineStyle: { color: '#1e2a38' } },
    },
    yAxis: {
      type: 'category',
      data: names,
      axisLabel: { color: '#9ab', fontSize: 11 },
      axisLine: { show: false },
      axisTick: { show: false },
    },
    series: [
      {
        name: '催收中',
        type: 'bar',
        stack: 'total',
        barMaxWidth: 20,
        data: byUnit.value.map(d => d.collecting_amount),
        itemStyle: { color: '#ef4444', borderRadius: [0, 0, 0, 0] },
        label: { show: false },
      },
      {
        name: '已回款',
        type: 'bar',
        stack: 'total',
        barMaxWidth: 20,
        data: byUnit.value.map(d => d.recovered_amount),
        itemStyle: { color: '#10b981', borderRadius: [0, 3, 3, 0] },
        label: {
          show: true, position: 'right', color: '#9ab', fontSize: 10,
          formatter: p => {
            const d = byUnit.value[p.dataIndex]
            return fmt(d.total_amount) + ' 万'
          }
        },
      },
      {
        name: '已核销',
        type: 'bar',
        stack: 'total',
        barMaxWidth: 20,
        data: byUnit.value.map(d => d.written_off_amount),
        itemStyle: { color: '#6b7280' },
      },
    ],
  }
})

// 状态占比饼图
const pieOption = computed(() => {
  if (!summary.value.total_amount) return {}
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'item',
      formatter: p => `${p.name}<br/><b>${fmt(p.value)}</b> 万（${p.percent}%）`
    },
    legend: {
      bottom: 0,
      textStyle: { color: '#9ab', fontSize: 11 },
    },
    series: [{
      type: 'pie',
      radius: ['38%', '65%'],
      center: ['50%', '44%'],
      data: [
        { name: '催收中', value: summary.value.collecting_amount, itemStyle: { color: '#ef4444' } },
        { name: '已回款', value: summary.value.recovered_amount,  itemStyle: { color: '#10b981' } },
        { name: '已核销', value: summary.value.written_off_amount, itemStyle: { color: '#6b7280' } },
      ].filter(d => d.value > 0),
      label: { show: false },
      emphasis: {
        label: { show: true, fontSize: 12, fontWeight: 'bold', color: '#e2e8f0' }
      },
    }],
  }
})

const itemsByUnit = computed(() => data.value?.items_by_unit || {})

// 按 byUnit 顺序（已按总金额降序）排列各事业部明细
const unitNames = computed(() => byUnit.value.map(u => u.business_unit_name))

function rateColor(r) { return r >= 30 ? 'var(--green)' : r >= 10 ? 'var(--amber)' : 'var(--red)' }
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <div class="section-header">
      <span class="section-title">催收仪表盘</span>
      <span v-if="data" style="font-size:12px;color:var(--text-sec)">
        {{ store.year }}年 · 共 {{ summary.total_count }} 个项目
      </span>
    </div>

    <template v-if="data">
      <!-- KPI 卡片行 -->
      <div class="kpi-grid">
        <!-- 总欠款 -->
        <div class="kpi-card">
          <div class="kpi-label">总欠款金额</div>
          <div class="kpi-value">{{ fmt(summary.total_amount) }}<span class="kpi-unit">万元</span></div>
          <div class="kpi-sub">共 {{ summary.total_count }} 个项目</div>
          <div class="kpi-progress">
            <div class="kpi-bar" style="width:100%;background:var(--text-dim)" />
          </div>
        </div>
        <!-- 催收中 -->
        <div class="kpi-card">
          <div class="kpi-label">催收中</div>
          <div class="kpi-value" style="color:var(--red)">
            {{ fmt(summary.collecting_amount) }}<span class="kpi-unit">万元</span>
          </div>
          <div class="kpi-sub">{{ summary.collecting_count }} 个项目</div>
          <div class="kpi-progress">
            <div class="kpi-bar" :style="{
              width: summary.total_amount ? (summary.collecting_amount / summary.total_amount * 100).toFixed(1) + '%' : '0%',
              background: 'var(--red)'
            }" />
          </div>
        </div>
        <!-- 已回款 -->
        <div class="kpi-card">
          <div class="kpi-label">已回款</div>
          <div class="kpi-value" :style="{ color: rateColor(summary.recovery_rate) }">
            {{ fmt(summary.recovered_amount) }}<span class="kpi-unit">万元</span>
          </div>
          <div class="kpi-sub">
            回款率
            <b :style="{ color: rateColor(summary.recovery_rate) }">{{ summary.recovery_rate }}%</b>
            · {{ summary.recovered_count }} 个项目
          </div>
          <div class="kpi-progress">
            <div class="kpi-bar" :style="{
              width: summary.recovery_rate + '%',
              background: rateColor(summary.recovery_rate)
            }" />
          </div>
        </div>
      </div>

      <!-- 图表区（两列） -->
      <div class="chart-grid">
        <div class="card">
          <div class="card-title">各事业部欠款金额分布</div>
          <v-chart :option="barOption" style="height:200px" autoresize />
        </div>
        <div class="card">
          <div class="card-title">状态占比</div>
          <v-chart :option="pieOption" style="height:200px" autoresize />
        </div>
      </div>

      <!-- 事业部汇总表 -->
      <div class="card" style="margin-bottom:12px">
        <div class="card-title">事业部催收汇总</div>
        <el-table :data="byUnit" size="small">
          <el-table-column prop="business_unit_name" label="事业部" min-width="130" />
          <el-table-column label="总欠款(万)" width="110" align="right">
            <template #default="{ row }"><span class="mono">{{ fmt(row.total_amount) }}</span></template>
          </el-table-column>
          <el-table-column label="催收中(万)" width="110" align="right">
            <template #default="{ row }">
              <span class="mono" style="color:var(--red)">{{ fmt(row.collecting_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="已回款(万)" width="110" align="right">
            <template #default="{ row }">
              <span class="mono" style="color:var(--green)">{{ fmt(row.recovered_amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column label="回款率" width="80" align="center">
            <template #default="{ row }">
              <span :style="{ color: rateColor(row.recovery_rate), fontWeight: 600 }">
                {{ row.recovery_rate }}%
              </span>
            </template>
          </el-table-column>
          <el-table-column label="项目数" width="70" align="center" prop="total_count" />
        </el-table>
      </div>

      <!-- Top10 重点催收项目 -->
      <div class="card">
        <div class="card-title" style="--dot-color: var(--red)">重点催收项目 Top 10</div>
        <el-table :data="topItems" size="small">
          <el-table-column type="index" width="40" align="center" />
          <el-table-column prop="project_name" label="项目名称" min-width="200" show-overflow-tooltip />
          <el-table-column prop="client_name" label="单位名称" min-width="160" show-overflow-tooltip />
          <el-table-column prop="business_unit_name" label="事业部" width="130" />
          <el-table-column label="欠款金额(万)" width="120" align="right">
            <template #default="{ row }">
              <span class="mono" style="color:var(--red);font-weight:600">{{ fmt(row.amount) }}</span>
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>

      <!-- 各事业部催收明细 -->
      <div v-for="unitName in unitNames" :key="unitName" class="card">
        <div class="div-header">
          <span class="div-title">{{ unitName.replace('事业部','') }}</span>
          <span class="div-stats">
            共 {{ (itemsByUnit[unitName] || []).length }} 项 ·
            合计 <span class="mono">{{ fmt((itemsByUnit[unitName] || []).reduce((s, i) => s + i.amount, 0)) }}</span> 万
          </span>
        </div>
        <el-table :data="itemsByUnit[unitName] || []" size="small">
          <el-table-column type="index" width="40" align="center" />
          <el-table-column prop="project_name" label="项目名称" min-width="220" show-overflow-tooltip />
          <el-table-column prop="client_name" label="单位名称" min-width="160" show-overflow-tooltip />
          <el-table-column label="欠款金额(万)" width="120" align="right">
            <template #default="{ row }">
              <span class="mono" :style="{ color: row.status === '已回款' ? 'var(--green)' : 'var(--red)', fontWeight: 600 }">
                {{ fmt(row.amount) }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="90" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.status === '催收中' ? 'danger' : row.status === '已回款' ? 'success' : 'info'">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="备注" min-width="120" show-overflow-tooltip />
        </el-table>
      </div>
    </template>

    <el-empty v-if="!loading && !data" description="暂无催收数据" />
  </div>
</template>

<style scoped>
.section-header { display:flex; align-items:center; gap:12px; margin-bottom:16px; }
.section-title  { font-size:16px; font-weight:600; }

/* KPI */
.kpi-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:12px; }
.kpi-card {
  background:var(--bg-card); border:1px solid var(--bg-border);
  border-radius:10px; padding:18px 20px;
}
.kpi-label { font-size:11px; color:var(--text-sec); letter-spacing:1px; margin-bottom:8px; }
.kpi-value { font-family:var(--mono); font-size:28px; font-weight:700; line-height:1; }
.kpi-unit  { font-size:13px; font-weight:400; margin-left:4px; color:var(--text-sec); }
.kpi-sub   { font-size:11px; color:var(--text-dim); margin-top:6px; margin-bottom:8px; }
.kpi-sub b { font-family:var(--mono); }
.kpi-progress { height:3px; background:var(--bg-border); border-radius:2px; overflow:hidden; }
.kpi-bar      { height:100%; border-radius:2px; transition:width .4s; }

/* 图表两列 */
.chart-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px; }
.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:16px 18px; margin-bottom:12px; }
.card:last-child { margin-bottom:0; }
.card-title {
  font-size:11px; letter-spacing:1.5px; color:var(--text-sec);
  margin-bottom:12px; display:flex; align-items:center; gap:8px;
}
.card-title::before {
  content:''; display:block; width:3px; height:12px; border-radius:2px;
  background:var(--dot-color, var(--accent));
}
.mono { font-family:var(--mono); }

/* 事业部明细 */
.div-header { display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }
.div-title  { font-size:12px; font-weight:600; color:var(--text-sec); letter-spacing:1px; }
.div-stats  { font-size:11px; color:var(--text-dim); }
</style>
