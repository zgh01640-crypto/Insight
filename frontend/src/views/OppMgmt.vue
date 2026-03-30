<script setup>
import { ref, onMounted, reactive } from 'vue'
import { useAppStore } from '@/stores/app'
import { getOpportunities, createOpportunity, updateOpportunity, deleteOpportunity } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const store   = useAppStore()
const loading = ref(false)
const list    = ref([])
const dlg     = ref(false)
const isEdit  = ref(false)
const form    = reactive({ name:'', business_unit_id:'', metric_type:'contract', year: new Date().getFullYear(), quarter:'Q1', estimated_amount:0, estimated_date:'', stage:'线索', status:'进行中', notes:'' })
const editId  = ref(null)
const filters = reactive({ year: new Date().getFullYear(), quarter:'', business_unit_id:'', metric_type:'' })

const STAGES  = ['线索','立项','报价','签约跟进','已完成']
const STATUSES= ['进行中','已赢单','已输单','已搁置']
const STAGE_TYPE = { '线索':'info','立项':'','报价':'warning','签约跟进':'success','已完成':'success' }
const STATUS_TYPE= { '进行中':'primary','已赢单':'success','已输单':'danger','已搁置':'info' }

async function load() {
  loading.value = true
  const params = {}
  if (filters.year) params.year = filters.year
  if (filters.quarter) params.quarter = filters.quarter
  if (filters.business_unit_id) params.business_unit_id = filters.business_unit_id
  if (filters.metric_type) params.metric_type = filters.metric_type
  const res = await getOpportunities(params)
  list.value = res?.data || []
  loading.value = false
}
onMounted(load)

function openCreate() {
  Object.assign(form, { name:'', business_unit_id: store.units[0]?.id || '', metric_type:'contract', year:store.year, quarter:'Q1', estimated_amount:0, estimated_date:'', stage:'线索', status:'进行中', notes:'' })
  isEdit.value = false; editId.value = null; dlg.value = true
}
function openEdit(row) {
  Object.assign(form, { ...row, business_unit_id: row.business_unit_id })
  isEdit.value = true; editId.value = row.id; dlg.value = true
}
async function submitForm() {
  if (isEdit.value) { await updateOpportunity(editId.value, { ...form }); ElMessage.success('已更新') }
  else { await createOpportunity({ ...form }); ElMessage.success('已创建') }
  dlg.value = false; load()
}
async function del(row) {
  await ElMessageBox.confirm(`确定删除「${row.name}」？`, '删除确认', { type: 'warning' })
  await deleteOpportunity(row.id)
  ElMessage.success('已删除'); load()
}
const METRIC_LABEL = { contract:'合同', revenue:'收入', payment:'回款' }
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap">
      <span style="font-size:16px;font-weight:600;margin-right:6px">商机管理</span>
      <el-select v-model="filters.year" size="small" style="width:90px" @change="load">
        <el-option :value="2026" label="2026年" /><el-option :value="2025" label="2025年" />
      </el-select>
      <el-select v-model="filters.quarter" size="small" style="width:90px" clearable placeholder="全部季度" @change="load">
        <el-option v-for="q in ['Q1','Q2','Q3','Q4']" :key="q" :value="q" :label="q" />
      </el-select>
      <el-select v-model="filters.business_unit_id" size="small" style="width:150px" clearable placeholder="全部事业部" @change="load">
        <el-option v-for="u in store.units" :key="u.id" :value="u.id" :label="u.name" />
      </el-select>
      <el-select v-model="filters.metric_type" size="small" style="width:90px" clearable placeholder="全部指标" @change="load">
        <el-option value="contract" label="合同" /><el-option value="revenue" label="收入" /><el-option value="payment" label="回款" />
      </el-select>
      <el-button size="small" type="primary" style="margin-left:auto" @click="openCreate">+ 新增商机</el-button>
    </div>

    <div class="card">
      <el-table :data="list" size="small">
        <el-table-column prop="name" label="商机名称" min-width="160" />
        <el-table-column prop="business_unit_name" label="事业部" width="130" />
        <el-table-column label="指标" width="70" align="center">
          <template #default="{ row }">{{ METRIC_LABEL[row.metric_type] }}</template>
        </el-table-column>
        <el-table-column prop="quarter" label="季度" width="60" align="center" />
        <el-table-column prop="estimated_amount" label="金额(万)" width="90" align="right">
          <template #default="{ row }"><span style="font-family:var(--mono)">{{ row.estimated_amount.toLocaleString() }}</span></template>
        </el-table-column>
        <el-table-column prop="estimated_date" label="预计时间" width="110" />
        <el-table-column prop="stage" label="阶段" width="100" align="center">
          <template #default="{ row }"><el-tag size="small" :type="STAGE_TYPE[row.stage]">{{ row.stage }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }"><el-tag size="small" :type="STATUS_TYPE[row.status]">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button link size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link size="small" type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Dialog -->
    <el-dialog v-model="dlg" :title="isEdit ? '编辑商机' : '新增商机'" width="520px">
      <el-form :model="form" label-width="90px" size="small">
        <el-form-item label="商机名称"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="所属事业部">
          <el-select v-model="form.business_unit_id" style="width:100%">
            <el-option v-for="u in store.units" :key="u.id" :value="u.id" :label="u.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="指标类型">
          <el-select v-model="form.metric_type" style="width:100%">
            <el-option value="contract" label="合同" /><el-option value="revenue" label="收入" /><el-option value="payment" label="回款" />
          </el-select>
        </el-form-item>
        <el-form-item label="所属年度"><el-input-number v-model="form.year" :min="2020" :max="2040" /></el-form-item>
        <el-form-item label="所属季度">
          <el-select v-model="form.quarter"><el-option v-for="q in ['Q1','Q2','Q3','Q4']" :key="q" :value="q" :label="q" /></el-select>
        </el-form-item>
        <el-form-item label="预计金额(万)"><el-input-number v-model="form.estimated_amount" :min="0" :precision="1" /></el-form-item>
        <el-form-item label="预计时间"><el-input v-model="form.estimated_date" placeholder="YYYY-MM-DD" /></el-form-item>
        <el-form-item label="商机阶段">
          <el-select v-model="form.stage"><el-option v-for="s in STAGES" :key="s" :value="s" :label="s" /></el-select>
        </el-form-item>
        <el-form-item label="商机状态">
          <el-select v-model="form.status"><el-option v-for="s in STATUSES" :key="s" :value="s" :label="s" /></el-select>
        </el-form-item>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dlg=false">取消</el-button>
        <el-button type="primary" @click="submitForm">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:18px 20px; }
</style>
