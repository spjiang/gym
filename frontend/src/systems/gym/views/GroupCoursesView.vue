<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { merchantsWithSystem } from '../../../core/nav/systems'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
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
type Booking = {
  id: number
  session_id: number
  member_id: number
  status: string
  member?: { id: number; name: string; phone: string } | null
}

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const coaches = ref<Coach[]>([])
const courses = ref<Course[]>([])
const sessions = ref<Session[]>([])
const bookings = ref<Booking[]>([])
const merchantId = ref<number | undefined>()
const selectedSessionId = ref<number | undefined>()
const loading = ref(false)

const courseDialog = ref(false)
const sessionDialog = ref(false)
const bookDialog = ref(false)
const submitting = ref(false)

const courseFormRef = ref<FormInstance>()
const sessionFormRef = ref<FormInstance>()
const bookFormRef = ref<FormInstance>()

const courseForm = reactive({ name: '', default_capacity: 20 })
const sessionForm = reactive({
  course_id: undefined as number | undefined,
  coach_id: undefined as number | undefined,
  starts_at: '',
  ends_at: '',
  room: '',
  capacity: 20,
})
const bookForm = reactive({ member_id: undefined as number | undefined })

const courseRules: FormRules = {
  name: [{ required: true, message: '请填写课程名称', trigger: 'blur' }],
}

const sessionRules: FormRules = {
  course_id: [{ required: true, message: '请选择课程', trigger: 'change' }],
  coach_id: [{ required: true, message: '请选择教练', trigger: 'change' }],
  starts_at: [{ required: true, message: '请填写开始时间', trigger: 'blur' }],
  ends_at: [{ required: true, message: '请填写结束时间', trigger: 'blur' }],
}

const bookRules: FormRules = {
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
}

const selectedSession = computed(() =>
  sessions.value.find((s) => s.id === selectedSessionId.value),
)

function courseName(id: number) {
  return courses.value.find((c) => c.id === id)?.name || `#${id}`
}

function coachName(id: number) {
  return coaches.value.find((c) => c.id === id)?.display_name || `#${id}`
}

function memberName(id: number, row?: Booking) {
  if (row?.member) return `${row.member.name} ${row.member.phone}`
  const m = members.value.find((x) => x.id === id)
  return m ? `${m.name} ${m.phone}` : `#${id}`
}

function bookingStatusLabel(s: string) {
  return { booked: '已预约', attended: '已出席', no_show: '未出席', cancelled: '已取消' }[s] || s
}

async function refresh() {
  loading.value = true
  try {
    const [m, mem] = await Promise.all([
      http.get('/merchants'),
      http.get('/members', { params: { page: 1, page_size: 100 } }),
    ])
    merchants.value = merchantsWithSystem(m.data, 'gym')
    members.value = mem.data.items
    if (!merchantId.value && merchants.value[0]) merchantId.value = merchants.value[0].id
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = merchants.value[0]?.id
    }
    if (!merchantId.value) return
    const [c, co, s] = await Promise.all([
      http.get('/group-courses', { params: { merchant_id: merchantId.value } }),
      http.get('/coaches', { params: { merchant_id: merchantId.value } }),
      http.get('/group-sessions', { params: { merchant_id: merchantId.value } }),
    ])
    courses.value = c.data
    coaches.value = co.data.filter((x: Coach) => x.is_active)
    sessions.value = s.data
    if (selectedSessionId.value) await loadBookings()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadBookings() {
  if (!selectedSessionId.value) return
  const { data } = await http.get('/group-bookings', {
    params: {
      merchant_id: merchantId.value,
      session_id: selectedSessionId.value,
      page: 1,
      page_size: 100,
    },
  })
  bookings.value = data.items
}

function openCourseDialog() {
  courseForm.name = ''
  courseForm.default_capacity = 20
  courseFormRef.value?.clearValidate()
  courseDialog.value = true
}

async function createCourse() {
  const ok = await courseFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/group-courses', {
      merchant_id: merchantId.value,
      name: courseForm.name.trim(),
      default_capacity: courseForm.default_capacity,
    })
    ElMessage.success('课程已创建')
    courseDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openSessionDialog() {
  sessionForm.course_id = courses.value[0]?.id
  sessionForm.coach_id = coaches.value[0]?.id
  sessionForm.starts_at = ''
  sessionForm.ends_at = ''
  sessionForm.room = ''
  sessionForm.capacity = courses.value[0]?.default_capacity || 20
  sessionFormRef.value?.clearValidate()
  sessionDialog.value = true
}

async function createSession() {
  const ok = await sessionFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/group-sessions', {
      merchant_id: merchantId.value,
      course_id: sessionForm.course_id,
      coach_id: sessionForm.coach_id,
      starts_at: new Date(sessionForm.starts_at).toISOString(),
      ends_at: new Date(sessionForm.ends_at).toISOString(),
      room: sessionForm.room,
      capacity: sessionForm.capacity,
    })
    ElMessage.success('场次已排')
    sessionDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '排课失败')
  } finally {
    submitting.value = false
  }
}

