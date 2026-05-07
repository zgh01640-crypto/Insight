<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import {
  getProducts, getProduct, createProduct, updateProduct, deleteProduct,
  getMilestones, createMilestone, updateMilestone, deleteMilestone,
  getAttachments, uploadAttachment, deleteAttachment, getAttachmentUrl,
} from '@/api'
import { ElMessage, ElMessageBox } from 'element-plus'

const store   = useAppStore()
const loading = ref(false)
const list    = ref([])
const filters = reactive({ business_unit_id: '', status: '', keyword: '' })

const STATUSES = ['立项中', '开发中', '测试中', '已上线', '延迟', '已暂停', '已终止']
const MS_STATUSES = ['未开始', '进行中', '已完成', '延期']
const STATUS_TYPE = {
  '立项中': 'info', '开发中': 'primary', '测试中': 'warning',
  '已上线': 'success', '延迟': 'danger', '已暂停': '', '已终止': 'danger',
}
const MS_STATUS_TYPE = {
  '未开始': 'info', '进行中': 'primary', '已完成': 'success', '延期': 'danger',
}

// ── 列表 ──────────────────────────────────────────────
async function load() {
  loading.value = true
  const params = {}
  if (filters.business_unit_id) params.business_unit_id = filters.business_unit_id
  if (filters.status) params.status = filters.status
  if (filters.keyword) params.keyword = filters.keyword
  const res = await getProducts(params)
  list.value = res?.data || []
  loading.value = false
}
onMounted(load)

