<script setup>
import { ref, onMounted, watch } from 'vue'
import { useAppStore } from '@/stores/app'
import { getTargets, updateTargets } from '@/api'
import { ElMessage } from 'element-plus'

const store   = useAppStore()
const loading = ref(false)
const saving  = ref(false)
const items   = ref([])
const METRICS = ['contract','revenue','payment']
const LABEL   = { contract:'合同', revenue:'收入', payment:'回款' }

// items indexed as map: [unit_id][metric] => item
const itemMap = ref({})

async function load() {
  loading.value = true
  const res = await getTargets(store.year)
  items.value = res?.data?.items || []
  itemMap.value = {}
  for (const it of items.value) {
    if (!itemMap.value[it.business_unit_id]) itemMap.value[it.business_unit_id] = {}
    itemMap.value[it.business_unit_id][it.metric_type] = it
  }
  loading.value = false
}

// Unique units
const units = ref([])
watch(items, () => {
  const seen = new Set()
  units.value = items.value.filter(i => { if (seen.has(i.business_unit_id)) return false; seen.add(i.business_unit_id); return true })
    .map(i => ({ id: i.business_unit_id, name: i.business_unit_name }))
})

onMounted(load)
watch(() => store.year, load)

async function save() {
  saving.value = true
  const body = {
    year: store.year,
    items: items.value.map(it => ({
      business_unit_id: it.business_unit_id,
      metric_type: it.metric_type,
      target_amount: it.target_amount,
      monthly_targets: it.monthly_targets,
    }))
  }
  await updateTargets(store.year, body)
  ElMessage.success('目标已保存')
  saving.value = false
}
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
      <span style="font-size:16px;font-weight:600">年度目标管理 · {{ store.year }}年</span>
      <div style="display:flex;gap:8px">
        <el-button size="small" @click="load">刷新</el-button>
        <el-button size="small" type="primary" :loading="saving" @click="save">保存</el-button>
      </div>
    </div>

    <div class="card" v-if="units.length">
      <el-table :data="units" size="small" border>
        <el-table-column prop="name" label="事业部" width="160" />
        <el-table-column v-for="m in METRICS" :key="m" :label="LABEL[m] + '目标(万)'" align="center" min-width="130">
          <template #default="{ row }">
            <el-input-number
              v-if="itemMap[row.id]?.[m]"
              v-model="itemMap[row.id][m].target_amount"
              :min="0" :precision="1" :step="100"
              size="small" style="width:120px"
              controls-position="right"
            />
            <span v-else style="color:var(--text-dim)">未设置</span>
          </template>
        </el-table-column>
      </el-table>

      <div style="margin-top:16px;font-size:12px;color:var(--text-sec)">
        ※ 修改数值后点击「保存」生效；月度分解可通过导入模板设置
      </div>
    </div>

    <el-empty v-if="!loading && !units.length" description="暂无目标数据，请导入或手动设置" />
  </div>
</template>

<style scoped>
.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:18px 20px; }
</style>
