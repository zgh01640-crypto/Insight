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

const store   = useAppStore()
const loading = ref(false)
const data    = ref(null)

async function load() {
  loading.value = true
  const res = await getOppSupport(store.year)
  data.value = res?.data || null
  loading.value = false
}
onMounted(load)
watch(() => store.year, load)

const funnelMax = computed(() => data.value ? Math.max(...data.value.funnel.map(f => f.total_amount), 1) : 1)

const quarterOption = computed(() => {
  if (!data.value) return {}
  const qs = ['Q1','Q2','Q3','Q4']
  const divNames = store.units.map(u => u.name)
  const colors = ['rgba(59,130,246,.7)', 'rgba(16,185,129,.7)', 'rgba(245,158,11,.7)', 'rgba(139,92,246,.7)', 'rgba(239,68,68,.7)']
  return {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { textStyle: { color: '#7a8fa6', fontSize: 10 }, top: 0 },
    grid: { left: 40, right: 20, top: 30, bottom: 20 },
    xAxis: { type: 'category', data: qs, axisLabel: { color: '#7a8fa6' }, splitLine: { show: false } },
    yAxis: { type: 'value', axisLabel: { color: '#7a8fa6', fontSize: 10 }, splitLine: { lineStyle: { color: '#1e2a38' } } },
    series: divNames.map((name, i) => ({
      name, type: 'bar', stack: 'total', barMaxWidth: 40,
      data: qs.map(q => data.value.quarterly[q]?.[name] || 0),
      itemStyle: { color: colors[i], borderRadius: i === divNames.length - 1 ? [3,3,0,0] : [0,0,0,0] }
    }))
  }
})

const STAGE_COLORS = { '线索': '#3b82f6', '立项': '#8b5cf6', '报价': '#f59e0b', '签约跟进': '#10b981', '已完成': '#34d399' }
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <div class="section-header"><span class="section-title">商机支撑分析</span><span class="section-sub">{{ store.year }}年 · 全中心</span></div>

    <div class="kpi-grid" v-if="data" style="margin-bottom:14px">
      <div class="kpi-card k-contract">
        <div class="kpi-label">进行中商机总金额</div>
        <div class="kpi-row"><span class="kpi-value">{{ data.opp_active_total.toLocaleString() }}</span><span class="kpi-unit">万元</span></div>
        <div class="kpi-meta"><span class="kpi-yoy">共 <b>{{ data.total_count }}</b> 条商机</span></div>
      </div>
      <div class="kpi-card k-revenue">
        <div class="kpi-label">合同缺口覆盖率</div>
        <div class="kpi-row"><span class="kpi-value" :class="data.cover_rate >= 100 ? 'text-green' : data.cover_rate >= 60 ? 'text-amber' : 'text-red'">{{ data.cover_rate >= 999 ? '100+' : data.cover_rate }}</span><span class="kpi-unit">%</span></div>
        <div class="kpi-meta"><span class="kpi-yoy">商机金额 / 合同缺口</span></div>
      </div>
      <div class="kpi-card k-payment">
        <div class="kpi-label">合同年度缺口</div>
        <div class="kpi-row"><span class="kpi-value">{{ data.contract_gap.toLocaleString() }}</span><span class="kpi-unit">万元</span></div>
        <div class="kpi-meta"><span class="kpi-yoy">年度目标 - YTD完成</span></div>
      </div>
    </div>

    <div class="two-col" style="margin-bottom:14px" v-if="data">
      <div class="card">
        <div class="card-title">商机阶段漏斗</div>
        <div class="funnel-list">
          <div v-for="f in data.funnel" :key="f.stage" class="funnel-item">
            <span class="funnel-label">{{ f.stage }}</span>
            <div class="funnel-track">
              <div
                class="funnel-bar"
                :style="{ width: (f.total_amount / funnelMax * 100) + '%', background: STAGE_COLORS[f.stage] }"
              >{{ f.total_amount > 0 ? f.total_amount.toLocaleString() + '万' : '' }}</div>
            </div>
            <span class="funnel-count">{{ f.count }}条</span>
          </div>
        </div>
      </div>
      <div class="card">
        <div class="card-title">季度商机分布</div>
        <v-chart :option="quarterOption" style="height:220px" autoresize />
      </div>
    </div>

    <el-empty v-if="!loading && !data" description="暂无商机数据" />
  </div>
</template>

<style scoped>
.section-header { display:flex; align-items:baseline; gap:10px; margin-bottom:16px; }
.section-title { font-size:16px; font-weight:600; }
.section-sub { font-size:12px; color:var(--text-sec); }
.kpi-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:14px; }
.kpi-card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:16px 18px; position:relative; overflow:hidden; }
.kpi-card::after { content:''; position:absolute; top:0; left:0; right:0; height:2px; }
.kpi-card.k-contract::after { background:var(--blue); } .kpi-card.k-revenue::after { background:var(--green); } .kpi-card.k-payment::after { background:var(--accent); }
.kpi-label { font-size:11px; color:var(--text-sec); margin-bottom:8px; }
.kpi-row { display:flex; align-items:baseline; gap:4px; }
.kpi-value { font-family:var(--mono); font-size:26px; font-weight:700; }
.kpi-unit { font-size:12px; color:var(--text-sec); }
.kpi-meta { margin-top:8px; font-size:11px; color:var(--text-sec); }
.text-green { color:var(--green); } .text-amber { color:var(--amber); } .text-red { color:var(--red); }
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
</style>
