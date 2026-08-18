<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import QtyStepper from '../../components/QtyStepper.vue'
import http from '../../api/http'
import { useCateringCart } from '../../stores/cateringCart'

type MenuItem = {
  id: number
  merchant_id: number
  name: string
  price: string | number
  category: string
  image_url?: string | null
  description?: string | null
  is_active: boolean
}

const route = useRoute()
const router = useRouter()
const cart = useCateringCart()
const merchantId = computed(() => Number(route.params.merchantId))
const itemId = computed(() => Number(route.params.itemId))
const item = ref<MenuItem | null>(null)
const err = ref('')
const loading = ref(true)

const qty = computed(() => cart.qtyOf(merchantId.value, itemId.value))
const cartCount = computed(() => cart.count(merchantId.value))

function goMenu() {
  router.push(`/m/${merchantId.value}/catering`)
}

function goCheckout() {
  if (qty.value <= 0 && item.value) cart.add(merchantId.value, item.value.id)
  router.push(`/m/${merchantId.value}/catering/checkout`)
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await http.get<MenuItem>(`/member/catering/menu/${itemId.value}`, {
      params: { merchant_id: merchantId.value },
    })
    if (data.merchant_id !== merchantId.value) {
      err.value = '该菜品不属于当前门店'
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

watch(itemId, load, { immediate: true })
</script>

<template>
  <section class="mw-page dish-page">
    <button class="back" type="button" @click="goMenu">← 点餐</button>

    <p v-if="loading" class="mw-page__desc">加载中…</p>
    <p v-else-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <template v-else-if="item">
      <div class="hero">
        <img v-if="item.image_url" :src="item.image_url" :alt="item.name" />
        <span v-else>{{ item.name.slice(0, 1) }}</span>
      </div>

      <h1 class="mw-page__title">{{ item.name }}</h1>
      <p v-if="item.category" class="mw-page__desc">{{ item.category }}</p>
      <div class="price">¥{{ item.price }}</div>

      <div class="mw-card">
        <div class="sec">介绍</div>
        <p class="desc">{{ item.description?.trim() || '暂无介绍' }}</p>
      </div>

      <div class="bar">
        <QtyStepper
          :qty="qty"
          @add="cart.add(merchantId, item.id)"
          @sub="cart.sub(merchantId, item.id)"
        />
        <button v-if="qty <= 0" class="mw-btn" type="button" @click="cart.add(merchantId, item.id)">
          加入购物车
        </button>
        <button v-else class="mw-btn" type="button" @click="goCheckout">
          去结算{{ cartCount > qty ? ` · ${cartCount}件` : '' }}
        </button>
      </div>
    </template>
  </section>
</template>

<style scoped>
.dish-page {
  padding-bottom: 88px;
}

.back {
  border: 0;
  background: transparent;
  color: var(--mw-brand);
  padding: 0;
  min-height: 0;
  margin-bottom: var(--mw-space-4);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
}

.hero {
  width: 100%;
  aspect-ratio: 4 / 3;
  border-radius: var(--mw-radius-lg);
  overflow: hidden;
  display: grid;
  place-items: center;
  background: var(--mw-brand);
  color: var(--mw-brand-ink);
  font-weight: 800;
  font-size: 72px;
  margin-bottom: var(--mw-space-4);
}

.hero img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.price {
  margin: 4px 0 16px;
  color: var(--mw-cyan);
  font-size: 1.35rem;
  font-weight: 700;
}

.sec {
  font-size: 0.78rem;
  color: var(--mw-text-secondary);
  margin-bottom: 8px;
}

.desc {
  margin: 0;
  white-space: pre-wrap;
  line-height: 1.65;
}

.bar {
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

.bar .mw-btn {
  flex: 1;
}
</style>
