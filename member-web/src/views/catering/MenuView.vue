<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QtyStepper from '../../components/QtyStepper.vue'
import http from '../../api/http'
import { useAuthStore } from '../../stores/auth'
import { useCateringCart } from '../../stores/cateringCart'

type MenuItem = {
  id: number
  merchant_id: number
  name: string
  price: string | number
  category: string
  category_id?: number | null
  image_url?: string | null
  description?: string | null
  is_active: boolean
}

const auth = useAuthStore()
const cart = useCateringCart()
const route = useRoute()
const router = useRouter()
const merchantId = computed(() => Number(route.params.merchantId))

const items = ref<MenuItem[]>([])
const qty = computed(() => cart.qtyMap(merchantId.value))
const loading = ref(false)
const err = ref('')
const activeCat = ref('')
const sheetOpen = ref(false)

const categories = computed(() => grouped.value.map((g) => g.category))

const grouped = computed(() => {
  const order: { key: string; category: string }[] = []
  const buckets = new Map<string, MenuItem[]>()
  for (const item of items.value) {
    const key = item.category_id != null ? `id:${item.category_id}` : item.category?.trim() || '其他'
    const label = item.category?.trim() || '其他'
    if (!buckets.has(key)) {
      buckets.set(key, [])
      order.push({ key, category: label })
    }
    buckets.get(key)!.push(item)
  }
  return order.map((g) => ({ category: g.category, items: buckets.get(g.key) || [] }))
})

const cartLines = computed(() =>
  items.value
    .filter((i) => (qty.value[i.id] || 0) > 0)
    .map((i) => ({ ...i, quantity: qty.value[i.id] })),
)

const cartCount = computed(() => cart.count(merchantId.value))
const subtotal = computed(() =>
  cartLines.value.reduce((sum, i) => sum + Number(i.price) * i.quantity, 0),
)
const tableNo = computed(() => cart.tableNoOf(merchantId.value))
const tableLocked = computed(() => cart.tableLockedOf(merchantId.value))

function money(n: number) {
  return n.toFixed(2)
}

function goDetail(id: number) {
  router.push(`/m/${merchantId.value}/catering/items/${id}`)
}

function goCheckout() {
  if (!cartLines.value.length) return
  sheetOpen.value = false
  const table = typeof route.query.table === 'string' ? route.query.table : ''
  router.push({
    path: `/m/${merchantId.value}/catering/checkout`,
    query: table ? { table } : {},
  })
}

