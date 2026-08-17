<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { bookingStatusLabel, sessionStatusLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Coach = { id: number; display_name: string }
type Course = { id: number; name: string }
type Session = {
  id: number
  course_id: number
  coach_id: number
  starts_at: string
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
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const coaches = ref<Coach[]>([])
const courses = ref<Course[]>([])
const sessions = ref<Session[]>([])
const bookings = ref<Booking[]>([])
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
  status: 'open' as string,
})

const bookDialog = ref(false)
const bookingListDialog = ref(false)
const bookingsLoading = ref(false)
const submitting = ref(false)
const currentSession = ref<Session | null>(null)
const bookFormRef = ref<FormInstance>()
const bookForm = reactive({ member_id: undefined as number | undefined })
const bookRules: FormRules = {
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
}

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

function fmtTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
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
          page: page.value,
          page_size: pageSize.value,
        },
      }),
    ])
    courses.value = c.data.items
    coaches.value = co.data.items
    sessions.value = s.data.items
    total.value = s.data.total
    if (currentSession.value) {
      const latest = sessions.value.find((x) => x.id === currentSession.value?.id)
      if (latest) currentSession.value = latest
      if (bookingListDialog.value) await loadBookings(currentSession.value.id)
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
  query.status = 'open'
  page.value = 1
  void refresh()
}

async function loadBookings(sessionId: number) {
  bookingsLoading.value = true
  try {
    const { data } = await http.get('/group-bookings', {
      params: {
        merchant_id: merchantId.value,
        session_id: sessionId,
        page: 1,
        page_size: 100,
      },
    })
    bookings.value = data.items
  } finally {
    bookingsLoading.value = false
  }
}

function openBookingList(row: Session) {
  currentSession.value = row
  bookingListDialog.value = true
  void loadBookings(row.id)
}

function openBookDialog(row?: Session) {
  if (row) currentSession.value = row
  if (!currentSession.value) return
  bookForm.member_id = undefined
  bookFormRef.value?.clearValidate()
  bookDialog.value = true
}

async function book() {
  const ok = await bookFormRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid || !currentSession.value) return
  submitting.value = true
  try {
    await http.post('/group-bookings', {
      merchant_id: mid,
      session_id: currentSession.value.id,
      member_id: bookForm.member_id,
    })
    ElMessage.success('代约成功')
    bookDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '预约失败')
  } finally {
    submitting.value = false
  }
}

async function cancel(id: number) {
  await http.post(`/group-bookings/${id}/cancel`, { force: true })
  ElMessage.success('已取消')
  if (currentSession.value) await loadBookings(currentSession.value.id)
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>团课代约</h3>
        <p class="lead">前台为会员占名额或取消预约。排场次请到「团课排课」，点名请到「团课签到」。</p>
      </div>
    </div>

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
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="sessions" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="场次" width="80" />
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
      <el-table-column label="操作" width="180">
        <template #default="{ row }">
          <el-button link type="primary" @click="openBookingList(row)">预约名单</el-button>
          <el-button link type="primary" :disabled="row.status !== 'open'" @click="openBookDialog(row)">代约</el-button>
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

    <el-dialog
      v-model="bookingListDialog"
      :title="currentSession ? `预约名单 · ${courseName(currentSession.course_id)} #${currentSession.id}` : '预约名单'"
      width="720px"
      destroy-on-close
    >
      <div class="card-toolbar">
        <span class="card-hint">
          {{ currentSession ? `${coachName(currentSession.coach_id)} · ${fmtTime(currentSession.starts_at)} · 上限 ${currentSession.capacity}` : '' }}
        </span>
        <el-button
          type="primary"
          plain
          size="small"
          :disabled="currentSession?.status !== 'open'"
          @click="openBookDialog()"
        >
          代约
        </el-button>
      </div>
      <el-table :data="bookings" v-loading="bookingsLoading" stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column label="会员" min-width="180">
          <template #default="{ row }">{{ memberName(row.member_id, row) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.status === 'attended' ? 'success' : row.status === 'cancelled' ? 'info' : 'warning'"
            >
              {{ bookingStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100">
          <template #default="{ row }">
            <el-button v-if="row.status === 'booked'" link type="danger" @click="cancel(row.id)">取消</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-dialog>

    <el-dialog
      v-model="bookDialog"
      :title="currentSession ? `代约 · ${courseName(currentSession.course_id)}` : '代会员预约'"
      width="460px"
      destroy-on-close
    >
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

.filters {
  margin-bottom: 8px;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.card-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.card-hint {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
