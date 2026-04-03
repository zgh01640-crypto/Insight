<script setup>
import { ref, onMounted, reactive } from 'vue'
import { useAppStore } from '@/stores/app'
import { getCollections, createCollection, updateCollection, deleteCollection, importCollections } from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const store   = useAppStore()
const loading = ref(false)
const list    = ref([])
const dlg     = ref(false)
const isEdit  = ref(false)
const form    = reactive({
  year: new Date().getFullYear(),
  business_unit_id: '',
  project_name: '',
  client_name: '',
  amount: 0,
  status: '催收中',
  notes: ''
})
const editId  = ref(null)
const filters = reactive({
  year: new Date().getFullYear(),
  business_unit_id: '',
  status: ''
})

const STATUSES = ['催收中', '已回款', '已核销']
const STATUS_TYPE = { '催收中': 'danger', '已回款': 'success', '已核销': 'info' }

async function load() {
  loading.value = true
  try {
    const params = {}
    if (filters.year) params.year = filters.year
    if (filters.business_unit_id) params.business_unit_id = filters.business_unit_id
    if (filters.status) params.status = filters.status
    const res = await getCollections(params)
    list.value = res?.data || []
  } finally {
    loading.value = false
  }
}
onMounted(load)

function openCreate() {
  Object.assign(form, {
    year: store.year || new Date().getFullYear(),
    business_unit_id: store.units[0]?.id || '',
    project_name: '',
    client_name: '',
    amount: 0,
    status: '催收中',
    notes: ''
  })
  isEdit.value = false
  editId.value = null
  dlg.value = true
}

function openEdit(row) {
  Object.assign(form, { ...row })
  isEdit.value = true
  editId.value = row.id
  dlg.value = true
}

async function submitForm() {
  if (isEdit.value) {
    await updateCollection(editId.value, { ...form })
    ElMessage.success('已更新')
  } else {
    await createCollection({ ...form })
    ElMessage.success('已创建')
  }
  dlg.value = false
  load()
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除「${row.project_name}」？`, '删除确认', { type: 'warning' })
  await deleteCollection(row.id)
  ElMessage.success('已删除')
  load()
}

function handleFileSelect(event) {
  const file = event.target.files?.[0]
  if (file) {
    handleImport(file)
    event.target.value = '' // 重置 input
  }
}

async function handleImport(file) {
  try {
    loading.value = true
    const res = await importCollections(file)
    const { success, fail } = res.data || {}
    ElMessage.success(`导入完成：${success || 0}条成功${fail > 0 ? `，${fail}条失败` : ''}`)
    await load()
  } catch (err) {
    ElMessage.error('导入失败，请检查文件格式')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap">
      <span style="font-size:16px;font-weight:600;margin-right:6px">催收项目管理</span>
      <el-select v-model="filters.year" size="small" style="width:90px" @change="load">
        <el-option :value="2026" label="2026年" />
        <el-option :value="2025" label="2025年" />
      </el-select>
      <el-select v-model="filters.business_unit_id" size="small" style="width:150px" clearable placeholder="全部事业部" @change="load">
        <el-option v-for="u in store.units" :key="u.id" :value="u.id" :label="u.name" />
      </el-select>
      <el-select v-model="filters.status" size="small" style="width:100px" clearable placeholder="全部状态" @change="load">
        <el-option v-for="s in STATUSES" :key="s" :value="s" :label="s" />
      </el-select>
      <div style="margin-left:auto;display:flex;gap:8px">
        <el-button size="small" type="primary" @click="openCreate">+ 新增</el-button>
        <el-button size="small" @click="$refs.fileInput?.click()">导入 Excel</el-button>
        <input ref="fileInput" type="file" accept=".xlsx,.xls,.csv" style="display:none" @change="handleFileSelect" />
      </div>
    </div>

    <div class="card">
      <el-table :data="list" size="small">
        <el-table-column prop="year" label="年份" width="70" align="center" />
        <el-table-column prop="business_unit_name" label="事业部" width="130" />
        <el-table-column prop="project_name" label="项目名称" min-width="180" />
        <el-table-column prop="client_name" label="单位名称" min-width="160" />
        <el-table-column prop="amount" label="欠款金额(万)" width="110" align="right">
          <template #default="{ row }"><span style="font-family:var(--mono)">{{ row.amount.toLocaleString() }}</span></template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="90" align="center">
          <template #default="{ row }"><el-tag size="small" :type="STATUS_TYPE[row.status]">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="notes" label="备注" min-width="150" show-overflow-tooltip />
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button link size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link size="small" type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- Dialog -->
    <el-dialog v-model="dlg" :title="isEdit ? '编辑催收项目' : '新增催收项目'" width="520px">
      <el-form :model="form" label-width="90px" size="small">
        <el-form-item label="年份"><el-input-number v-model="form.year" :min="2020" :max="2040" style="width:100%" /></el-form-item>
        <el-form-item label="所属事业部">
          <el-select v-model="form.business_unit_id" style="width:100%">
            <el-option v-for="u in store.units" :key="u.id" :value="u.id" :label="u.name" />
          </el-select>
        </el-form-item>
        <el-form-item label="项目名称"><el-input v-model="form.project_name" /></el-form-item>
        <el-form-item label="单位名称"><el-input v-model="form.client_name" /></el-form-item>
        <el-form-item label="欠款金额(万)"><el-input-number v-model="form.amount" :min="0" :precision="2" style="width:100%" /></el-form-item>
        <el-form-item label="状态">
          <el-select v-model="form.status" style="width:100%">
            <el-option v-for="s in STATUSES" :key="s" :value="s" :label="s" />
          </el-select>
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

<style>
.el-table__body-wrapper .el-scrollbar__bar .el-scrollbar__thumb,
.el-table__footer-wrapper .el-scrollbar__bar .el-scrollbar__thumb {
  background-color: #2d3f52 !important;
  opacity: 1 !important;
}
.el-table__body-wrapper .el-scrollbar__bar,
.el-table__footer-wrapper .el-scrollbar__bar {
  opacity: 1 !important;
  height: 6px !important;
  bottom: 0 !important;
}
.el-table__body-wrapper .el-scrollbar__bar .el-scrollbar__thumb:hover {
  background-color: #4a6580 !important;
}
</style>
