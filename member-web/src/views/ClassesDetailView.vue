<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'

type Session = {
  id: number
  merchant_id: number
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
  booked_count: number
  book_ahead_minutes: number
  cancel_ahead_minutes: number
  already_booked: boolean
}

const route = useRoute()
const router = useRouter()
const mid = computed(() => Number(route.params.merchantId))
const sessionId = computed(() => Number(route.params.sessionId))
const item = ref<Session | null>(null)
const err = ref('')
const msg = ref('')
const loading = ref(true)
const busy = ref(false)

function fmt(iso?: string | null) {
  if (!iso) return '—'
  return iso.slice(0, 16).replace('T', ' ')
}

function ruleText(minutes: number, kind: '预约' | '取消') {
  if (minutes <= 0) return `开课前均可${kind}`
  if (minutes % 60 === 0) return `需提前 ${minutes / 60} 小时${kind}`
  return `需提前 ${minutes} 分钟${kind}`
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await http.get<Session>(`/member/group-sessions/${sessionId.value}`)
    if (data.merchant_id !== mid.value) {
      err.value = '该场次不属于当前门店'
      item.value = null
      return
    }
    item.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
    item.value = null
  } finally {
    loading.value = false
  }
}

async function book() {
  if (!item.value) return
  busy.value = true
  err.value = ''
  msg.value = ''
  try {
    await http.post('/member/group-bookings', {
      merchant_id: mid.value,
      session_id: item.value.id,
    })
    msg.value = '预约成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '预约失败'
  } finally {
    busy.value = false
  }
}

function goCoach() {
  if (!item.value?.coach_id) return
  router.push(`/m/${mid.value}/gym/coaches/${item.value.coach_id}?from=${item.value.id}`)
}

onMounted(load)
</script>

<template>
  <section class="mw-page">
    <button class="back" type="button" @click="router.push(`/m/${mid}/gym/classes`)">← 团课预约</button>

    <p v-if="loading" class="mw-page__desc">加载中…</p>
    <p v-else-if="err && !item" class="mw-msg mw-msg--error">{{ err }}</p>

    <template v-else-if="item">
      <h1 class="mw-page__title">{{ item.course_name }}</h1>
      <p class="mw-page__desc">团课详情</p>
      <p v-if="msg" class="mw-msg mw-msg--ok">{{ msg }}</p>
      <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

      <div class="mw-card">
        <div class="row"><span>上课时间</span><strong>{{ fmt(item.starts_at) }} ～ {{ fmt(item.ends_at).slice(11) }}</strong></div>
        <div class="row">
          <span>教练</span>
          <button
            v-if="item.coach_id"
            class="coach-link"
            type="button"
            @click="goCoach"
          >
            {{ item.coach_name || '教练详情' }} →
          </button>
          <strong v-else>—</strong>
        </div>
        <div class="row"><span>教室</span><strong>{{ item.room || '未指定' }}</strong></div>
        <div class="row"><span>时长</span><strong>{{ item.duration_minutes ? `${item.duration_minutes} 分钟` : '—' }}</strong></div>
        <div class="row"><span>难度</span><strong>{{ item.difficulty || '—' }}</strong></div>
        <div class="row"><span>名额</span><strong>剩余 {{ item.remaining }} / {{ item.capacity }}</strong></div>
        <div class="row"><span>预约规则</span><strong>{{ ruleText(item.book_ahead_minutes, '预约') }}</strong></div>
        <div class="row"><span>取消规则</span><strong>{{ ruleText(item.cancel_ahead_minutes, '取消') }}</strong></div>
      </div>

      <button
        v-if="item.already_booked"
        class="mw-btn mw-btn--block"
        type="button"
        disabled
      >
        已预约
      </button>
      <button
        v-else-if="item.remaining > 0 && item.status === 'open'"
        class="mw-btn mw-btn--block"
        type="button"
        :disabled="busy"
        @click="book"
      >
        {{ busy ? '处理中' : '立即预约' }}
      </button>
      <p v-else class="mw-empty">该场次暂不可预约</p>
    </template>
  </section>
</template>

<style scoped>
.back {
  border: 0;
  background: transparent;
  color: var(--mw-brand);
  padding: 0;
  margin-bottom: var(--mw-space-4);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--mw-border);
  font-size: 14px;
}

.row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.row span {
  color: var(--mw-text-secondary);
  flex-shrink: 0;
}

.row strong {
  font-weight: 600;
  text-align: right;
}

.coach-link {
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--mw-brand);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}
</style>
