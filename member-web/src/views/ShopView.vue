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
  try {
    const { data: order } = await http.post('/member/orders/membership', {
      merchant_id: auth.merchantId,
      product_id: productId,
    })
    const { data: paid } = await http.post(`/member/orders/${order.id}/pay/online`)
    msg.value = `购卡成功，订单 #${paid.id}，实付 ¥${paid.amount}`
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '购买失败'
  }
}

async function buyPt(productId: number) {
  msg.value = ''
  err.value = ''
  try {
    const { data: order } = await http.post('/member/orders/pt-package', {
      merchant_id: auth.merchantId,
      product_id: productId,
    })
    const { data: paid } = await http.post(`/member/orders/${order.id}/pay/online`)
    msg.value = `买课包成功，订单 #${paid.id}，实付 ¥${paid.amount}`
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '购买失败'
  }
}

onMounted(load)
</script>

<template>
  <section>
    <h2>商城</h2>
    <p class="muted">线上支付（开发环境 mock）</p>
    <p v-if="msg" class="muted">{{ msg }}</p>
    <p v-if="err" class="err">{{ err }}</p>
    <h3>会籍卡种</h3>
    <div v-for="p in cards" :key="p.id" class="card row">
      <div>
        <div>{{ p.name }}{{ p.is_trial ? '（体验）' : '' }}</div>
        <div class="muted">¥{{ p.price }}</div>
      </div>
      <button @click="buyCard(p.id)">购买</button>
    </div>
    <h3>私教课包</h3>
    <div v-for="p in pts" :key="p.id" class="card row">
      <div>
        <div>{{ p.name }}</div>
        <div class="muted">¥{{ p.price }} · {{ p.session_count }} 次</div>
      </div>
      <button @click="buyPt(p.id)">购买</button>
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
