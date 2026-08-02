<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

type Session = {
  id: number
  course_id: number
  starts_at: string
  ends_at: string
  capacity: number
  status: string
}
type Booking = { id: number; session_id: number; status: string }

const auth = useAuthStore()
const sessions = ref<Session[]>([])
const bookings = ref<Booking[]>([])
const msg = ref('')
const err = ref('')

async function load() {
  err.value = ''
  const mid = auth.merchantId
  const [s, b] = await Promise.all([
    http.get('/member/group-sessions', { params: { merchant_id: mid } }),
    http.get('/member/group-bookings', { params: { merchant_id: mid } }),
  ])
  sessions.value = s.data
  bookings.value = b.data
}

async function book(sessionId: number) {
  msg.value = ''
  err.value = ''
  try {
    await http.post('/member/group-bookings', {
      merchant_id: auth.merchantId,
      session_id: sessionId,
    })
    msg.value = '预约成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '预约失败'
  }
}

async function cancel(id: number) {
  msg.value = ''
  err.value = ''
  try {
    await http.delete(`/member/group-bookings/${id}`)
    msg.value = '已取消'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '取消失败'
  }
}

onMounted(load)
</script>

<template>
  <section>
    <h2>团课</h2>
    <p v-if="msg" class="muted">{{ msg }}</p>
    <p v-if="err" class="err">{{ err }}</p>
    <h3>可约场次</h3>
    <div v-for="s in sessions" :key="s.id" class="card row">
      <div>
        <div>场次 #{{ s.id }} · 课程 {{ s.course_id }}</div>
        <div class="muted">{{ s.starts_at.slice(0, 16).replace('T', ' ') }}</div>
      </div>
      <button @click="book(s.id)">预约</button>
    </div>
    <h3>我的预约</h3>
    <div v-for="b in bookings" :key="b.id" class="card row">
      <div>#{{ b.id }} · 场次 {{ b.session_id }} · {{ b.status }}</div>
      <button v-if="b.status === 'booked'" class="ghost" @click="cancel(b.id)">取消</button>
    </div>
  </section>
</template>

<style scoped>
.row {
  display: flex;
  justify-content: space-between;
  gap: 0.75rem;
  align-items: center;
}
</style>
