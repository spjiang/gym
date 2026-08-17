<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import { bookingStatusLabel, sessionStatusLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Course = { id: number; name: string }
type Coach = { id: number; display_name: string }
type Session = {
  id: number
  course_id: number
  coach_id: number
  starts_at: string
  ends_at: string
  room: string | null
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
const courses = ref<Course[]>([])
const coaches = ref<Coach[]>([])
const sessions = ref<Session[]>([])
const bookings = ref<Booking[]>([])
const { merchantId } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const currentSession = ref<Session | null>(null)
const dialogVisible = ref(false)
const checkinAlertVisible = ref(false)
const loading = ref(false)
const bookingsLoading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const bookingTotal = ref(0)
const bookingPage = ref(1)
const bookingPageSize = ref(20)
const query = reactive({
  q: '',
  course_id: undefined as number | undefined,
  coach_id: undefined as number | undefined,
  on_date: '' as string,
})

function courseName(id: number) {
  return courses.value.find((c) => c.id === id)?.name || `#${id}`
}

function coachName(id: number) {
  return coaches.value.find((c) => c.id === id)?.display_name || `#${id}`
}

function memberName(id: number, row?: Booking) {
  if (row?.member) return `${row.member.name} ${row.member.phone}`
  return `#${id}`
}

function fmtDateTime(d: Date) {
  if (Number.isNaN(d.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fmtTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return fmtDateTime(d)
}

function signWindow(session: Session | null | undefined) {
  if (!session?.starts_at) return '—'
  const start = new Date(session.starts_at)
  const end = session.ends_at ? new Date(session.ends_at) : start
  const openAt = new Date(start.getTime() - 60 * 60 * 1000)
  return `${fmtDateTime(openAt)} ～ ${fmtDateTime(end)}`
}

const attendWindow = computed(() => {
  const session = currentSession.value
  if (!session?.starts_at) {
    return { open: false, title: '', classTime: '—', signTime: '—' }
  }
  const start = new Date(session.starts_at)
  const end = session.ends_at ? new Date(session.ends_at) : start
  const openAt = new Date(start.getTime() - 60 * 60 * 1000)
  const classTime = fmtDateTime(start)
  const signTime = `${fmtDateTime(openAt)} ～ ${fmtDateTime(end)}`
  const now = Date.now()
  if (now < openAt.getTime()) {
    return { open: false, title: '未到签到时间', classTime, signTime }
  }
  if (now > end.getTime()) {
    return { open: false, title: '课程已结束', classTime, signTime }
  }
  return { open: true, title: '签到已开放', classTime, signTime }
})

async function refresh() {
  loading.value = true
  try {
    const { data } = await http.get('/merchants')
    merchants.value = merchantsWithSystem(data, 'gym')
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
    if (currentSession.value && !sessions.value.some((x) => x.id === currentSession.value?.id)) {
      currentSession.value = null
      dialogVisible.value = false
      bookings.value = []
      bookingTotal.value = 0
    }
    if (dialogVisible.value && currentSession.value) await loadBookings()
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
  query.on_date = ''
  page.value = 1
  void refresh()
}

async function loadBookings() {
  if (!currentSession.value) {
    bookings.value = []
    bookingTotal.value = 0
    return
  }
  bookingsLoading.value = true
  try {
    const { data } = await http.get<Page<Booking>>('/group-bookings', {
      params: {
        merchant_id: merchantId.value,
        session_id: currentSession.value.id,
        page: bookingPage.value,
        page_size: bookingPageSize.value,
      },
    })
    bookings.value = data.items
    bookingTotal.value = data.total
  } finally {
    bookingsLoading.value = false
  }
}

function openRoster(row: Session) {
  currentSession.value = row
  bookingPage.value = 1
  dialogVisible.value = true
  void loadBookings()
}

async function checkin(id: number, status: string) {
  if (status === 'attended' && !attendWindow.value.open) {
    checkinAlertVisible.value = true
    return
  }
  try {
    await http.post(`/group-bookings/${id}/checkin`, { status })
    ElMessage.success(status === 'attended' ? '已签到' : '已标记未出席')
    await loadBookings()
  } catch (e: unknown) {
    if (status === 'attended') {
      checkinAlertVisible.value = true
    }
    ElMessage.error(e instanceof Error ? e.message : '签到失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>团课签到</h3>
        <p class="lead">点「查看名单」打开已预约会员，再点「签到」。代约请到「团课管理 → 团课代约」。</p>
      </div>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
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
      <el-form-item label="日期">
        <el-date-picker v-model="query.on_date" type="date" value-format="YYYY-MM-DD" placeholder="全部日期" style="width: 160px" />
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="课程 / 场次 / 教室" style="width: 180px" @keyup.enter="search" />
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
      <el-table-column label="开课时间" min-width="170">
        <template #default="{ row }">{{ fmtTime(row.starts_at) }}</template>
      </el-table-column>
      <el-table-column label="签到时间" min-width="280">
        <template #default="{ row }">{{ signWindow(row) }}</template>
      </el-table-column>
      <el-table-column prop="room" label="教室" min-width="120" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">{{ sessionStatusLabel(row.status) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button link type="primary" @click="openRoster(row)">查看名单</el-button>
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
      v-model="dialogVisible"
      :title="currentSession ? `已预约会员 · ${courseName(currentSession.course_id)} #${currentSession.id}` : '已预约会员'"
      width="760px"
      destroy-on-close
    >
      <p class="card-hint">
        {{
          currentSession
            ? `${coachName(currentSession.coach_id)} · ${currentSession.room || '未指定教室'} · 共 ${bookingTotal} 人`
            : ''
        }}
      </p>
      <el-alert
        :type="attendWindow.open ? 'success' : 'warning'"
        :title="attendWindow.title"
        show-icon
        :closable="false"
        class="checkin-window-alert"
      >
        <p>开课时间：{{ attendWindow.classTime }}</p>
        <p>签到时间：{{ attendWindow.signTime }}</p>
      </el-alert>
      <el-table
        :data="bookings"
        v-loading="bookingsLoading"
        stripe
        style="width: 100%; margin-top: 12px"
        empty-text="本场暂无预约会员"
      >
        <el-table-column prop="id" label="预约" width="80" />
        <el-table-column label="会员" min-width="220">
          <template #default="{ row }">{{ memberName(row.member_id, row) }}</template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">{{ bookingStatusLabel(row.status) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="180">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'booked' || row.status === 'no_show'"
              type="primary"
              link
              @click.stop="checkin(row.id, 'attended')"
            >
              {{ row.status === 'no_show' ? '改为已出席' : '签到' }}
            </el-button>
            <el-button
              v-if="row.status === 'booked' || row.status === 'attended'"
              link
              @click="checkin(row.id, 'no_show')"
            >
              {{ row.status === 'attended' ? '改为未出席' : '未出席' }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="bookingPage"
          v-model:page-size="bookingPageSize"
          :total="bookingTotal"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next"
          background
          @current-change="loadBookings"
          @size-change="
            () => {
              bookingPage = 1
              loadBookings()
            }
          "
        />
      </div>
    </el-dialog>

    <el-dialog
      v-model="checkinAlertVisible"
      title="无法签到"
      width="460px"
      append-to-body
      align-center
      class="checkin-time-alert"
      modal-class="checkin-time-alert-overlay"
    >
      <p class="checkin-alert-lead">{{ attendWindow.title }}，暂不能标记出席。</p>
      <p>开课时间：{{ attendWindow.classTime }}</p>
      <p>签到时间：{{ attendWindow.signTime }}</p>
      <p class="card-hint">仅开课当天、开课前 1 小时起到下课前可签到。</p>
      <template #footer>
        <el-button type="primary" @click="checkinAlertVisible = false">知道了</el-button>
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

.card-hint {
  margin: 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.card-hint + .card-hint {
  margin-top: 6px;
}

.checkin-window-alert {
  margin-top: 10px;
}

.checkin-window-alert p,
.checkin-alert-lead + p {
  margin: 4px 0 0;
  line-height: 1.6;
}

.checkin-alert-lead {
  margin: 0 0 10px;
  font-weight: 600;
}
</style>
