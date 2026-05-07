<script setup>
import { ref, onMounted, computed } from 'vue'
import { getProductDashboard } from '@/api'
import { use } from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
use([BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const loading = ref(false)
const data    = ref(null)

const ALL_STATUSES = ['立项中', '开发中', '测试中', '已上线', '延迟', '已暂停', '已终止']
const MS_STATUSES  = ['未开始', '进行中', '已完成', '延期']

const STATUS_COLORS = {
  '立项中': '#6b7280', '开发中': '#3b82f6', '测试中': '#f0a500',
  '已上线': '#10b981', '延迟':   '#ef4444', '已暂停': '#9ca3af', '已终止': '#374151',
}
const MS_COLORS = {
  '未开始': '#6b7280', '进行中': '#3b82f6', '已完成': '#10b981', '延期': '#ef4444',
}

async function load() {
  loading.value = true
  const res = await getProductDashboard()
  data.value = res?.data || null
  loading.value = false
}
onMounted(load)

const summary = computed(() => data.value?.summary || {})
const byUnit  = computed(() => data.value?.by_unit || [])
const atRisk  = computed(() => data.value?.at_risk || [])
const msByUnit= computed(() => data.value?.milestone_by_unit || [])

// 已上线率
const onlineRate = computed(() => {
  const t = summary.value.total
  return t ? Math.round((summary.value.by_status?.['已上线'] || 0) / t * 100) : 0
})

// 里程碑完成率
const msRate = computed(() => {
  const t = summary.value.milestone_total
  return t ? Math.round(summary.value.milestone_done / t * 100) : 0
})

// ── 各事业部产品数量堆叠图 ──────────────────────────
const unitStackOption = computed(() => {
  if (!byUnit.value.length) return {}
  const units = byUnit.value.map(u => u.name.replace('事业部', '').replace('研发部', ''))
  const series = ALL_STATUSES
    .filter(s => byUnit.value.some(u => (u.by_status?.[s] || 0) > 0))
    .map(s => ({
      name: s,
      type: 'bar',
      stack: 'total',
      barMaxWidth: 20,
      label: {
        show: true,
        formatter: p => p.value > 0 ? p.value : '',
        color: '#fff',
        fontSize: 10,
      },
      itemStyle: { color: STATUS_COLORS[s] },
      data: byUnit.value.map(u => u.by_status?.[s] || 0),
    }))
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'shadow' },
      formatter: params => {
        const unit = byUnit.value[params[0].dataIndex]
        let s = `<b>${unit.name}</b> 共 ${unit.total} 个<br/>`
        params.filter(p => p.value > 0).forEach(p => {
          s += `${p.marker}${p.seriesName}：${p.value}<br/>`
        })
        return s
      },
    },
    legend: {
      data: series.map(s => s.name),
      textStyle: { color: '#9ab', fontSize: 10 },
      bottom: 0,
    },
    grid: { left: 90, right: 20, top: 10, bottom: 36 },
    xAxis: { type: 'value', axisLabel: { color: '#7a8fa6', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    yAxis: { type: 'category', data: units, axisLabel: { color: '#9ab', fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false } },
    series,
  }
})

// ── 状态分布饼图 ────────────────────────────────────
const statusPieOption = computed(() => {
  if (!summary.value.by_status) return {}
  const pieData = ALL_STATUSES
    .filter(s => (summary.value.by_status[s] || 0) > 0)
    .map(s => ({ name: s, value: summary.value.by_status[s], itemStyle: { color: STATUS_COLORS[s] } }))
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', formatter: '{b}：{c} 个 ({d}%)' },
    legend: { orient: 'vertical', right: 10, top: 'middle', textStyle: { color: '#9ab', fontSize: 11 } },
    series: [{
      type: 'pie', radius: ['38%', '65%'],
      center: ['38%', '50%'],
      label: { show: false },
      data: pieData,
    }],
  }
})

