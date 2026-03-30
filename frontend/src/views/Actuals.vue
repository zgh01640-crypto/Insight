<script setup>
import { ref, onMounted } from 'vue'
import { importActuals, importTargets, importOpps, getImportHistory, getBatchFailures } from '@/api'
import { ElMessage } from 'element-plus'

const history  = ref([])
const uploading = ref(false)
const TYPE_LABEL = { annual_target: '年度目标', monthly_actual: '月度完成', opportunity: '商机' }

async function loadHistory() {
  const res = await getImportHistory()
  history.value = res?.data || []
}
onMounted(loadHistory)

async function handleUpload(file, type) {
  uploading.value = true
  const fn = type === 'actuals' ? importActuals : type === 'targets' ? importTargets : importOpps
  const res = await fn(file.raw || file)
  ElMessage({ type: res.success ? 'success' : 'warning', message: res.message })
  await loadHistory()
  uploading.value = false
  return false
}

async function showFailures(row) {
  if (row.fail_rows === 0) return ElMessage.info('无失败记录')
  const res = await getBatchFailures(row.id)
  const rows = res?.data || []
  ElMessage({ message: rows.map(r => `第${r.row}行: ${r.reason}`).join('\n'), type: 'warning', duration: 0, showClose: true })
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
