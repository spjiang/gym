<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Merchant = { id: number; name: string }
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
type Booking = { id: number; session_id: number; member_id: number; status: string }

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const coaches = ref<Coach[]>([])
const courses = ref<Course[]>([])
const sessions = ref<Session[]>([])
const bookings = ref<Booking[]>([])
const merchantId = ref<number | undefined>()
const selectedSessionId = ref<number | undefined>()

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

async function refresh() {
  const [m, mem] = await Promise.all([http.get('/merchants'), http.get('/members')])
  merchants.value = m.data
  members.value = mem.data
  if (!merchantId.value && m.data[0]) merchantId.value = m.data[0].id
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
}

async function loadBookings() {
  if (!selectedSessionId.value) return
  const { data } = await http.get('/group-bookings', {
    params: { merchant_id: merchantId.value, session_id: selectedSessionId.value },
  })
  bookings.value = data
}

async function createCourse() {
  await http.post('/group-courses', { merchant_id: merchantId.value, ...courseForm })
  ElMessage.success('课程已创建')
  await refresh()
}

async function createSession() {
  await http.post('/group-sessions', {
    merchant_id: merchantId.value,
    ...sessionForm,
    starts_at: new Date(sessionForm.starts_at).toISOString(),
    ends_at: new Date(sessionForm.ends_at).toISOString(),
  })
  ElMessage.success('场次已排')
  await refresh()
}

async function book() {
  await http.post('/group-bookings', {
    merchant_id: merchantId.value,
    session_id: selectedSessionId.value,
    member_id: bookForm.member_id,
  })
  ElMessage.success('代约成功')
  await loadBookings()
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
    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-card header="新建团课模板" style="margin-bottom: 16px">
      <el-form inline>
        <el-form-item label="名称"><el-input v-model="courseForm.name" /></el-form-item>
        <el-form-item label="默认上限">
          <el-input-number v-model="courseForm.default_capacity" :min="1" />
        </el-form-item>
        <el-button type="primary" @click="createCourse">创建</el-button>
      </el-form>
    </el-card>

    <el-card header="排场次" style="margin-bottom: 16px">
      <el-form inline>
        <el-form-item label="课程">
          <el-select v-model="sessionForm.course_id" style="width: 160px">
            <el-option v-for="c in courses" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="教练">
          <el-select v-model="sessionForm.coach_id" style="width: 140px">
            <el-option v-for="c in coaches" :key="c.id" :label="c.display_name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="开始">
          <el-input v-model="sessionForm.starts_at" placeholder="YYYY-MM-DDTHH:mm" />
        </el-form-item>
        <el-form-item label="结束">
          <el-input v-model="sessionForm.ends_at" placeholder="YYYY-MM-DDTHH:mm" />
        </el-form-item>
        <el-form-item label="教室"><el-input v-model="sessionForm.room" /></el-form-item>
        <el-form-item label="上限">
          <el-input-number v-model="sessionForm.capacity" :min="1" />
        </el-form-item>
        <el-button type="primary" @click="createSession">排课</el-button>
      </el-form>
    </el-card>

    <h3>场次</h3>
    <el-table
      :data="sessions"
      stripe
      highlight-current-row
      @current-change="(row: Session | undefined) => { selectedSessionId = row?.id; loadBookings() }"
    >
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="course_id" label="课程" width="90" />
      <el-table-column prop="coach_id" label="教练" width="90" />
      <el-table-column prop="starts_at" label="开始" />
      <el-table-column prop="capacity" label="上限" width="80" />
      <el-table-column prop="room" label="教室" width="100" />
      <el-table-column prop="status" label="状态" width="90" />
    </el-table>

    <el-card v-if="selectedSessionId" header="预约名单" style="margin-top: 16px">
      <el-form inline>
        <el-form-item label="会员">
          <el-select v-model="bookForm.member_id" filterable style="width: 220px">
            <el-option v-for="x in members" :key="x.id" :label="`${x.name} ${x.phone}`" :value="x.id" />
          </el-select>
        </el-form-item>
        <el-button type="primary" @click="book">代约</el-button>
      </el-form>
      <el-table :data="bookings" stripe style="margin-top: 12px">
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="member_id" label="会员" width="90" />
        <el-table-column prop="status" label="状态" width="110" />
        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button v-if="row.status === 'booked'" link type="danger" @click="cancel(row.id)">取消</el-button>
            <el-button v-if="row.status === 'booked'" link type="success" @click="checkin(row.id, 'attended')">出席</el-button>
            <el-button v-if="row.status === 'booked'" link @click="checkin(row.id, 'no_show')">未出席</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>