// ── 里程碑完成率图 ───────────────────────────────────
const msRateOption = computed(() => {
  if (!byUnit.value.length) return {}
  const withMs = byUnit.value.filter(u => u.milestone_total > 0)
  if (!withMs.length) return {}
  const names = withMs.map(u => u.name.replace('事业部', '').replace('研发部', ''))
  const rates = withMs.map(u => u.milestone_rate)
  return {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      formatter: p => {
        const u = withMs[p[0].dataIndex]
        return `${u.name}<br/>里程碑完成率 <b>${u.milestone_rate}%</b><br/>${u.milestone_done}/${u.milestone_total} 个节点`
      },
    },
    grid: { left: 90, right: 60, top: 10, bottom: 10 },
    xAxis: {
      type: 'value', max: 100,
      axisLabel: { color: '#7a8fa6', fontSize: 10, formatter: v => v + '%' },
      splitLine: { lineStyle: { color: '#1e2a38' } },
    },
    yAxis: { type: 'category', data: names, axisLabel: { color: '#9ab', fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false } },
    series: [{
      type: 'bar', barMaxWidth: 18, data: rates,
      itemStyle: { color: '#10b981', borderRadius: [0, 3, 3, 0] },
      label: { show: true, position: 'right', color: '#9ab', fontSize: 10, formatter: p => p.value + '%' },
      markLine: {
        silent: true, symbol: 'none',
        data: [{ xAxis: 100, lineStyle: { color: '#f0a500', type: 'dashed', width: 1 } }],
        label: { show: false },
      },
    }],
  }
})

// ── 里程碑状态堆叠图（按事业部）──────────────────────
const msStackOption = computed(() => {
  if (!msByUnit.value.length) return {}
  const units = msByUnit.value.map(u => u.name.replace('事业部', '').replace('研发部', ''))
  const series = MS_STATUSES
    .filter(s => msByUnit.value.some(u => (u[s] || 0) > 0))
    .map(s => ({
      name: s, type: 'bar', stack: 'total', barMaxWidth: 18,
      label: { show: true, formatter: p => p.value > 0 ? p.value : '', color: '#fff', fontSize: 10 },
      itemStyle: { color: MS_COLORS[s] },
      data: msByUnit.value.map(u => u[s] || 0),
    }))
  if (!series.length) return {}
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: series.map(s => s.name), textStyle: { color: '#9ab', fontSize: 10 }, bottom: 0 },
    grid: { left: 90, right: 20, top: 10, bottom: 36 },
    xAxis: { type: 'value', axisLabel: { color: '#7a8fa6', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    yAxis: { type: 'category', data: units, axisLabel: { color: '#9ab', fontSize: 11 }, axisLine: { show: false }, axisTick: { show: false } },
    series,
  }
})

