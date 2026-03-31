<script setup>
import { ref, onMounted } from 'vue'
import { importActuals, importTargets, importOpps, getImportHistory, getBatchFailures, getActuals, deleteActual } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '@/stores/app'

const store    = useAppStore()
const history  = ref([])
const uploading = ref(false)
const actuals  = ref([])
const aLoading = ref(false)
const aFilter  = ref({ year: new Date().getFullYear(), month: '', business_unit_id: '' })

const TYPE_LABEL   = { annual_target: '年度目标', monthly_actual: '月度完成', opportunity: '商机' }
const METRIC_LABEL = { contract: '合同', revenue: '收入', payment: '回款' }
const MONTHS = Array.from({ length: 12 }, (_, i) => i + 1)

async function loadHistory() {
  const res = await getImportHistory()
  history.value = res?.data || []
}

async function loadActuals() {
  aLoading.value = true
  const params = {}
  if (aFilter.value.year)             params.year = aFilter.value.year
  if (aFilter.value.month)            params.month = aFilter.value.month
  if (aFilter.value.business_unit_id) params.business_unit_id = aFilter.value.business_unit_id
  const res = await getActuals(params)
  actuals.value = res?.data || []
  aLoading.value = false
}

onMounted(() => { loadHistory(); loadActuals() })

async function handleUpload(file, type) {
  uploading.value = true
  const fn = type === 'actuals' ? importActuals : type === 'targets' ? importTargets : importOpps
  const res = await fn(file.raw || file)
  ElMessage({ type: res.success ? 'success' : 'warning', message: res.message })
  await loadHistory()
  await loadActuals()
  uploading.value = false
  return false
}

async function showFailures(row) {
  if (row.fail_rows === 0) return ElMessage.info('无失败记录')
  const res = await getBatchFailures(row.id)
  const rows = res?.data || []
  ElMessage({ message: rows.map(r => `第${r.row}行: ${r.reason}`).join('\n'), type: 'warning', duration: 0, showClose: true })
}

async function delActual(row) {
  await ElMessageBox.confirm(
    `确定删除「${row.business_unit_name} · ${row.year}年${row.month}月 · ${METRIC_LABEL[row.metric_type] || row.metric_type}」？`,
    '删除确认', { type: 'warning' }
  )
  await deleteActual(row.id)
  ElMessage.success('已删除')
  loadActuals()
}
</script>

<template>
  <div>
    <div style="font-size:16px;font-weight:600;margin-bottom:16px">月度数据导入</div>

    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:16px">
      <div class="card" v-for="t in [['actuals','月度完成数据'],['targets','年度目标数据'],['opps','商机数据']]" :key="t[0]">
        <div class="card-title">{{ t[1] }}</div>
        <el-upload
          drag action="" :auto-upload="false"
          :on-change="(f) => handleUpload(f, t[0])"
          accept=".xlsx,.xls,.csv"
          :show-file-list="false"
        >
          <el-icon style="font-size:28px;color:var(--text-dim)"><Upload /></el-icon>
          <div style="font-size:13px;color:var(--text-sec);margin-top:8px">拖放或点击上传</div>
          <div style="font-size:11px;color:var(--text-dim);margin-top:4px">.xlsx · .xls · .csv</div>
        </el-upload>
      </div>
    </div>

    <!-- 月度数据管理 -->
    <div class="card" style="margin-bottom:14px">
      <div class="card-title">月度完成数据管理</div>
      <div style="display:flex;gap:8px;margin-bottom:12px;flex-wrap:wrap">
        <el-select v-model="aFilter.year" size="small" style="width:90px" @change="loadActuals">
          <el-option v-for="y in [2026,2025,2024]" :key="y" :value="y" :label="y+'年'" />
        </el-select>
        <el-select v-model="aFilter.month" size="small" style="width:90px" clearable placeholder="全部月份" @change="loadActuals">
          <el-option v-for="m in MONTHS" :key="m" :value="m" :label="m+'月'" />
        </el-select>
        <el-select v-model="aFilter.business_unit_id" size="small" style="width:150px" clearable placeholder="全部事业部" @change="loadActuals">
          <el-option v-for="u in store.units" :key="u.id" :value="u.id" :label="u.name" />
        </el-select>
      </div>
      <el-table :data="actuals" size="small" v-loading="aLoading" element-loading-background="transparent">
        <el-table-column prop="year"               label="年份"   width="70"  align="center" />
        <el-table-column prop="month"              label="月份"   width="70"  align="center">
          <template #default="{ row }">{{ row.month }}月</template>
        </el-table-column>
        <el-table-column prop="business_unit_name" label="事业部" min-width="130" />
        <el-table-column prop="metric_type"        label="指标"   width="80"  align="center">
          <template #default="{ row }">{{ METRIC_LABEL[row.metric_type] || row.metric_type }}</template>
        </el-table-column>
        <el-table-column prop="actual_amount"      label="完成值(万)" width="110" align="right">
          <template #default="{ row }"><span style="font-family:var(--mono)">{{ row.actual_amount.toLocaleString() }}</span></template>
        </el-table-column>
        <el-table-column label="操作" width="80" align="center">
          <template #default="{ row }">
            <el-button link size="small" type="danger" @click="delActual(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 导入历史 -->
    <div class="card">
      <div class="card-title">导入历史</div>
      <el-table :data="history" size="small">
        <el-table-column prop="created_at" label="导入时间" width="170">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN') }}</template>
        </el-table-column>
        <el-table-column prop="filename" label="文件名" />
        <el-table-column prop="import_type" label="类型" width="100">
          <template #default="{ row }">{{ TYPE_LABEL[row.import_type] || row.import_type }}</template>
        </el-table-column>
        <el-table-column prop="success_rows" label="成功" width="70" align="center">
          <template #default="{ row }"><span style="color:var(--green);font-family:var(--mono)">{{ row.success_rows }}</span></template>
        </el-table-column>
        <el-table-column prop="fail_rows" label="失败" width="70" align="center">
          <template #default="{ row }">
            <span :style="{ color: row.fail_rows > 0 ? 'var(--red)' : 'var(--text-dim)', fontFamily: 'var(--mono)', cursor: row.fail_rows > 0 ? 'pointer' : 'default' }" @click="showFailures(row)">
              {{ row.fail_rows }}
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:18px 20px; }
.card-title { font-size:11px; letter-spacing:1.5px; color:var(--text-sec); text-transform:uppercase; margin-bottom:14px; display:flex; align-items:center; gap:8px; }
.card-title::before { content:''; display:block; width:3px; height:12px; border-radius:2px; background:var(--accent); }
</style>
