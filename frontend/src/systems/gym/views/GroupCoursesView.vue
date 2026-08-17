<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { sessionStatusLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Coach = { id: number; display_name: string; is_active: boolean }
type Course = { id: number; name: string; default_capacity: number }
type Session = {
  id: number
  course_id: number
  coach_id: number
  starts_at: string
  ends_at: string
  room: string | null
  capacity: number
  status: string
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const router = useRouter()
const merchants = ref<Merchant[]>([])
const coaches = ref<Coach[]>([])
const courses = ref<Course[]>([])
const sessions = ref<Session[]>([])
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({
  q: '',
  course_id: undefined as number | undefined,
  coach_id: undefined as number | undefined,
  status: '' as string,
  on_date: '' as string,
})

const sessionDialog = ref(false)
const detailVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const detail = ref<Session | null>(null)

const sessionFormRef = ref<FormInstance>()

const sessionForm = reactive({
  course_id: undefined as number | undefined,
  coach_id: undefined as number | undefined,
  starts_at: '',
  ends_at: '',
  room: '',
  capacity: 20,
  status: 'open',
})
const sessionRules: FormRules = {
  course_id: [{ required: true, message: '请选择课程', trigger: 'change' }],
  coach_id: [{ required: true, message: '请选择教练', trigger: 'change' }],
  starts_at: [{ required: true, message: '请填写开始时间', trigger: 'blur' }],
  ends_at: [{ required: true, message: '请填写结束时间', trigger: 'blur' }],
}

const activeCoaches = computed(() => coaches.value.filter((x) => x.is_active))

function courseName(id: number) {
  return courses.value.find((c) => c.id === id)?.name || `#${id}`
}

function coachName(id: number) {
  return coaches.value.find((c) => c.id === id)?.display_name || `#${id}`
}

function fmtTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function toPickerValue(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso.slice(0, 19)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}:00`
}

async function refresh() {
  loading.value = true
  try {
    const { data: merchantRows } = await http.get('/merchants')
    merchants.value = merchantsWithSystem(merchantRows, 'gym')
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const [c, co, s] = await Promise.all([
      http.get('/group-courses', { params: { merchant_id: merchantId.value, page: 1, page_size: 100 } }),
      http.get('/coaches', { params: { merchant_id: merchantId.value, page: 1, page_size: 100 } }),
      http.get<Page<Session>>('/group-sessions', {
        params: {
          merchant_id: merchantId.value,
          q: query.q.trim() || undefined,
          course_id: query.course_id,
          coach_id: query.coach_id,
          status: query.status || undefined,
          on_date: query.on_date || undefined,
          page: page.value,
          page_size: pageSize.value,
        },
      }),
    ])
    courses.value = c.data.items
    coaches.value = co.data.items
    sessions.value = s.data.items
    total.value = s.data.total
    if (detail.value) {
      const latest = sessions.value.find((x) => x.id === detail.value?.id)
      if (latest) detail.value = latest
    }
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void refresh()
}

function resetSearch() {
  query.q = ''
  query.course_id = undefined
  query.coach_id = undefined
  query.status = ''
  query.on_date = ''
  page.value = 1
  void refresh()
}

function openDetail(row: Session) {
  detail.value = row
  detailVisible.value = true
}

function resetSessionForm() {
  sessionForm.course_id = courses.value[0]?.id
  sessionForm.coach_id = activeCoaches.value[0]?.id
  sessionForm.starts_at = ''
  sessionForm.ends_at = ''
  sessionForm.room = ''
  sessionForm.capacity = courses.value[0]?.default_capacity || 20
  sessionForm.status = 'open'
}

function openSessionDialog() {
  editingId.value = null
  resetSessionForm()
  sessionFormRef.value?.clearValidate()
  sessionDialog.value = true
}

function openEdit(row: Session) {
  editingId.value = row.id
  sessionForm.course_id = row.course_id
  sessionForm.coach_id = row.coach_id
  sessionForm.starts_at = toPickerValue(row.starts_at)
  sessionForm.ends_at = toPickerValue(row.ends_at)
  sessionForm.room = row.room || ''
  sessionForm.capacity = row.capacity
  sessionForm.status = row.status
  sessionFormRef.value?.clearValidate()
  sessionDialog.value = true
}

async function saveSession() {
  const ok = await sessionFormRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    const payload = {
      merchant_id: mid,
      course_id: sessionForm.course_id,
      coach_id: sessionForm.coach_id,
      starts_at: new Date(sessionForm.starts_at).toISOString(),
      ends_at: new Date(sessionForm.ends_at).toISOString(),
      room: sessionForm.room,
      capacity: sessionForm.capacity,
      status: sessionForm.status,
    }
    if (editingId.value) {
      await http.patch(`/group-sessions/${editingId.value}`, payload)
      ElMessage.success('场次已更新')
    } else {
      await http.post('/group-sessions', payload)
      ElMessage.success('场次已排')
    }
    sessionDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : editingId.value ? '更新失败' : '排课失败')
  } finally {
    submitting.value = false
  }
}

async function removeSession(row: Session) {
  try {
    await ElMessageBox.confirm(
      `确认删除「${courseName(row.course_id)}」这场课？删除后不可预约，已预约会员会被取消；记录仍会保留。`,
      '删除确认',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消', appendTo: document.body },
    )
  } catch {
    return
  }
  try {
    await http.delete(`/group-sessions/${row.id}`)
    ElMessage.success('场次已删除')
    if (detail.value?.id === row.id) detailVisible.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>团课排课</h3>
        <p class="lead">安排场次。课种请先在「团课管理 → 团课模板」建好；代约请到「团课管理 → 团课代约」。</p>
      </div>
      <div class="toolbar-actions">
        <el-button @click="router.push('/group-templates')">团课模板</el-button>
        <el-button type="primary" @click="openSessionDialog">排场次</el-button>
      </div>
    </div>

    <el-alert
      v-if="!loading && courses.length === 0"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
      title="还没有团课模板，无法排场次。请先到「团课管理 → 团课模板」创建课种。"
    />

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="课程 / 教练 / 教室 / ID" style="width: 200px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="课程">
        <el-select v-model="query.course_id" clearable placeholder="全部" style="width: 140px">
          <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="教练">
        <el-select v-model="query.coach_id" clearable placeholder="全部" style="width: 140px">
          <el-option v-for="c in coaches" :key="c.id" :label="c.display_name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="可预约" value="open" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期">
        <el-date-picker
          v-model="query.on_date"
          type="date"
          value-format="YYYY-MM-DD"
          placeholder="上课日期"
          style="width: 150px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="sessions" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="课程" min-width="160">
        <template #default="{ row }">{{ courseName(row.course_id) }}</template>
      </el-table-column>
      <el-table-column label="教练" min-width="140">
        <template #default="{ row }">{{ coachName(row.coach_id) }}</template>
      </el-table-column>
      <el-table-column label="开始" min-width="180">
        <template #default="{ row }">{{ fmtTime(row.starts_at) }}</template>
      </el-table-column>
      <el-table-column prop="capacity" label="上限" width="80" />
      <el-table-column prop="room" label="教室" min-width="140" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">{{ sessionStatusLabel(row.status) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.status !== 'cancelled'" link type="danger" @click="removeSession(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="refresh"
        @size-change="
          () => {
            page = 1
            refresh()
          }
        "
      />
    </div>

    <el-drawer v-model="detailVisible" title="场次详情" size="520px" destroy-on-close>
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="课程">{{ courseName(detail.course_id) }}</el-descriptions-item>
          <el-descriptions-item label="教练">{{ coachName(detail.coach_id) }}</el-descriptions-item>
          <el-descriptions-item label="开始">{{ fmtTime(detail.starts_at) }}</el-descriptions-item>
          <el-descriptions-item label="结束">{{ fmtTime(detail.ends_at) }}</el-descriptions-item>
          <el-descriptions-item label="教室">{{ detail.room || '—' }}</el-descriptions-item>
          <el-descriptions-item label="上限">{{ detail.capacity }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ sessionStatusLabel(detail.status) }}</el-descriptions-item>
        </el-descriptions>
        <div class="detail-actions">
          <el-button type="primary" plain @click="openEdit(detail)">编辑</el-button>
          <el-button v-if="detail.status !== 'cancelled'" type="danger" plain @click="removeSession(detail)">删除</el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 排场次 / 编辑场次 -->
    <el-dialog v-model="sessionDialog" :title="editingId ? '编辑场次' : '排场次'" width="520px" destroy-on-close>
      <el-form ref="sessionFormRef" :model="sessionForm" :rules="sessionRules" label-width="90px">
        <el-form-item label="课程" prop="course_id">
          <el-select v-model="sessionForm.course_id" style="width: 100%">
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教练" prop="coach_id">
          <el-select v-model="sessionForm.coach_id" style="width: 100%">
            <el-option v-for="c in activeCoaches" :key="c.id" :label="c.display_name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始" prop="starts_at">
          <el-date-picker
            v-model="sessionForm.starts_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择开始时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="结束" prop="ends_at">
          <el-date-picker
            v-model="sessionForm.ends_at"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="选择结束时间"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="教室">
          <el-input v-model="sessionForm.room" placeholder="如：操房 1" maxlength="64" />
        </el-form-item>
        <el-form-item label="上限">
          <el-input-number v-model="sessionForm.capacity" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="editingId" label="状态">
          <el-select v-model="sessionForm.status" style="width: 100%">
            <el-option label="可预约" value="open" />
            <el-option label="已取消" value="cancelled" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="sessionDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveSession">
          {{ editingId ? '保存' : '排课' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 20px;
}

.toolbar h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}

.lead {
  margin: 0;
  max-width: 640px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--el-text-color-secondary);
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.filters {
  margin-bottom: 8px;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 16px;
}
</style>
