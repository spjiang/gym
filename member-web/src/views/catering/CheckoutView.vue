<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QtyStepper from '../../components/QtyStepper.vue'
import http from '../../api/http'
import { payMemberOrder } from '../../api/pay'
import { useCateringCart } from '../../stores/cateringCart'

type MenuItem = {
  id: number
  name: string
  price: string | number
  category: string
  image_url?: string | null
  is_active: boolean
}

type QuoteCoupon = {
  id: number
  name: string
  discount_type: string
  threshold_amount: string | number
  fixed_amount?: string | number | null
  percent_off?: number | null
  eligible: boolean
  ineligible_reason?: string | null
}

type Quote = {
  original_amount: string | number
  promotion_discount_amount: string | number
  promotion_rate: string | number
  coupon_discount_amount: string | number
  payable: string | number
  coupons: QuoteCoupon[]
}

const cart = useCateringCart()
const route = useRoute()
const router = useRouter()
const merchantId = computed(() => Number(route.params.merchantId))

const items = ref<MenuItem[]>([])
const loading = ref(true)
const err = ref('')
const busy = ref(false)
const leaving = ref(false)
const quote = ref<Quote | null>(null)

const qty = computed(() => cart.qtyMap(merchantId.value))
const note = computed({
  get: () => cart.noteOf(merchantId.value),
  set: (v: string) => cart.setNote(merchantId.value, v),
})
const tableNo = computed({
  get: () => cart.tableNoOf(merchantId.value),
  set: (v: string) => cart.setTableNo(merchantId.value, v),
})
const tableLocked = computed(() => cart.tableLockedOf(merchantId.value))
const couponId = computed({
  get: () => cart.couponOf(merchantId.value),
  set: (v: number | null) => cart.setCoupon(merchantId.value, v),
})

const cartLines = computed(() =>
  items.value
    .filter((i) => (qty.value[i.id] || 0) > 0)
    .map((i) => ({ ...i, quantity: qty.value[i.id] })),
)
const subtotal = computed(() =>
  cartLines.value.reduce((sum, i) => sum + Number(i.price) * i.quantity, 0),
)
const payable = computed(() => Number(quote.value?.payable ?? subtotal.value))
const promoOff = computed(() => Number(quote.value?.promotion_discount_amount || 0))
const couponOff = computed(() => Number(quote.value?.coupon_discount_amount || 0))
const eligibleCoupons = computed(() => (quote.value?.coupons || []).filter((c) => c.eligible))
const blockedCoupons = computed(() => (quote.value?.coupons || []).filter((c) => !c.eligible))

function money(n: number) {
  return n.toFixed(2)
}

function couponFace(c: QuoteCoupon) {
  return c.discount_type === 'fixed' ? `减¥${c.fixed_amount}` : `${c.percent_off}%折`
}

function goMenu() {
  router.push(`/m/${merchantId.value}/catering`)
}

function goCoupons() {
  router.push(`/m/${merchantId.value}/catering/coupons`)
}

async function loadMenu() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await http.get<MenuItem[]>('/member/catering/menu', {
      params: { merchant_id: merchantId.value },
    })
    items.value = data
    const validIds = new Set(data.map((i) => i.id))
    for (const id of Object.keys(qty.value).map(Number)) {
      if (!validIds.has(id)) cart.setQty(merchantId.value, id, 0)
    }
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
  } finally {
    loading.value = false
  }
}

async function refreshQuote() {
  if (!cartLines.value.length) {
    quote.value = null
    return
  }
  try {
    const { data } = await http.post<Quote>('/member/catering/quote', {
      merchant_id: merchantId.value,
      items: cartLines.value.map((i) => ({ menu_item_id: i.id, quantity: i.quantity })),
      member_coupon_id: couponId.value || null,
    })
    quote.value = data
    const selected = data.coupons.find((c) => c.id === couponId.value)
    if (couponId.value && selected && !selected.eligible) couponId.value = null
  } catch {
    quote.value = null
  }
}

async function submit() {
  if (!cartLines.value.length) return
  busy.value = true
  err.value = ''
  try {
    const { data: order } = await http.post('/member/catering/checkout', {
      merchant_id: merchantId.value,
      items: cartLines.value.map((i) => ({ menu_item_id: i.id, quantity: i.quantity })),
      note: note.value || null,
      table_no: tableNo.value || null,
      member_coupon_id: couponId.value || null,
    })
    let paid = false
    try {
      await payMemberOrder(order.id)
      paid = true
    } catch (e: unknown) {
      err.value = e instanceof Error ? `${e.message}，可在订单中继续支付` : '支付未完成，可在订单中继续支付'
    }
    leaving.value = true
    if (paid) cart.clear(merchantId.value)
    await router.push(`/m/${merchantId.value}/catering/orders/${order.id}`)
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '下单失败'
  } finally {
    busy.value = false
  }
}

watch(
  () => [cartLines.value.map((i) => `${i.id}:${i.quantity}`).join(','), couponId.value],
  () => {
    void refreshQuote()
  },
)

watch([loading, cartLines, busy], () => {
  if (leaving.value) return
  if (!loading.value && !busy.value && !cartLines.value.length) goMenu()
})

onMounted(async () => {
  await bindTableFromQuery()
  await loadMenu()
  if (!cart.count(merchantId.value)) goMenu()
})

async function bindTableFromQuery() {
  const raw = route.query.table
  const code = typeof raw === 'string' ? raw.trim() : Array.isArray(raw) ? String(raw[0] || '').trim() : ''
  if (!code || !merchantId.value) return
  try {
    const { data } = await http.get<{ name: string }>('/member/catering/table', {
      params: { merchant_id: merchantId.value, code },
    })
    cart.lockTable(merchantId.value, data.name)
  } catch {
    /* 无效桌码时仍允许手填 */
  }
}
</script>

