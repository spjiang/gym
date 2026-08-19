<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import { payMemberOrder } from '../../api/pay'
import { useCateringCart } from '../../stores/cateringCart'
import { diningOrderLabel } from '../../utils/labels'

type OrderDetail = {
  id: number
  status: string
  dining_status?: string | null
  amount: string | number
  original_amount?: string | number | null
  promotion_discount_amount?: string | number | null
  pickup_code?: string | null
  customer_note?: string | null
  created_at?: string
  items?: {
    menu_item_id: number
    name: string
    quantity: number
    unit_price: string | number
    line_amount: string | number
  }[]
}

type Step = { key: string; label: string; done: boolean; current: boolean }

const HINTS: Record<string, string> = {
  preparing: '后厨制作中，请留意取餐号。',
  ready: '已出餐，请到吧台取餐。',
  completed: '订单已完成。',
}

const route = useRoute()
const router = useRouter()
const cart = useCateringCart()
const merchantId = computed(() => Number(route.params.merchantId))
const orderId = computed(() => Number(route.params.orderId))
const order = ref<OrderDetail | null>(null)
const err = ref('')
const busy = ref(false)
const reused = ref(false)
let timer: number | null = null

const kitchen = computed(() => {
  if (!order.value || order.value.status !== 'paid') return ''
  return order.value.dining_status || 'preparing'
})
const original = computed(() => Number(order.value?.original_amount || 0))
const promoOff = computed(() => Number(order.value?.promotion_discount_amount || 0))
const paid = computed(() => Number(order.value?.amount || 0))
const couponOff = computed(() => {
  if (!original.value) return 0
  const n = original.value - promoOff.value - paid.value
  return n > 0.004 ? n : 0
})
const showPickup = computed(() => order.value?.status === 'paid' && !!order.value.pickup_code)

const steps = computed<Step[]>(() => {
  const o = order.value
  if (!o) return []
  const kitchenNow = o.status === 'paid' ? o.dining_status || 'preparing' : ''
  const paidDone = o.status === 'paid' || o.status === 'refunded'
  const preparingDone = paidDone && ['preparing', 'ready', 'completed'].includes(kitchenNow)
  const readyDone = paidDone && ['ready', 'completed'].includes(kitchenNow)
  const completedDone = paidDone && kitchenNow === 'completed'
  return [
    { key: 'created', label: '已下单', done: true, current: false },
    {
      key: 'pay',
      label:
        o.status === 'cancelled' ? '已取消' : o.status === 'refunded' ? '已退款' : o.status === 'pending' ? '待支付' : '已支付',
      done: paidDone,
      current: o.status === 'pending' || o.status === 'cancelled' || o.status === 'refunded',
    },
    { key: 'prep', label: '制作中', done: preparingDone, current: kitchenNow === 'preparing' },
    { key: 'ready', label: '待取餐', done: readyDone, current: kitchenNow === 'ready' },
    { key: 'done', label: '已完成', done: completedDone, current: kitchenNow === 'completed' },
  ]
})

async function load() {
  try {
    const { data } = await http.get<OrderDetail>(`/member/catering/orders/${orderId.value}`)
    order.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
  }
}

function startPoll() {
  stopPoll()
  timer = window.setInterval(() => {
    const o = order.value
    if (o?.status === 'pending' || (o?.status === 'paid' && (o.dining_status === 'preparing' || o.dining_status === 'ready' || !o.dining_status))) {
      void load()
    }
  }, 8000)
}

function stopPoll() {
  if (timer != null) {
    window.clearInterval(timer)
    timer = null
  }
}

onMounted(() => {
  void load()
  startPoll()
})
onUnmounted(stopPoll)

async function pay() {
  if (!order.value) return
  busy.value = true
  err.value = ''
  try {
    await payMemberOrder(order.value.id)
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '支付失败'
  } finally {
    busy.value = false
  }
}

async function cancel() {
  if (!order.value) return
  if (!window.confirm('取消后订单关闭，已选优惠券将退回。确定取消？')) return
  busy.value = true
  err.value = ''
  try {
    const { data } = await http.post<OrderDetail>(`/member/catering/orders/${order.value.id}/cancel`)
    order.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '取消失败'
  } finally {
    busy.value = false
  }
}

function reorder() {
  if (!order.value?.items?.length) return
  cart.fill(
    merchantId.value,
    order.value.items.map((it) => ({ id: it.menu_item_id, quantity: it.quantity })),
  )
  reused.value = true
  router.push(`/m/${merchantId.value}/catering`)
}
</script>