function openBookDialog() {
  bookForm.member_id = undefined
  bookFormRef.value?.clearValidate()
  bookDialog.value = true
}

async function book() {
  const ok = await bookFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/group-bookings', {
      merchant_id: merchantId.value,
      session_id: selectedSessionId.value,
      member_id: bookForm.member_id,
    })
    ElMessage.success('代约成功')
    bookDialog.value = false
    await loadBookings()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '预约失败')
  } finally {
    submitting.value = false
  }
}

async function cancel(id: number) {
  await http.post(`/group-bookings/${id}/cancel`, { force: true })
  ElMessage.success('已取消')
  await loadBookings()
}

async function checkin(id: number, status: string) {
  await http.post(`/group-bookings/${id}/checkin`, { status })
  ElMessage.success('签到已更新')
  await loadBookings()
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>团课排课</h3>
      <div class="toolbar-actions">
        <el-button type="primary" plain @click="openCourseDialog">新建团课模板</el-button>
        <el-button type="primary" @click="openSessionDialog">排场次</el-button>
      </div>
    </div>

    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <h3 class="section-title">团课模板</h3>
    <el-table :data="courses" v-loading="loading" stripe style="margin-bottom: 28px">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="default_capacity" label="默认上限" width="110" />
    </el-table>

    <h3 class="section-title">场次</h3>
    <el-table
      :data="sessions"
      v-loading="loading"
      stripe
      highlight-current-row
      @current-change="(row: Session | undefined) => { selectedSessionId = row?.id; loadBookings() }"
    >
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="课程" width="140">
        <template #default="{ row }">{{ courseName(row.course_id) }}</template>
      </el-table-column>
      <el-table-column label="教练" width="120">
        <template #default="{ row }">{{ coachName(row.coach_id) }}</template>
      </el-table-column>
      <el-table-column prop="starts_at" label="开始" />
      <el-table-column prop="capacity" label="上限" width="80" />
      <el-table-column prop="room" label="教室" width="100" />
      <el-table-column prop="status" label="状态" width="90" />
    </el-table>

    <el-card v-if="selectedSessionId" header="预约名单" style="margin-top: 16px">
      <div class="card-toolbar">
        <span class="card-hint">场次 #{{ selectedSessionId }} · {{ courseName(selectedSession?.course_id || 0) }}</span>
        <el-button type="primary" plain size="small" @click="openBookDialog">代约</el-button>
      </div>
      <el-table :data="bookings" stripe style="margin-top: 12px">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="会员" width="220">
          <template #default="{ row }">{{ memberName(row.member_id, row) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.status === 'attended' ? 'success' : row.status === 'cancelled' ? 'info' : 'warning'"
            >
              {{ bookingStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button v-if="row.status === 'booked'" link type="danger" @click="cancel(row.id)">取消</el-button>
            <el-button v-if="row.status === 'booked'" link type="success" @click="checkin(row.id, 'attended')">出席</el-button>
            <el-button v-if="row.status === 'booked'" link @click="checkin(row.id, 'no_show')">未出席</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 新建团课模板弹窗 -->
    <el-dialog v-model="courseDialog" title="新建团课模板" width="460px" destroy-on-close>
      <el-form ref="courseFormRef" :model="courseForm" :rules="courseRules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="courseForm.name" placeholder="如：燃脂操 / 瑜伽" maxlength="128" />
        </el-form-item>
        <el-form-item label="默认上限">
          <el-input-number v-model="courseForm.default_capacity" :min="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="courseDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createCourse">创建</el-button>
      </template>
    </el-dialog>

    <!-- 排场次弹窗 -->
    <el-dialog v-model="sessionDialog" title="排场次" width="520px" destroy-on-close>
      <el-form ref="sessionFormRef" :model="sessionForm" :rules="sessionRules" label-width="90px">
        <el-form-item label="课程" prop="course_id">
          <el-select v-model="sessionForm.course_id" style="width: 100%">
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教练" prop="coach_id">
          <el-select v-model="sessionForm.coach_id" style="width: 100%">
            <el-option v-for="c in coaches" :key="c.id" :label="c.display_name" :value="c.id" />
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
      </el-form>
      <template #footer>
        <el-button @click="sessionDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createSession">排课</el-button>
      </template>
    </el-dialog>

    <!-- 代约弹窗 -->
    <el-dialog v-model="bookDialog" title="代会员预约" width="460px" destroy-on-close>
      <el-form ref="bookFormRef" :model="bookForm" :rules="bookRules" label-width="90px">
        <el-form-item label="会员" prop="member_id">
          <el-select v-model="bookForm.member_id" filterable style="width: 100%">
            <el-option v-for="x in members" :key="x.id" :label="`${x.name} ${x.phone}`" :value="x.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="bookDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="book">确认预约</el-button>
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
  margin: 0;
  font-size: 1.1rem;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.section-title {
  margin: 0 0 12px;
  font-size: 0.95rem;
}

.card-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.card-hint {
  font-size: 0.85rem;
  color: var(--admin-ink-muted);
}
</style>
