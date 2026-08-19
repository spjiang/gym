<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AgreementSheet from '../components/AgreementSheet.vue'
import http from '../api/http'
import { payMemberOrder } from '../api/pay'
import { useAuthStore } from '../stores/auth'
import { activityRegStatusLabel } from '../utils/labels'

type Activity = {
  id: number
  name: string
  category: string | null
  location: string | null
  cover_url: string | null
  starts_at: string
  ends_at: string
  register_ends_at: string | null
  capacity: number
  price: string
  remaining_capacity: number | null
  already_registered: boolean
  my_registration_id: number | null
  my_registration_status: string | null
  my_order_id: number | null
  can_register: boolean
}

type Registration = {
  id: number
  activity_id: number
  status: string
  amount: string
  order_id: number | null
  activity_name: string | null
  activity_starts_at: string | null
  location: string | null
}

const auth = useAuthStore()
const router = useRouter()
const activities = ref<Activity[]>([])
const mine = ref<Registration[]>([])
const msg = ref('')
const err = ref('')
const busyId = ref<number | null>(null)
const agreeOpen = ref(false)
const agreeSummary = ref('')
const agreeConfirmLabel = ref('立即报名')
const pendingJoin = ref<(() => Promise<void>) | null>(null)

function fmt(iso?: string | null) {
  if (!iso) return '—'
  return iso.slice(0, 16).replace('T', ' ')
}

function money(raw?: string | null) {
  if (raw == null || raw === '') return '免费'
  const n = Number(raw)
  if (Number.isNaN(n) || n <= 0) return '免费'
  return `¥ ${Number.isInteger(n) ? String(n) : n.toFixed(2)}`
}

function seats(a: Activity) {
  if (a.capacity <= 0 || a.remaining_capacity == null) return '不限名额'
  return `剩余 ${a.remaining_capacity}/${a.capacity}`
}

function goDetail(id: number) {
  router.push(`/m/${auth.merchantId}/gym/activities/${id}`)
}

async function load() {
  err.value = ''
  const mid = auth.merchantId
  const [a, r] = await Promise.all([
    http.get<Activity[]>('/member/activities', { params: { merchant_id: mid } }),
    http.get<Registration[]>('/member/activity-registrations', { params: { merchant_id: mid } }),
  ])
  activities.value = a.data
  mine.value = r.data
}

async function join(a: Activity) {
  agreeSummary.value = `${a.name}  ${money(a.price)}`
  agreeConfirmLabel.value = Number(a.price) > 0 ? '报名并支付' : '立即报名'
  pendingJoin.value = () => doJoin(a.id)
  agreeOpen.value = true
}

async function doJoin(activityId: number) {
  msg.value = ''
  err.value = ''
  busyId.value = activityId
  try {
    const { data } = await http.post<{
      registration: Registration
      order: { id: number; amount?: string } | null
    }>('/member/activity-registrations', {
      merchant_id: auth.merchantId,
      activity_id: activityId,
    })
    if (data.order) {
      await payMemberOrder(data.order.id)
    }
    msg.value = '报名成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '报名失败'
  } finally {
    busyId.value = null
  }
}

async function onAgreeConfirm() {
  const next = pendingJoin.value
  pendingJoin.value = null
  if (next) await next()
}

async function payPending(orderId: number) {
  msg.value = ''
  err.value = ''
  busyId.value = orderId
  try {
    await payMemberOrder(orderId)
    msg.value = '报名成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '支付失败'
  } finally {
    busyId.value = null
  }
}

async function cancel(id: number) {
  msg.value = ''
  err.value = ''
  busyId.value = id
  try {
    await http.post(`/member/activity-registrations/${id}/cancel`)
    msg.value = '已取消报名'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '取消失败'
  } finally {
    busyId.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="mw-page">
    <h1 class="mw-page__title">活动报名</h1>
    <p class="mw-page__desc">赛事、体测与体验课，报名后按活动时间到店</p>
    <p v-if="msg" class="mw-msg mw-msg--ok">{{ msg }}</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <h2 class="mw-section-title first">我的报名</h2>
    <div v-for="r in mine" :key="r.id" class="mw-card mw-list-row">
      <button class="mw-list-row__main as-btn" type="button" @click="goDetail(r.activity_id)">
        <div class="mw-list-row__title">{{ r.activity_name || `活动 #${r.activity_id}` }}</div>
        <div class="mw-list-row__meta">
          {{ fmt(r.activity_starts_at) }}
          <template v-if="r.location"> · {{ r.location }}</template>
          · {{ activityRegStatusLabel(r.status) }}
        </div>
      </button>
      <div class="row-actions">
        <button
          v-if="r.status === 'pending' && r.order_id"
          class="mw-btn mw-btn--sm"
          type="button"
          :disabled="busyId === r.order_id"
          @click="payPending(r.order_id)"
        >
          去支付
        </button>
        <button
          v-if="r.status === 'pending' || r.status === 'confirmed'"
          class="mw-btn mw-btn--ghost mw-btn--sm"
          type="button"
          :disabled="busyId === r.id"
          @click="cancel(r.id)"
        >
          取消
        </button>
      </div>
    </div>
    <div v-if="!mine.length" class="mw-empty">暂无报名</div>

    <h2 class="mw-section-title">可报活动</h2>
    <div v-for="a in activities" :key="a.id" class="mw-card session">
      <button class="session__main as-btn" type="button" @click="goDetail(a.id)">
        <img v-if="a.cover_url" class="cover" :src="a.cover_url" alt="" />
        <div>
          <div class="mw-list-row__title">{{ a.name }}</div>
          <div class="mw-list-row__meta">
            {{ fmt(a.starts_at) }} ～ {{ fmt(a.ends_at).slice(11) }}
            <template v-if="a.category"> · {{ a.category }}</template>
          </div>
          <div class="mw-list-row__meta">
            {{ seats(a) }}
            <template v-if="a.location"> · {{ a.location }}</template>
            · {{ money(a.price) }}
          </div>
        </div>
      </button>
      <div class="session__actions">
        <button class="mw-btn mw-btn--ghost mw-btn--sm" type="button" @click="goDetail(a.id)">详情</button>
        <button
          v-if="a.my_registration_status === 'pending' && a.my_order_id"
          class="mw-btn mw-btn--sm"
          type="button"
          :disabled="busyId === a.my_order_id"
          @click="payPending(a.my_order_id)"
        >
          去支付
        </button>
        <button
          v-else-if="a.can_register"
          class="mw-btn mw-btn--sm"
          type="button"
          :disabled="busyId === a.id"
          @click="join(a)"
        >
          {{ busyId === a.id ? '处理中' : '报名' }}
        </button>
        <button v-else-if="a.already_registered" class="mw-btn mw-btn--sm" type="button" disabled>
          已报名
        </button>
      </div>
    </div>
    <div v-if="!activities.length" class="mw-empty">暂无可报活动</div>
    <AgreementSheet
      v-model:open="agreeOpen"
      :merchant-id="auth.merchantId"
      scene="activity"
      :summary="agreeSummary"
      :confirm-label="agreeConfirmLabel"
      @confirm="onAgreeConfirm"
    />
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
  display: flex;
  gap: 12px;
  align-items: flex-start;
}

.cover {
  width: 72px;
  height: 72px;
  object-fit: cover;
  border-radius: 8px;
  flex-shrink: 0;
}

.session__actions,
.row-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex-shrink: 0;
}
</style>