async function jump(category: string) {
  activeCat.value = category
  await nextTick()
  document.getElementById(`cat-${category}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await http.get<MenuItem[]>('/member/catering/menu', {
      params: { merchant_id: merchantId.value },
    })
    items.value = data
    activeCat.value = categories.value[0] || ''
    await bindTableFromQuery()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '菜单加载失败'
  } finally {
    loading.value = false
  }
}

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
    /* 桌码无效时仍可点餐，结算页允许手填 */
  }
}

onMounted(load)
</script>

<template>
  <section class="menu">
    <header class="page-head">
      <h1>点餐</h1>
      <p>{{ auth.currentMerchant?.name }} · 选好后去结算</p>
      <p v-if="tableLocked && tableNo" class="seat">当前桌号 {{ tableNo }} · 下单后厨房按此出餐</p>
    </header>

    <p v-if="loading" class="mw-page__desc">加载中…</p>
    <p v-else-if="err" class="mw-msg mw-msg--error">{{ err }}</p>
    <p v-else-if="!items.length" class="mw-empty">暂无上架菜品</p>

    <template v-else>
      <nav class="cats" aria-label="菜品分类">
        <button
          v-for="cat in categories"
          :key="cat"
          type="button"
          class="cats__item"
          :class="{ 'cats__item--on': activeCat === cat }"
          @click="jump(cat)"
        >
          {{ cat }}
        </button>
      </nav>

      <section v-for="group in grouped" :id="`cat-${group.category}`" :key="group.category" class="group">
        <h2 class="group__title">{{ group.category }}</h2>
        <article
          v-for="item in group.items"
          :key="item.id"
          class="dish mw-card"
          role="link"
          tabindex="0"
          @click="goDetail(item.id)"
          @keydown.enter="goDetail(item.id)"
        >
          <div class="dish__media">
            <img v-if="item.image_url" :src="item.image_url" alt="" />
            <span v-else>{{ item.name.slice(0, 1) }}</span>
          </div>
          <div class="dish__info">
            <div class="dish__name">{{ item.name }}</div>
            <div v-if="item.description" class="dish__desc">{{ item.description }}</div>
            <div class="dish__price">¥{{ item.price }}</div>
          </div>
          <QtyStepper
            :qty="qty[item.id] || 0"
            @add="cart.add(merchantId, item.id)"
            @sub="cart.sub(merchantId, item.id)"
          />
        </article>
      </section>
    </template>

    <div v-if="cartCount" class="cartbar">
      <button type="button" class="cartbar__info" @click="sheetOpen = true">
        <span class="cartbar__badge">{{ cartCount }}</span>
        <span>已选 · ¥{{ money(subtotal) }}</span>
      </button>
      <button class="mw-btn" type="button" @click="goCheckout">去结算</button>
    </div>

    <div v-if="sheetOpen" class="sheet" role="dialog" aria-label="购物车">
      <button type="button" class="sheet__mask" aria-label="关闭" @click="sheetOpen = false" />
      <div class="sheet__panel">
        <div class="sheet__head">
          <strong>已选菜品</strong>
          <button type="button" class="sheet__clear" @click="cart.clear(merchantId); sheetOpen = false">
            清空
          </button>
        </div>
        <div v-for="line in cartLines" :key="line.id" class="sheet__row">
          <div>
            <div class="sheet__name">{{ line.name }}</div>
            <div class="dish__price">¥{{ line.price }}</div>
          </div>
          <QtyStepper
            :qty="line.quantity"
            @add="cart.add(merchantId, line.id)"
            @sub="cart.sub(merchantId, line.id)"
          />
        </div>
        <button class="mw-btn mw-btn--block" type="button" @click="goCheckout">去结算 ¥{{ money(subtotal) }}</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.menu {
  padding-bottom: 72px;
}

.page-head h1 {
  margin: 0;
  font-size: 1.25rem;
}

.page-head p {
  margin: 4px 0 12px;
  color: var(--mw-text-secondary);
  font-size: 0.85rem;
}

.page-head .seat {
  margin-top: 0;
  color: var(--mw-cyan);
  font-weight: 650;
}

.cats {
  position: sticky;
  top: 0;
  z-index: 8;
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 4px 0 12px;
  margin: 0 -4px 8px;
  background: var(--mw-bg);
  scrollbar-width: none;
}

.cats::-webkit-scrollbar {
  display: none;
}

.cats__item {
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

.cats__item--on {
  background: var(--mw-brand);
  border-color: var(--mw-brand);
  color: var(--mw-brand-ink);
}

.group {
  scroll-margin-top: 56px;
}

.group__title {
  margin: 8px 0 10px;
  font-size: 13px;
  font-weight: 700;
  color: var(--mw-text-secondary);
}

.dish {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
  cursor: pointer;
}

.dish__media {
  width: 72px;
  height: 72px;
  border-radius: 10px;
  overflow: hidden;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  background: var(--mw-brand);
  color: var(--mw-brand-ink);
  font-weight: 700;
  font-size: 22px;
}

.dish__media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dish__info {
  flex: 1;
  min-width: 0;
}

.dish__name {
  font-weight: 700;
}

.dish__desc {
  margin-top: 2px;
  font-size: 12px;
  color: var(--mw-text-secondary);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.dish__price {
  margin-top: 4px;
  color: var(--mw-cyan);
  font-weight: 700;
}

.cartbar {
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

.cartbar__info {
  display: flex;
  align-items: center;
  gap: 10px;
  min-height: 40px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--mw-text);
  font-weight: 700;
}

.cartbar__badge {
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 999px;
  display: grid;
  place-items: center;
  background: var(--mw-brand);
  color: var(--mw-brand-ink);
  font-size: 12px;
}

.sheet {
  position: fixed;
  inset: 0;
  z-index: 40;
}

.sheet__mask {
  position: absolute;
  inset: 0;
  border: 0;
  min-height: 0;
  padding: 0;
  background: rgba(0, 0, 0, 0.55);
}

.sheet__panel {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: 0;
  width: min(100%, var(--mw-shell-max));
  max-height: 70vh;
  overflow: auto;
  padding: 16px 16px calc(16px + var(--mw-safe-bottom));
  border-radius: 16px 16px 0 0;
  background: var(--mw-bg-elevated);
}

.sheet__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.sheet__clear {
  min-height: 32px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--mw-text-secondary);
  font-size: 13px;
}

.sheet__row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--mw-border);
}

.sheet__name {
  font-weight: 650;
}

.sheet__panel .mw-btn {
  margin-top: 16px;
}
</style>
