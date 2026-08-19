<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AgreementSheet from '../components/AgreementSheet.vue'
import http from '../api/http'
import { payMemberOrder } from '../api/pay'
import { activityRegStatusLabel } from '../utils/labels'

type Activity = {
  id: number
  merchant_id: number
  name: string
  category: string | null
  location: string | null
  cover_url: string | null
  description: string | null
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

const route = useRoute()
const router = useRouter()
const mid = computed(() => Number(route.params.merchantId))
const activityId = computed(() => Number(route.params.activityId))
const item = ref<Activity | null>(null)
const err = ref('')
const msg = ref('')
const loading = ref(true)
const busy = ref(false)
const agreeOpen = ref(false)

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
  return `剩余 ${a.remaining_capacity} / ${a.capacity}`
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await http.get<Activity>(`/member/activities/${activityId.value}`)
    if (data.merchant_id !== mid.value) {
      err.value = '该活动不属于当前门店'
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

function openJoin() {
  agreeOpen.value = true
}

async function join() {
  if (!item.value) return
  busy.value = true
  err.value = ''
  msg.value = ''
  try {
    const { data } = await http.post<{
      order: { id: number } | null
    }>('/member/activity-registrations', {
      merchant_id: mid.value,
      activity_id: item.value.id,
    })
    if (data.order) {
      await payMemberOrder(data.order.id)
    }
    msg.value = '报名成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '报名失败'
  } finally {
    busy.value = false
  }
}

async function payPending() {
  if (!item.value?.my_order_id) return
  busy.value = true
  err.value = ''
  msg.value = ''
  try {
    await payMemberOrder(item.value.my_order_id)
    msg.value = '报名成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '支付失败'
  } finally {
    busy.value = false
  }
}

async function cancel() {
  if (!item.value?.my_registration_id) return
  busy.value = true
  err.value = ''
  msg.value = ''
  try {
    await http.post(`/member/activity-registrations/${item.value.my_registration_id}/cancel`)
    msg.value = '已取消报名'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '取消失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="mw-page">
    <button class="back" type="button" @click="router.push(`/m/${mid}/gym/activities`)">← 活动报名</button>

    <p v-if="loading" class="mw-page__desc">加载中…</p>
    <p v-else-if="err && !item" class="mw-msg mw-msg--error">{{ err }}</p>

    <template v-else-if="item">
      <h1 class="mw-page__title">{{ item.name }}</h1>
      <p class="mw-page__desc">{{ item.category || '活动详情' }}</p>
      <p v-if="msg" class="mw-msg mw-msg--ok">{{ msg }}</p>
      <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

      <img v-if="item.cover_url" class="cover" :src="item.cover_url" alt="" />

      <div class="mw-card">
        <div class="row"><span>活动时间</span><strong>{{ fmt(item.starts_at) }} ～ {{ fmt(item.ends_at) }}</strong></div>
        <div class="row"><span>报名截止</span><strong>{{ fmt(item.register_ends_at) }}</strong></div>
        <div class="row"><span>地点</span><strong>{{ item.location || '—' }}</strong></div>
        <div class="row"><span>名额</span><strong>{{ seats(item) }}</strong></div>
        <div class="row"><span>费用</span><strong>{{ money(item.price) }}</strong></div>
        <div v-if="item.my_registration_status" class="row">
          <span>我的报名</span>
          <strong>{{ activityRegStatusLabel(item.my_registration_status) }}</strong>
        </div>
      </div>

      <p v-if="item.description" class="desc">{{ item.description }}</p>

      <button
        v-if="item.my_registration_status === 'pending' && item.my_order_id"
        class="mw-btn mw-btn--block"
        type="button"
        :disabled="busy"
        @click="payPending"
      >
        {{ busy ? '处理中' : '去支付' }}
      </button>
      <button
        v-else-if="item.can_register"
        class="mw-btn mw-btn--block"
        type="button"
        :disabled="busy"
        @click="openJoin"
      >
        {{ busy ? '处理中' : Number(item.price) > 0 ? '报名并支付' : '立即报名' }}
      </button>
      <button
        v-else-if="item.already_registered"
        class="mw-btn mw-btn--block"
        type="button"
        disabled
      >
        已报名
      </button>
      <p v-else class="mw-empty">该活动暂不可报名</p>

      <button
        v-if="item.my_registration_status === 'pending' || item.my_registration_status === 'confirmed'"
        class="mw-btn mw-btn--ghost mw-btn--block cancel"
        type="button"
        :disabled="busy"
        @click="cancel"
      >
        取消报名
      </button>
    </template>
    <AgreementSheet
      v-if="item"
      v-model:open="agreeOpen"
      :merchant-id="mid"
      scene="activity"
      :summary="`${item.name}  ${money(item.price)}`"
      :confirm-label="Number(item.price) > 0 ? '报名并支付' : '立即报名'"
      @confirm="join"
    />
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

.cover {
  width: 100%;
  height: 160px;
  object-fit: cover;
  border-radius: var(--mw-radius-md);
  margin-bottom: var(--mw-space-3);
  border: 1px solid var(--mw-border);
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

.desc {
  margin: var(--mw-space-4) 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--mw-text-secondary);
  white-space: pre-wrap;
}

.cancel {
  margin-top: 10px;
}
</style>