function fmtSize(bytes) {
  if (!bytes) return '0 B'
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

// ── 弹窗状态 ─────────────────────────────────────────
const dlg    = ref(false)
const isEdit = ref(false)
const editId = ref(null)
const activeTab = ref('basic')
const saving = ref(false)

const form = reactive({
  business_unit_id: null, name: '', status: '立项中',
  initiated_at: '', product_manager: '', tech_support: '',
  dev_members: '', progress: '', risk: '', notes: '',
})

// 里程碑（弹窗内编辑缓冲）
const milestones = ref([])
const msForm = reactive({ name: '', planned_date: '', actual_date: '', status: '未开始', sort_order: 0 })
const msEditing = ref(null)  // 正在编辑的里程碑 id
const msAdding  = ref(false)

// 附件
const attachments = ref([])
const attachUploading = ref(false)

function openCreate() {
  Object.assign(form, {
    business_unit_id: store.units[0]?.id || null, name: '', status: '立项中',
    initiated_at: '', product_manager: '', tech_support: '',
    dev_members: '', progress: '', risk: '', notes: '',
  })
  milestones.value = []
  attachments.value = []
  isEdit.value = false
  editId.value = null
  activeTab.value = 'basic'
  msAdding.value = false
  msEditing.value = null
  dlg.value = true
}

async function openEdit(row) {
  const res = await getProduct(row.id)
  const p = res?.data
  if (!p) return
  Object.assign(form, {
    business_unit_id: p.business_unit_id, name: p.name, status: p.status,
    initiated_at: p.initiated_at || '', product_manager: p.product_manager || '',
    tech_support: p.tech_support || '', dev_members: p.dev_members || '',
    progress: p.progress || '', risk: p.risk || '', notes: p.notes || '',
  })
  milestones.value = p.milestones || []
  attachments.value = p.attachments || []
  isEdit.value = true
  editId.value = p.id
  activeTab.value = 'basic'
  msAdding.value = false
  msEditing.value = null
  dlg.value = true
}

async function submitForm() {
  if (!form.name.trim()) { ElMessage.warning('请填写产品名称'); return }
  if (!form.business_unit_id) { ElMessage.warning('请选择所属事业部'); return }
  saving.value = true
  try {
    const payload = { ...form }
    if (!payload.initiated_at) payload.initiated_at = null
    if (isEdit.value) {
      await updateProduct(editId.value, payload)
      ElMessage.success('已更新')
    } else {
      const res = await createProduct(payload)
      editId.value = res?.data?.id
      isEdit.value = true
      ElMessage.success('已创建')
    }
    dlg.value = false
    load()
  } finally {
    saving.value = false
  }
}

async function del(row) {
  await ElMessageBox.confirm(`确定删除产品「${row.name}」及其所有里程碑和附件？`, '删除确认', { type: 'warning' })
  await deleteProduct(row.id)
  ElMessage.success('已删除')
  load()
}

// ── 里程碑操作 ────────────────────────────────────────
function startAddMs() {
  Object.assign(msForm, { name: '', planned_date: '', actual_date: '', status: '未开始', sort_order: milestones.value.length })
  msAdding.value = true
  msEditing.value = null
}

async function confirmAddMs() {
  if (!msForm.name.trim()) { ElMessage.warning('请填写节点名称'); return }
  if (!editId.value) {
    // 未保存产品，先保存
    const payload = { ...form }
    if (!payload.initiated_at) payload.initiated_at = null
    const res = await createProduct(payload)
    editId.value = res?.data?.id
    isEdit.value = true
  }
  const data = {
    name: msForm.name,
    planned_date: msForm.planned_date || null,
    actual_date: msForm.actual_date || null,
    status: msForm.status,
    sort_order: msForm.sort_order,
  }
  const res = await createMilestone(editId.value, data)
  milestones.value.push(res?.data)
  msAdding.value = false
}

function startEditMs(m) {
  Object.assign(msForm, {
    name: m.name, planned_date: m.planned_date || '', actual_date: m.actual_date || '',
    status: m.status, sort_order: m.sort_order,
  })
  msEditing.value = m.id
  msAdding.value = false
}

async function confirmEditMs(m) {
  const data = {
    name: msForm.name,
    planned_date: msForm.planned_date || null,
    actual_date: msForm.actual_date || null,
    status: msForm.status,
    sort_order: msForm.sort_order,
  }
  await updateMilestone(editId.value, m.id, data)
  Object.assign(m, data)
  msEditing.value = null
}

async function delMs(m) {
  await deleteMilestone(editId.value, m.id)
  milestones.value = milestones.value.filter(x => x.id !== m.id)
}

// ── 附件操作 ──────────────────────────────────────────
async function handleAttachFile(file) {
  if (!editId.value) {
    // 先保存产品
    const payload = { ...form }
    if (!payload.initiated_at) payload.initiated_at = null
    const res = await createProduct(payload)
    editId.value = res?.data?.id
    isEdit.value = true
  }
  attachUploading.value = true
  try {
    const res = await uploadAttachment(editId.value, file)
    attachments.value.push(res?.data)
    ElMessage.success('上传成功')
  } catch {
    ElMessage.error('上传失败')
  } finally {
    attachUploading.value = false
  }
  return false  // 阻止 el-upload 自动上传
}

async function delAttach(a) {
  await deleteAttachment(editId.value, a.id)
  attachments.value = attachments.value.filter(x => x.id !== a.id)
  ElMessage.success('已删除')
}
</script>

<template>
  <div v-loading="loading" element-loading-background="transparent">
    <!-- 标题栏 -->
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap">
      <span style="font-size:16px;font-weight:600;margin-right:4px">产品管理台账</span>
      <el-select v-model="filters.business_unit_id" size="small" style="width:150px" clearable placeholder="全部事业部" @change="load">
        <el-option v-for="u in store.units" :key="u.id" :value="u.id" :label="u.name" />
      </el-select>
      <el-select v-model="filters.status" size="small" style="width:110px" clearable placeholder="全部状态" @change="load">
        <el-option v-for="s in STATUSES" :key="s" :value="s" :label="s" />
      </el-select>
      <el-input v-model="filters.keyword" size="small" style="width:160px" placeholder="搜索产品名称" clearable @change="load" @clear="load" />
      <el-button size="small" type="primary" style="margin-left:auto" @click="openCreate">+ 新增产品</el-button>
    </div>

    <!-- 列表 -->
    <div class="card">
      <el-table :data="list" size="small">
        <el-table-column prop="name" label="产品名称" min-width="160" show-overflow-tooltip />
        <el-table-column prop="business_unit_name" label="事业部" width="130" />
        <el-table-column label="状态" width="90" align="center">
          <template #default="{ row }">
            <el-tag size="small" :type="STATUS_TYPE[row.status]">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="initiated_at" label="立项时间" width="110" />
        <el-table-column prop="product_manager" label="产品经理" width="100" show-overflow-tooltip />
        <el-table-column prop="tech_support" label="专业支持" width="100" show-overflow-tooltip />
        <el-table-column prop="dev_members" label="研发成员" min-width="120" show-overflow-tooltip />
        <el-table-column label="里程碑" width="130" align="center">
          <template #default="{ row }">
            <span v-if="row.milestone_total">
              <el-progress
                :percentage="row.milestone_total ? Math.round(row.milestone_done / row.milestone_total * 100) : 0"
                :stroke-width="6" style="width:80px;display:inline-block"
              />
              <span style="font-size:10px;color:var(--text-sec);margin-left:4px">{{ row.milestone_done }}/{{ row.milestone_total }}</span>
            </span>
            <span v-else style="color:var(--text-dim);font-size:11px">—</span>
          </template>
        </el-table-column>
        <el-table-column label="附件" width="60" align="center">
          <template #default="{ row }">
            <span v-if="row.attachment_count" style="font-size:11px;color:var(--accent)">{{ row.attachment_count }} 个</span>
            <span v-else style="color:var(--text-dim);font-size:11px">—</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-button link size="small" @click="openEdit(row)">编辑</el-button>
            <el-button link size="small" type="danger" @click="del(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 弹窗 -->
    <el-dialog v-model="dlg" :title="isEdit ? '编辑产品' : '新增产品'" width="660px" :close-on-click-modal="false">
      <el-tabs v-model="activeTab">

        <!-- 基本信息 -->
        <el-tab-pane label="基本信息" name="basic">
          <el-form :model="form" label-width="90px" size="small" style="margin-top:8px">
            <el-form-item label="产品名称">
              <el-input v-model="form.name" placeholder="必填" />
            </el-form-item>
            <el-form-item label="所属事业部">
              <el-select v-model="form.business_unit_id" style="width:100%">
                <el-option v-for="u in store.units" :key="u.id" :value="u.id" :label="u.name" />
              </el-select>
            </el-form-item>
            <el-form-item label="产品状态">
              <el-select v-model="form.status" style="width:100%">
                <el-option v-for="s in STATUSES" :key="s" :value="s" :label="s" />
              </el-select>
            </el-form-item>
            <el-form-item label="立项时间">
              <el-input v-model="form.initiated_at" placeholder="YYYY-MM-DD" style="width:160px" />
            </el-form-item>
            <el-form-item label="产品经理">
              <el-input v-model="form.product_manager" />
            </el-form-item>
            <el-form-item label="专业支持">
              <el-input v-model="form.tech_support" />
            </el-form-item>
            <el-form-item label="研发成员">
              <el-input v-model="form.dev_members" placeholder="多人用逗号分隔" />
            </el-form-item>
            <el-form-item label="进展情况">
              <el-input v-model="form.progress" type="textarea" :rows="3" placeholder="最新进展" />
            </el-form-item>
            <el-form-item label="风险">
              <el-input v-model="form.risk" type="textarea" :rows="2" placeholder="当前风险" />
            </el-form-item>
            <el-form-item label="备注">
              <el-input v-model="form.notes" type="textarea" :rows="2" />
            </el-form-item>
          </el-form>
        </el-tab-pane>

        <!-- 里程碑 -->
        <el-tab-pane label="里程碑" name="milestones">
          <div style="margin-top:8px">
            <el-table :data="milestones" size="small" style="margin-bottom:10px">
              <el-table-column label="节点名称" min-width="140">
                <template #default="{ row }">
                  <el-input v-if="msEditing === row.id" v-model="msForm.name" size="small" />
                  <span v-else>{{ row.name }}</span>
                </template>
              </el-table-column>
              <el-table-column label="计划日期" width="110">
                <template #default="{ row }">
                  <el-input v-if="msEditing === row.id" v-model="msForm.planned_date" size="small" placeholder="YYYY-MM-DD" />
                  <span v-else>{{ row.planned_date || '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="完成日期" width="110">
                <template #default="{ row }">
                  <el-input v-if="msEditing === row.id" v-model="msForm.actual_date" size="small" placeholder="YYYY-MM-DD" />
                  <span v-else>{{ row.actual_date || '—' }}</span>
                </template>
              </el-table-column>
              <el-table-column label="状态" width="100">
                <template #default="{ row }">
                  <el-select v-if="msEditing === row.id" v-model="msForm.status" size="small" style="width:90px">
                    <el-option v-for="s in MS_STATUSES" :key="s" :value="s" :label="s" />
                  </el-select>
                  <el-tag v-else size="small" :type="MS_STATUS_TYPE[row.status]">{{ row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column label="操作" width="90" align="center">
                <template #default="{ row }">
                  <template v-if="msEditing === row.id">
                    <el-button link size="small" type="primary" @click="confirmEditMs(row)">保存</el-button>
                    <el-button link size="small" @click="msEditing = null">取消</el-button>
                  </template>
                  <template v-else>
                    <el-button link size="small" @click="startEditMs(row)">编辑</el-button>
                    <el-button link size="small" type="danger" @click="delMs(row)">删除</el-button>
                  </template>
                </template>
              </el-table-column>
            </el-table>

            <!-- 新增里程碑行 -->
            <div v-if="msAdding" class="ms-add-row">
              <el-input v-model="msForm.name" size="small" placeholder="节点名称" style="width:140px" />
              <el-input v-model="msForm.planned_date" size="small" placeholder="计划日期" style="width:110px" />
              <el-input v-model="msForm.actual_date" size="small" placeholder="完成日期" style="width:110px" />
              <el-select v-model="msForm.status" size="small" style="width:90px">
                <el-option v-for="s in MS_STATUSES" :key="s" :value="s" :label="s" />
              </el-select>
              <el-button size="small" type="primary" @click="confirmAddMs">确定</el-button>
              <el-button size="small" @click="msAdding = false">取消</el-button>
            </div>
            <el-button v-else size="small" @click="startAddMs">+ 添加里程碑</el-button>
          </div>
        </el-tab-pane>

        <!-- 附件 -->
        <el-tab-pane label="附件" name="attachments">
          <div style="margin-top:8px">
            <!-- 上传区 -->
            <el-upload
              :before-upload="handleAttachFile"
              :show-file-list="false"
              :disabled="attachUploading"
              drag
              style="margin-bottom:12px"
            >
              <div style="padding:16px 0;color:var(--text-sec);font-size:13px">
                {{ attachUploading ? '上传中...' : '点击或拖拽文件到此处上传（支持任意格式）' }}
              </div>
            </el-upload>

            <!-- 附件列表 -->
            <el-table :data="attachments" size="small">
              <el-table-column prop="filename" label="文件名" min-width="200" show-overflow-tooltip />
              <el-table-column label="大小" width="90" align="right">
                <template #default="{ row }">{{ fmtSize(row.file_size) }}</template>
              </el-table-column>
              <el-table-column label="上传时间" width="150">
                <template #default="{ row }">{{ row.uploaded_at?.slice(0,16) }}</template>
              </el-table-column>
              <el-table-column label="操作" width="100" align="center">
                <template #default="{ row }">
                  <a :href="getAttachmentUrl(row.id)" target="_blank" style="font-size:12px;color:var(--accent);margin-right:8px">下载</a>
                  <el-button link size="small" type="danger" @click="delAttach(row)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </el-tab-pane>

      </el-tabs>

      <template #footer>
        <el-button @click="dlg = false">关闭</el-button>
        <el-button v-if="activeTab === 'basic'" type="primary" :loading="saving" @click="submitForm">
          {{ isEdit ? '保存更新' : '创建产品' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.card { background:var(--bg-card); border:1px solid var(--bg-border); border-radius:10px; padding:18px 20px; }
.ms-add-row { display:flex; align-items:center; gap:6px; flex-wrap:wrap; margin-bottom:4px; }
</style>
