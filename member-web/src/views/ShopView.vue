<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

type Product = {
  id: number
  name: string
  price: string
  product_type?: string
  session_count?: number
  is_trial?: boolean
}
const auth = useAuthStore()
const cards = ref<Product[]>([])
const pts = ref<Product[]>([])
const msg = ref('')
const err = ref('')
const busyId = ref<number | null>(null)

async function load() {
  const mid = auth.merchantId
  const [c, p] = await Promise.all([
    http.get('/member/catalog/membership-products', { params: { merchant_id: mid } }),
    http.get('/member/catalog/pt-products', { params: { merchant_id: mid } }),
  ])
  cards.value = c.data
  pts.value = p.data
}

async function buyCard(productId: number) {
  msg.value = ''
  err.value = ''
  busyId.value = productId
  try {
    const { data: order } = await http.post('/member/orders/membership', {
      merchant_id: auth.merchantId,
      product_id: productId,
    })
    const { data: paid } = await http.post(`/member/orders/${order.id}/pay/online`)
    msg.value = `购卡成功，订单 #${paid.id}，实付 ¥${paid.amount}`
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '购买失败'
  } finally {
    busyId.value = null
  }
}

async function buyPt(productId: number) {
  msg.value = ''
  err.value = ''
  busyId.value = productId
  try {
    const { data: order } = await http.post('/member/orders/pt-package', {
      merchant_id: auth.merchantId,
      product_id: productId,
    })
    const { data: paid } = await http.post(`/member/orders/${order.id}/pay/online`)
    msg.value = `购买成功，订单 #${paid.id}，实付 ¥${paid.amount}`
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '购买失败'
  } finally {
    busyId.value = null
  }
}

onMounted(load)
</script>

<template>
  <section class="mw-page">
    <h1 class="mw-page__title">商城</h1>
    <p class="mw-page__desc">购买会籍或私教课包，支付结果以订单状态为准</p>
    <p v-if="msg" class="mw-msg mw-msg--ok">{{ msg }}</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <h2 class="mw-section-title">会籍卡种</h2>
    <div v-for="p in cards" :key="p.id" class="mw-card mw-list-row">
      <div class="mw-list-row__main">
        <div class="mw-list-row__title">
          {{ p.name }}
          <span v-if="p.is_trial" class="mw-status">体验</span>
        </div>
        <div class="mw-price">¥{{ p.price }}</div>
      </div>
      <button
        class="mw-btn mw-btn--sm mw-list-row__action"
        type="button"
        :disabled="busyId === p.id"
        @click="buyCard(p.id)"
      >
        {{ busyId === p.id ? '支付中' : '购买' }}
      </button>
    </div>
    <div v-if="!cards.length" class="mw-empty">暂无可售卡种</div>

    <h2 class="mw-section-title">私教课包</h2>
    <div v-for="p in pts" :key="p.id" class="mw-card mw-list-row">
      <div class="mw-list-row__main">
        <div class="mw-list-row__title">{{ p.name }}</div>
        <div class="mw-list-row__meta">
          <span class="mw-price">¥{{ p.price }}</span> · {{ p.session_count }} 次
        </div>
      </div>
      <button
        class="mw-btn mw-btn--sm mw-list-row__action"
        type="button"
        :disabled="busyId === p.id"
        @click="buyPt(p.id)"
      >
        {{ busyId === p.id ? '支付中' : '购买' }}
      </button>
    </div>
    <div v-if="!pts.length" class="mw-empty">暂无课包</div>
  </section>
</template>