<template>
  <section class="checkout">
    <button class="back" type="button" @click="goMenu">← 返回点餐</button>
    <h1 class="mw-page__title">确认订单</h1>
    <p class="mw-page__desc">核对菜品、桌号与优惠后提交支付</p>

    <p v-if="loading" class="mw-page__desc">加载中…</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <template v-if="!loading && cartLines.length">
      <div class="mw-card">
        <div class="sec">已选菜品</div>
        <div v-for="line in cartLines" :key="line.id" class="line">
          <div class="line__main">
            <div class="line__name">{{ line.name }}</div>
            <div class="line__price">¥{{ line.price }}</div>
          </div>
          <QtyStepper
            :qty="line.quantity"
            @add="cart.add(merchantId, line.id)"
            @sub="cart.sub(merchantId, line.id)"
          />
        </div>
      </div>

      <label class="mw-field">
        <span class="mw-field__label">{{ tableLocked ? '桌号' : '桌号（选填）' }}</span>
        <input
          v-if="!tableLocked"
          v-model="tableNo"
          class="mw-input"
          type="text"
          maxlength="16"
          placeholder="吧台 / A3"
        />
        <span v-else class="seat">{{ tableNo }} · 扫码入座</span>
      </label>
      <label class="mw-field">
        <span class="mw-field__label">备注</span>
        <input v-model="note" class="mw-input" type="text" maxlength="120" placeholder="少冰 / 去冰 / 微辣…" />
      </label>

      <div class="mw-card">
        <div class="sec-row">
          <span class="sec">优惠券</span>
          <button type="button" class="link" @click="goCoupons">去领券</button>
        </div>
        <button
          type="button"
          class="coupon"
          :class="{ 'coupon--on': !couponId }"
          @click="couponId = null"
        >
          不使用优惠券
        </button>
        <button
          v-for="c in eligibleCoupons"
          :key="c.id"
          type="button"
          class="coupon"
          :class="{ 'coupon--on': couponId === c.id }"
          @click="couponId = c.id"
        >
          <span>{{ c.name }} · {{ couponFace(c) }}</span>
          <span class="coupon__meta">满¥{{ c.threshold_amount }}</span>
        </button>
        <div v-for="c in blockedCoupons" :key="c.id" class="coupon coupon--off">
          <span>{{ c.name }} · {{ couponFace(c) }}</span>
          <span class="coupon__meta">{{ c.ineligible_reason || '未满门槛' }}</span>
        </div>
        <p v-if="!(quote?.coupons || []).length" class="mw-page__desc" style="margin: 8px 0 0">
          暂无餐饮券，可先去卡券领取
        </p>
      </div>

      <div class="mw-card break">
        <div><span>商品合计</span><span>¥{{ money(subtotal) }}</span></div>
        <div v-if="promoOff > 0"><span>推广会员折扣</span><span>-¥{{ money(promoOff) }}</span></div>
        <div v-if="couponOff > 0"><span>优惠券</span><span>-¥{{ money(couponOff) }}</span></div>
        <div class="break__pay"><span>实付</span><span>¥{{ money(payable) }}</span></div>
      </div>

      <div class="paybar">
        <div>
          <div class="paybar__label">实付</div>
          <div class="paybar__price">¥{{ money(payable) }}</div>
        </div>
        <button class="mw-btn" type="button" :disabled="busy || !cartLines.length" @click="submit">
          {{ busy ? '提交中…' : '提交并支付' }}
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.checkout {
  padding-bottom: 88px;
}

.back {
  border: 0;
  background: transparent;
  color: var(--mw-brand);
  padding: 0;
  min-height: 0;
  margin-bottom: 8px;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
}

.sec {
  font-size: 13px;
  font-weight: 700;
  color: var(--mw-text-secondary);
  margin-bottom: 8px;
}

.sec-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.sec-row .sec {
  margin: 0;
}

.link {
  min-height: 0;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--mw-brand);
  font-size: 13px;
  font-weight: 600;
}

.line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-top: 1px solid var(--mw-border);
}

.line:first-of-type {
  border-top: 0;
  padding-top: 0;
}

.line__name {
  font-weight: 650;
}

.line__price {
  font-size: 13px;
  color: var(--mw-cyan);
  font-weight: 700;
}

.coupon {
  width: 100%;
  display: flex;
  justify-content: space-between;
  gap: 8px;
  min-height: 44px;
  margin-bottom: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--mw-border);
  background: var(--mw-bg);
  color: var(--mw-text);
  text-align: left;
}

.coupon--on {
  border-color: var(--mw-brand);
  background: var(--mw-brand-muted);
}

.coupon--off {
  opacity: 0.55;
}

.coupon__meta {
  color: var(--mw-text-secondary);
  font-size: 12px;
  flex-shrink: 0;
}

.break {
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 14px;
  color: var(--mw-text-secondary);
}

.break div {
  display: flex;
  justify-content: space-between;
}

.break__pay {
  color: var(--mw-text);
  font-weight: 700;
  font-size: 16px;
}

.paybar {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: calc(var(--mw-tab-h) + var(--mw-safe-bottom));
  width: min(100%, var(--mw-shell-max));
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 16px;
  background: var(--mw-bg-elevated);
  border-top: 1px solid var(--mw-border);
  z-index: 25;
}

.paybar__label {
  font-size: 12px;
  color: var(--mw-text-secondary);
}

.paybar__price {
  font-size: 1.15rem;
  font-weight: 800;
  color: var(--mw-cyan);
}

.seat {
  display: block;
  padding: 10px 12px;
  border-radius: 10px;
  background: rgba(45, 212, 191, 0.16);
  color: var(--mw-cyan);
  font-weight: 650;
}
</style>