function rateColor(r) { return r >= 80 ? 'var(--green)' : r >= 50 ? 'var(--amber)' : 'var(--red)' }
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <div class="section-header">
      <span class="section-title">产品驾驶舱</span>
    </div>

    <template v-if="data">
      <!-- KPI 卡片 -->
      <div class="kpi-row">
        <!-- 产品总数 -->
        <div class="kpi-card">
          <div class="kpi-label">产品总数</div>
          <div class="kpi-value">{{ summary.total }}</div>
          <div class="kpi-sub">
            在研 {{ (summary.by_status?.['立项中']||0) + (summary.by_status?.['开发中']||0) + (summary.by_status?.['测试中']||0) }} &nbsp;·&nbsp;
            上线 {{ summary.by_status?.['已上线']||0 }} &nbsp;·&nbsp;
            暂停/终止 {{ (summary.by_status?.['已暂停']||0) + (summary.by_status?.['已终止']||0) }}
          </div>
        </div>
        <!-- 已上线 -->
        <div class="kpi-card">
          <div class="kpi-label">已上线</div>
          <div class="kpi-value" style="color:var(--green)">{{ summary.by_status?.['已上线']||0 }}</div>
          <div class="kpi-sub">占总数 {{ onlineRate }}%</div>
          <div class="kpi-bar"><div class="kpi-bar-fill" :style="{ width: onlineRate+'%', background:'var(--green)' }" /></div>
        </div>
        <!-- 延迟/风险 -->
        <div class="kpi-card">
          <div class="kpi-label">延迟 / 风险</div>
          <div class="kpi-value" :style="{ color: summary.at_risk_count > 0 ? 'var(--red)' : 'var(--green)' }">
            {{ summary.at_risk_count }}
          </div>
          <div class="kpi-sub">需关注产品</div>
        </div>
        <!-- 里程碑完成率 -->
        <div class="kpi-card">
          <div class="kpi-label">里程碑完成率</div>
          <div class="kpi-value" :style="{ color: rateColor(msRate) }">
            {{ summary.milestone_total ? msRate : '—' }}<span v-if="summary.milestone_total" style="font-size:16px;font-weight:400">%</span>
          </div>
          <div class="kpi-sub">{{ summary.milestone_done }} / {{ summary.milestone_total }} 个节点</div>
          <div v-if="summary.milestone_total" class="kpi-bar">
            <div class="kpi-bar-fill" :style="{ width: msRate+'%', background: rateColor(msRate) }" />
          </div>
        </div>
      </div>

      <!-- 图表第一行 -->
      <div class="chart-row">
        <div class="card">
          <div class="card-title" style="--dot-color:#3b82f6">各事业部产品数量（按状态）</div>
          <v-chart v-if="byUnit.length" :option="unitStackOption" style="height:220px" autoresize />
          <div v-else class="empty-tip">暂无数据</div>
        </div>
        <div class="card">
          <div class="card-title" style="--dot-color:#f0a500">产品状态分布</div>
          <v-chart :option="statusPieOption" style="height:220px" autoresize />
        </div>
      </div>

      <!-- 图表第二行 -->
      <div class="chart-row">
        <div class="card">
          <div class="card-title" style="--dot-color:#10b981">各事业部里程碑完成率</div>
          <v-chart v-if="msByUnit.length" :option="msRateOption" style="height:200px" autoresize />
          <div v-else class="empty-tip">暂无里程碑数据</div>
        </div>
        <div class="card">
          <div class="card-title" style="--dot-color:#6b7280">各事业部里程碑状态分布</div>
          <v-chart v-if="msByUnit.length" :option="msStackOption" style="height:200px" autoresize />
          <div v-else class="empty-tip">暂无里程碑数据</div>
        </div>
      </div>

      <!-- 延迟/风险产品列表 -->
      <div v-if="atRisk.length" class="card" style="margin-top:12px">
        <div class="card-title" style="--dot-color:#ef4444">⚠ 需关注产品（延迟 / 有风险）</div>
        <el-table :data="atRisk" size="small">
          <el-table-column prop="name" label="产品名称" min-width="180" show-overflow-tooltip />
          <el-table-column prop="business_unit_name" label="事业部" width="130" />
          <el-table-column label="状态" width="80" align="center">
            <template #default="{ row }">
              <el-tag size="small" :type="row.status === '延迟' ? 'danger' : ''">{{ row.status }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="product_manager" label="产品经理" width="90" />
          <el-table-column prop="progress" label="进展" width="100" show-overflow-tooltip />
          <el-table-column prop="risk" label="风险" min-width="200" show-overflow-tooltip>
            <template #default="{ row }">
              <span v-if="row.risk" style="color:var(--red)">{{ row.risk }}</span>
              <span v-else style="color:var(--text-dim)">—</span>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </template>

    <el-empty v-if="!loading && !data" description="暂无产品数据" />
  </div>
</template>

<style scoped>
.section-header { display:flex; align-items:center; gap:10px; margin-bottom:16px; }
.section-title  { font-size:16px; font-weight:600; }

.kpi-row { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:14px; }
.kpi-card {
  background:var(--bg-card); border:1px solid var(--bg-border);
  border-radius:10px; padding:16px 18px;
}
.kpi-label { font-size:11px; color:var(--text-sec); letter-spacing:1px; margin-bottom:6px; }
.kpi-value { font-family:var(--mono); font-size:32px; font-weight:700; line-height:1; }
.kpi-sub   { font-size:11px; color:var(--text-dim); margin-top:4px; margin-bottom:6px; }
.kpi-bar   { height:4px; background:var(--bg-border); border-radius:2px; overflow:hidden; }
.kpi-bar-fill { height:100%; border-radius:2px; transition:width .4s; }

.chart-row { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:12px; }
.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:16px 18px; }
.card-title {
  font-size:11px; letter-spacing:1.5px; color:var(--text-sec);
  margin-bottom:10px; display:flex; align-items:center; gap:8px;
}
.card-title::before {
  content:''; display:block; width:3px; height:12px; border-radius:2px;
  background:var(--dot-color, var(--accent));
}
.empty-tip { font-size:12px; color:var(--text-dim); text-align:center; padding:40px 0; }
</style>
