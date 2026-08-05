<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'

type OrderDetail = {
  id: number
  status: string
  amount: string | number
  pickup_code?: string | null
  customer_note?: string | null
  items?: {
    name: string
    quantity: number
    unit_price: string | number
    line_amount: string | number
  }[]
}

const route = useRoute()
const router = useRouter()
const merchantId = computed(() => Number(route.params.merchantId))
const orderId = computed(() => Number(route.params.orderId))
const order = ref<OrderDetail | null>(null)
const err = ref('')
const busy = ref(false)

async function load() {
  try {
    const { data } = await http.get<OrderDetail>(`/member/catering/orders/${orderId.value}`)
    order.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
  }
}

async function refund() {
  if (!order.value || order.value.status !== 'paid') return
  if (!confirm('确认申请退款？')) return
  busy.value = true
  err.value = ''
  try {
    const { data } = await http.post<OrderDetail>(`/member/catering/orders/${orderId.value}/refund`)
    order.value = { ...order.value, ...data }
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '退款失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <section>
    <button class="back" type="button" @click="router.push(`/m/${merchantId}/catering/orders`)">← 订单列表</button>

    <p v-if="err" class="err">{{ err }}</p>
    <p v-else-if="!order" class="hint">加载中…</p>

    <template v-else>
      <div class="mw-card hero" v-if="order.pickup_code">
        <div class="hero__label">取餐号</div>
        <div class="hero__code">{{ order.pickup_code }}</div>
        <div class="hero__status">{{ order.status }}</div>
      </div>

      <div class="mw-card">
        <div class="row"><span>订单</span><span>#{{ order.id }}</span></div>
        <div class="row"><span>状态</span><span>{{ order.status }}</span></div>
        <div class="row"><span>金额</span><span>¥{{ order.amount }}</span></div>
        <div v-if="order.customer_note" class="row"><span>备注</span><span>{{ order.customer_note }}</span></div>
      </div>

      <div v-if="order.items?.length" class="mw-card">
        <div class="sec-title">明细</div>
        <div v-for="(it, idx) in order.items" :key="idx" class="row">
          <span>{{ it.name }} ×{{ it.quantity }}</span>
          <span>¥{{ it.line_amount }}</span>
        </div>
      </div>

      <button
        v-if="order.status === 'paid'"
        class="mw-btn mw-btn--ghost"
        type="button"
        :disabled="busy"
        @click="refund"
      >
        {{ busy ? '处理中…' : '申请退款' }}
      </button>
    </template>
  </section>
</template>

<style scoped>
.back {
  border: 0;
  background: transparent;
  color: #2f5549;
  padding: 0;
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
.hint,
.err {
  color: var(--mw-muted, #78716c);
}
.err {
  color: #b42318;
}
</style>
