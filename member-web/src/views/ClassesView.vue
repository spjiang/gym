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
const busyId = ref<number | null>(null)

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
  busyId.value = sessionId
  try {
    await http.post('/member/group-bookings', {
      merchant_id: auth.merchantId,
      session_id: sessionId,
    })
    msg.value = '预约成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '预约失败'
  } finally {
    busyId.value = null
  }
}

async function cancel(id: number) {
  msg.value = ''
  err.value = ''
  busyId.value = id
  try {
    await http.delete(`/member/group-bookings/${id}`)
    msg.value = '已取消'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '取消失败'
  } finally {
    busyId.value = null
  }
}

function fmt(iso: string) {
  return iso.slice(0, 16).replace('T', ' ')
}

onMounted(load)
</script>

<template>
  <section class="mw-page">
    <h1 class="mw-page__title">团课预约</h1>
    <p class="mw-page__desc">预约前请确认场次时间与取消规则</p>
    <p v-if="msg" class="mw-msg mw-msg--ok">{{ msg }}</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <h2 class="mw-section-title">可约场次</h2>
    <div v-for="s in sessions" :key="s.id" class="mw-card mw-list-row">
      <div class="mw-list-row__main">
        <div class="mw-list-row__title">场次 #{{ s.id }} · 课程 {{ s.course_id }}</div>
        <div class="mw-list-row__meta">{{ fmt(s.starts_at) }} · 容量 {{ s.capacity }}</div>
      </div>
      <button
        class="mw-btn mw-btn--sm mw-list-row__action"
        type="button"
        :disabled="busyId === s.id"
        @click="book(s.id)"
      >
        {{ busyId === s.id ? '处理中' : '预约' }}
      </button>
    </div>
    <div v-if="!sessions.length" class="mw-empty">暂无可约场次</div>

    <h2 class="mw-section-title">我的预约</h2>
    <div v-for="b in bookings" :key="b.id" class="mw-card mw-list-row">
      <div class="mw-list-row__main">
        <div class="mw-list-row__title">预约 #{{ b.id }}</div>
        <div class="mw-list-row__meta">场次 {{ b.session_id }} · {{ b.status }}</div>
      </div>
      <button
        v-if="b.status === 'booked'"
        class="mw-btn mw-btn--ghost mw-btn--sm mw-list-row__action"
        type="button"
        :disabled="busyId === b.id"
        @click="cancel(b.id)"
      >
        取消
      </button>
    </div>
    <div v-if="!bookings.length" class="mw-empty">暂无预约</div>
  </section>
</template>
