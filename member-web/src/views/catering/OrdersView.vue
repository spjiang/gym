<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../../api/http'
import { payMemberOrder } from '../../api/pay'
import {
  diningOrderBucket,
  diningOrderLabel,
  diningStatusTone,
  type DiningBucket,
} from '../../utils/labels'

type Order = {
  id: number
  status: string
  dining_status?: string | null
  amount: string | number
  pickup_code?: string | null
  title?: string
}

const TABS: { id: DiningBucket; label: string }[] = [
  { id: 'all', label: '全部' },
  { id: 'pending', label: '待支付' },
  { id: 'active', label: '进行中' },
  { id: 'done', label: '已结束' },
]

const route = useRoute()
const router = useRouter()
const merchantId = computed(() => Number(route.params.merchantId))
const orders = ref<Order[]>([])
const tab = ref<DiningBucket>('all')
const err = ref('')
const busyId = ref<number | null>(null)

const filtered = computed(() => {
  if (tab.value === 'all') return orders.value
  return orders.value.filter((o) => diningOrderBucket(o) === tab.value)
})

function goDetail(id: number) {
  router.push(`/m/${merchantId.value}/catering/orders/${id}`)
}

function goMenu() {
  router.push(`/m/${merchantId.value}/catering`)
}

function titleOf(o: Order) {
  const raw = (o.title || '').replace(/^.*?点单：/, '')
  return raw || `订单 #${o.id}`
}

function showPickup(o: Order) {
  return o.status === 'paid' && !!o.pickup_code
}

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

async function pay(o: Order) {
  busyId.value = o.id
  err.value = ''
  try {
    await payMemberOrder(o.id)
    await load()
    goDetail(o.id)
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '支付失败'
  } finally {
    busyId.value = null
  }
}

async function cancel(o: Order) {
  if (!window.confirm('取消后订单关闭，已选优惠券将退回。确定取消？')) return
  busyId.value = o.id
  err.value = ''
  try {
    await http.post(`/member/catering/orders/${o.id}/cancel`)
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
  <section>
    <header class="page-head">
      <h1>我的订单</h1>
      <p>待支付可继续付款；制作完成后请到吧台取餐。</p>
    </header>

    <nav class="tabs" aria-label="订单筛选">
      <button
        v-for="t in TABS"
        :key="t.id"
        type="button"
        class="tabs__item"
        :class="{ 'tabs__item--on': tab === t.id }"
        @click="tab = t.id"
      >
        {{ t.label }}
      </button>
    </nav>

    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>
    <div v-else-if="!filtered.length" class="mw-empty">
      {{ tab === 'all' ? '暂无餐饮订单' : '该状态下暂无订单' }}
      <button class="mw-btn mw-btn--ghost mw-btn--sm" type="button" style="margin-top: 12px" @click="goMenu">
        去点餐
      </button>
    </div>

    <article v-for="o in filtered" :key="o.id" class="mw-card order" @click="goDetail(o.id)">
      <div class="order__row">
        <span class="order__title">{{ titleOf(o) }}</span>
        <span :class="diningStatusTone(o)">{{ diningOrderLabel(o) }}</span>
      </div>
      <div class="order__row">
        <span class="order__amt">¥{{ o.amount }}</span>
        <span v-if="showPickup(o)" class="pickup">取餐号 {{ o.pickup_code }}</span>
        <span v-else class="order__id">#{{ o.id }}</span>
      </div>
      <div v-if="o.status === 'pending'" class="order__actions" @click.stop>
        <button class="mw-btn mw-btn--ghost mw-btn--sm" type="button" :disabled="busyId === o.id" @click="cancel(o)">
          取消订单
        </button>
        <button class="mw-btn mw-btn--sm" type="button" :disabled="busyId === o.id" @click="pay(o)">
          {{ busyId === o.id ? '处理中…' : '去支付' }}
        </button>
      </div>
    </article>
  </section>
</template>

<style scoped>
.page-head h1 {
  margin: 0;
  font-size: 1.25rem;
}

.page-head p {
  margin: 4px 0 12px;
  color: var(--mw-text-secondary);
  font-size: 0.85rem;
}

.tabs {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  margin-bottom: 14px;
  scrollbar-width: none;
}

.tabs::-webkit-scrollbar {
  display: none;
}

.tabs__item {
  flex-shrink: 0;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  border: 1px solid var(--mw-border);
  background: var(--mw-surface);
  color: var(--mw-text-secondary);
  font-size: 13px;
  font-weight: 600;
}

.tabs__item--on {
  background: var(--mw-brand);
  border-color: var(--mw-brand);
  color: var(--mw-brand-ink);
}

.order {
  cursor: pointer;
}

.order__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.order__title {
  font-weight: 700;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.order__amt {
  font-weight: 700;
  color: var(--mw-cyan);
}

.order__id {
  font-size: 12px;
  color: var(--mw-text-secondary);
}

.pickup {
  font-weight: 700;
  color: var(--mw-cyan);
}

.order__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 10px;
}

.mw-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
}
</style>
