<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'

type Order = {
  id: number
  status: string
  amount: string | number
  pickup_code?: string | null
  title?: string
}

const route = useRoute()
const router = useRouter()
const merchantId = computed(() => Number(route.params.merchantId))
const orders = ref<Order[]>([])
const err = ref('')

async function load() {
  try {
    const { data } = await http.get<Order[]>('/member/catering/orders', {
      params: { merchant_id: merchantId.value },
    })
    orders.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
  }
}

onMounted(load)
</script>

<template>
  <section>
    <header class="page-head">
      <h1>我的订单</h1>
    </header>
    <p v-if="err" class="err">{{ err }}</p>
    <p v-else-if="!orders.length" class="hint">暂无餐饮订单</p>

    <button
      v-for="o in orders"
      :key="o.id"
      type="button"
      class="mw-card order"
      @click="router.push(`/m/${merchantId}/catering/orders/${o.id}`)"
    >
      <div class="order__row">
        <span>#{{ o.id }}</span>
        <span class="status">{{ o.status }}</span>
      </div>
      <div class="order__row">
        <span>¥{{ o.amount }}</span>
        <span v-if="o.pickup_code" class="pickup">取餐号 {{ o.pickup_code }}</span>
      </div>
    </button>
  </section>
</template>

<style scoped>
.page-head h1 {
  margin: 0 0 16px;
  font-size: 1.25rem;
}
.order {
  width: 100%;
  text-align: left;
  margin-bottom: 10px;
  cursor: pointer;
  border: 1px solid var(--mw-border);
  font: inherit;
  color: inherit;
  display: block;
}
.order__row {
  display: flex;
  justify-content: space-between;
  margin-bottom: 4px;
}
.status {
  font-size: 0.8rem;
  color: var(--mw-muted, #78716c);
}
.pickup {
  font-weight: 700;
  color: #2f5549;
}
.hint,
.err {
  color: var(--mw-muted, #78716c);
}
.err {
  color: #b42318;
}
</style>
