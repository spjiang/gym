<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import { bookingStatusLabel, sessionStatusLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'

type Session = {
  id: number
  course_id: number
  starts_at: string
  room: string | null
  status: string
}
type Pkg = { id: number; member_id: number; remaining_sessions: number; status: string }
type Booking = { id: number; session_id: number; member_id: number; status: string }

const sessions = ref<Session[]>([])
const packages = ref<Pkg[]>([])
const bookings = ref<Booking[]>([])
const merchantId = ref<number | undefined>()

async function refresh() {
  const m = await http.get('/merchants')
  const gyms = merchantsWithSystem(m.data, 'gym')
  merchantId.value = gyms[0]?.id
  if (!merchantId.value) return
  const [s, p] = await Promise.all([
    http.get('/group-sessions', { params: { merchant_id: merchantId.value } }),
    http.get('/pt-packages', {
      params: { merchant_id: merchantId.value, status: 'active', page: 1, page_size: 100 },
    }),
  ])
  sessions.value = s.data
  packages.value = p.data.items
  if (sessions.value[0]) {
    const b = await http.get('/group-bookings', {
      params: {
        merchant_id: merchantId.value,
        session_id: sessions.value[0].id,
        status: 'booked',
        page: 1,
        page_size: 100,
      },
    })
    bookings.value = b.data.items
  }
}

async function consume(id: number) {
  await http.post(`/pt-packages/${id}/consume`)
  ElMessage.success('核销成功')
  await refresh()
}

async function checkin(id: number) {
  await http.post(`/group-bookings/${id}/checkin`, { status: 'attended' })
  ElMessage.success('已标记出席')
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div>
    <h3>我的场次（教练视角按权限过滤）</h3>
    <el-table :data="sessions" stripe>
      <el-table-column prop="id" label="场次" width="80" />
      <el-table-column prop="course_id" label="课程" width="90" />
      <el-table-column prop="starts_at" label="开始" />
      <el-table-column prop="room" label="教室" width="100" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">{{ sessionStatusLabel(row.status) }}</template>
      </el-table-column>
    </el-table>

    <h3 style="margin-top: 24px">待核销私教课包</h3>
    <el-table :data="packages" stripe>
      <el-table-column prop="id" label="课包" width="80" />
      <el-table-column prop="member_id" label="会员" width="90" />
      <el-table-column prop="remaining_sessions" label="剩余" width="90" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button link type="primary" @click="consume(row.id)">核销 1 次</el-button>
        </template>
      </el-table-column>
    </el-table>

    <h3 style="margin-top: 24px">最近场次待签到</h3>
    <el-table :data="bookings" stripe>
      <el-table-column prop="id" label="预约" width="80" />
      <el-table-column prop="member_id" label="会员" width="90" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">{{ bookingStatusLabel(row.status) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button link type="success" @click="checkin(row.id)">出席</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
