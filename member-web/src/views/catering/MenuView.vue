<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import { payMemberOrder } from '../../api/pay'
import { useAuthStore } from '../../stores/auth'

type MenuItem = {
  id: number
  merchant_id: number
  name: string
  price: string | number
  category: string
  is_active: boolean
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const merchantId = computed(() => Number(route.params.merchantId))

const items = ref<MenuItem[]>([])
const qty = reactive<Record<number, number>>({})
const note = ref('')
const loading = ref(false)
const err = ref('')
const busy = ref(false)

const cartLines = computed(() =>
  items.value
    .filter((i) => (qty[i.id] || 0) > 0)
    .map((i) => ({ ...i, quantity: qty[i.id] })),
)
const total = computed(() =>
  cartLines.value.reduce((s, i) => s + Number(i.price) * i.quantity, 0),
)

function add(id: number) {
  qty[id] = (qty[id] || 0) + 1
}

function sub(id: number) {
  const n = (qty[id] || 0) - 1
  qty[id] = n > 0 ? n : 0
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await http.get<MenuItem[]>('/member/catering/menu', {
      params: { merchant_id: merchantId.value },
    })
    items.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '菜单加载失败'
  } finally {
    loading.value = false
  }
}

async function checkout() {
  if (!cartLines.value.length) return
  busy.value = true
  err.value = ''
  try {
    const { data: order } = await http.post('/member/catering/checkout', {
      merchant_id: merchantId.value,
      items: cartLines.value.map((i) => ({ menu_item_id: i.id, quantity: i.quantity })),
      note: note.value || null,
    })
    await payMemberOrder(order.id)
    for (const k of Object.keys(qty)) qty[Number(k)] = 0
    note.value = ''
    router.push(`/m/${merchantId.value}/catering/orders/${order.id}`)
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '下单失败'
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <section>
    <header class="page-head">
      <h1>点餐</h1>
      <p>{{ auth.currentMerchant?.name }} · 演示支付</p>
    </header>

    <p v-if="loading" class="hint">加载中…</p>
    <p v-else-if="err" class="err">{{ err }}</p>
    <p v-else-if="!items.length" class="hint">暂无上架菜品</p>

    <article v-for="item in items" :key="item.id" class="mw-card dish">
      <div class="dish__info">
        <div class="dish__name">{{ item.name }}</div>
        <div v-if="item.category" class="dish__cat">{{ item.category }}</div>
        <div class="dish__price">¥{{ item.price }}</div>
      </div>
      <div class="dish__qty">
        <button type="button" class="qty-btn" :disabled="!(qty[item.id] > 0)" @click="sub(item.id)">−</button>
        <span>{{ qty[item.id] || 0 }}</span>
        <button type="button" class="qty-btn" @click="add(item.id)">+</button>
      </div>
    </article>

    <div v-if="cartLines.length" class="cart mw-card">
      <label class="note">
        备注
        <input v-model="note" type="text" placeholder="少冰 / 微辣…" maxlength="120" />
      </label>
      <div class="cart__row">
        <span>合计 ¥{{ total.toFixed(2) }}</span>
        <button class="mw-btn mw-btn--primary" type="button" :disabled="busy" @click="checkout">
          {{ busy ? '提交中…' : '下单并支付' }}
        </button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.page-head h1 {
  margin: 0;
  font-size: 1.25rem;
}
.page-head p {
  margin: 4px 0 16px;
  color: var(--mw-muted, #78716c);
  font-size: 0.85rem;
}
.dish {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}
.dish__name {
  font-weight: 700;
}
.dish__cat {
  font-size: 0.75rem;
  color: var(--mw-muted, #78716c);
}
.dish__price {
  margin-top: 4px;
  color: #2f5549;
  font-weight: 600;
}
.dish__qty {
  display: flex;
  align-items: center;
  gap: 8px;
}
.qty-btn {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  border: 1px solid var(--mw-border);
  background: #fff;
  font-size: 1rem;
  line-height: 1;
  cursor: pointer;
}
.qty-btn:disabled {
  opacity: 0.4;
}
.cart {
  position: sticky;
  bottom: calc(var(--mw-tab-h) + var(--mw-safe-bottom) + 12px);
  margin-top: 16px;
}
.note {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 0.85rem;
  margin-bottom: 12px;
}
.note input {
  border: 1px solid var(--mw-border);
  border-radius: 8px;
  padding: 8px 10px;
  font: inherit;
}
.cart__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 700;
}
.hint,
.err {
  color: var(--mw-muted, #78716c);
}
.err {
  color: #b42318;
}
</style>