<template>
  <section>
    <button class="back" type="button" @click="router.push(`/m/${merchantId}/catering/orders`)">← 订单列表</button>

    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>
    <p v-else-if="!order" class="mw-page__desc">加载中…</p>

    <template v-else>
      <div v-if="showPickup" class="mw-card hero" :class="kitchen ? `hero--${kitchen}` : ''">
        <div class="hero__label">取餐号</div>
        <div class="hero__code">{{ order.pickup_code }}</div>
        <div class="hero__status">{{ diningOrderLabel(order) }}</div>
      </div>
      <div v-else class="mw-card">
        <div class="row"><span>订单</span><span>#{{ order.id }}</span></div>
        <div class="row"><span>状态</span><span>{{ diningOrderLabel(order) }}</span></div>
      </div>

      <div class="mw-card timeline">
        <div v-for="s in steps" :key="s.key" class="step" :class="{ 'step--done': s.done, 'step--on': s.current }">
          <i />
          <span>{{ s.label }}</span>
        </div>
      </div>

      <div class="mw-card">
        <div v-if="original > paid" class="row"><span>商品合计</span><span>¥{{ original.toFixed(2) }}</span></div>
        <div v-if="promoOff > 0" class="row"><span>推广折扣</span><span>-¥{{ promoOff.toFixed(2) }}</span></div>
        <div v-if="couponOff > 0" class="row"><span>优惠券</span><span>-¥{{ couponOff.toFixed(2) }}</span></div>
        <div class="row"><span>实付</span><span>¥{{ order.amount }}</span></div>
        <div v-if="order.customer_note" class="row"><span>备注</span><span>{{ order.customer_note }}</span></div>
      </div>

      <div v-if="order.items?.length" class="mw-card">
        <div class="sec-title">明细</div>
        <div v-for="(it, idx) in order.items" :key="idx" class="row">
          <span>{{ it.name }} ×{{ it.quantity }}</span>
          <span>¥{{ it.line_amount }}</span>
        </div>
      </div>

      <p v-if="kitchen && HINTS[kitchen]" class="mw-page__desc">{{ HINTS[kitchen] }}</p>
      <p v-else-if="order.status === 'paid'" class="mw-page__desc">如需退款请联系门店前台。</p>
      <p v-else-if="order.status === 'pending'" class="mw-page__desc">请尽快完成支付；取消后优惠券会退回。</p>
      <p v-else-if="order.status === 'cancelled'" class="mw-page__desc">订单已取消。</p>

      <div v-if="order.status === 'pending'" class="actions">
        <button class="mw-btn mw-btn--ghost mw-btn--block" type="button" :disabled="busy" @click="cancel">
          取消订单
        </button>
        <button class="mw-btn mw-btn--block" type="button" :disabled="busy" @click="pay">
          {{ busy ? '处理中…' : '去支付' }}
        </button>
      </div>
      <button
        v-else-if="order.items?.length"
        class="mw-btn mw-btn--ghost mw-btn--block"
        type="button"
        @click="reorder"
      >
        {{ reused ? '已加入购物车' : '再来一单' }}
      </button>
    </template>
  </section>
</template>

<style scoped>
.back {
  border: 0;
  background: transparent;
  color: var(--mw-brand);
  padding: 0;
  min-height: 0;
  margin-bottom: 12px;
  cursor: pointer;
  font: inherit;
}

.hero {
  text-align: center;
  margin-bottom: 12px;
  background: linear-gradient(145deg, #3d6b5c, #2f5549);
  color: #f7f3ec;
}

.hero--preparing {
  background: linear-gradient(145deg, #c56a2a, #8a4314);
}

.hero--ready {
  background: linear-gradient(145deg, #2f8f78, #1f5f52);
}

.hero--completed {
  background: linear-gradient(145deg, #3a424a, #2a3138);
}

.hero__label {
  font-size: 0.8rem;
  opacity: 0.85;
}

.hero__code {
  font-size: 2.4rem;
  font-weight: 800;
  letter-spacing: 0.08em;
  margin: 4px 0;
}

.hero__status {
  font-size: 0.85rem;
  opacity: 0.9;
}

.timeline {
  display: flex;
  justify-content: space-between;
  gap: 4px;
}

.step {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  color: var(--mw-text-tertiary);
  text-align: center;
}

.step i {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: var(--mw-border);
}

.step--done {
  color: var(--mw-text-secondary);
}

.step--done i {
  background: var(--mw-brand);
}

.step--on {
  color: var(--mw-brand);
  font-weight: 700;
}

.step--on i {
  background: var(--mw-brand);
  box-shadow: 0 0 0 4px var(--mw-brand-muted);
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 6px 0;
  font-size: 0.92rem;
}

.sec-title {
  font-weight: 700;
  margin-bottom: 6px;
}

.mw-card {
  margin-bottom: 12px;
}

.actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-top: 8px;
}
</style>
