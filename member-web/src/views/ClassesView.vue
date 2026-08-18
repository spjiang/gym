<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'
import { bookingStatusLabel } from '../utils/labels'

type Session = {
  id: number
  course_id: number
  starts_at: string
  ends_at: string
  capacity: number
  status: string
  room: string | null
  course_name: string
  difficulty: string | null
  duration_minutes: number | null
  coach_id: number
  coach_name: string | null
  remaining: number
  cancel_ahead_minutes: number
}

type Booking = {
  id: number
  session_id: number
  status: string
  course_name: string | null
  coach_id: number | null
  coach_name: string | null
  room: string | null
  starts_at: string | null
  ends_at: string | null
}

const auth = useAuthStore()
const router = useRouter()
const sessions = ref<Session[]>([])
const bookings = ref<Booking[]>([])
const msg = ref('')
const err = ref('')
const busyId = ref<number | null>(null)

async function load() {
  err.value = ''
  const mid = auth.merchantId
  const [s, b] = await Promise.all([
    http.get<Session[]>('/member/group-sessions', { params: { merchant_id: mid } }),
    http.get<Booking[]>('/member/group-bookings', { params: { merchant_id: mid } }),
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

function fmt(iso: string | null | undefined) {
  if (!iso) return '—'
  return iso.slice(0, 16).replace('T', ' ')
}

function goDetail(sessionId: number) {
  router.push(`/m/${auth.merchantId}/gym/classes/${sessionId}`)
}

onMounted(load)
</script>

<template>
  <section class="mw-page">
    <h1 class="mw-page__title">团课预约</h1>
    <p class="mw-page__desc">预约前请确认场次时间与取消规则</p>
    <p v-if="msg" class="mw-msg mw-msg--ok">{{ msg }}</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <h2 class="mw-section-title first">我的预约</h2>
    <div v-for="b in bookings" :key="b.id" class="mw-card mw-list-row">
      <button class="mw-list-row__main as-btn" type="button" @click="goDetail(b.session_id)">
        <div class="mw-list-row__title">{{ b.course_name || `场次 #${b.session_id}` }}</div>
        <div class="mw-list-row__meta">
          {{ fmt(b.starts_at) }}
          <template v-if="b.coach_name"> · {{ b.coach_name }}</template>
          · {{ bookingStatusLabel(b.status) }}
        </div>
      </button>
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

    <h2 class="mw-section-title">可约场次</h2>
    <div v-for="s in sessions" :key="s.id" class="mw-card session">
      <button class="session__main as-btn" type="button" @click="goDetail(s.id)">
        <div class="mw-list-row__title">{{ s.course_name }}</div>
        <div class="mw-list-row__meta">
          {{ fmt(s.starts_at) }} ～ {{ fmt(s.ends_at).slice(11) }}
          <template v-if="s.coach_name"> · {{ s.coach_name }}</template>
        </div>
        <div class="mw-list-row__meta">
          剩余 {{ s.remaining }}/{{ s.capacity }}
          <template v-if="s.room"> · {{ s.room }}</template>
          <template v-if="s.difficulty"> · {{ s.difficulty }}</template>
        </div>
      </button>
      <div class="session__actions">
        <button class="mw-btn mw-btn--ghost mw-btn--sm" type="button" @click="goDetail(s.id)">详情</button>
        <button
          class="mw-btn mw-btn--sm"
          type="button"
          :disabled="busyId === s.id"
          @click="book(s.id)"
        >
          {{ busyId === s.id ? '处理中' : '预约' }}
        </button>
      </div>
    </div>
    <div v-if="!sessions.length" class="mw-empty">暂无可约场次</div>
  </section>
</template>

<style scoped>
.mw-section-title.first {
  margin-top: 0;
}

.as-btn {
  border: 0;
  background: transparent;
  padding: 0;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.session {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--mw-space-3);
}

.session__main {
  min-width: 0;
  flex: 1;
}

.session__actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}
</style>
