<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, RouterView, useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const mid = computed(() => Number(route.params.merchantId))
const isCatering = computed(() => route.path.includes('/catering'))

const gymTabs = computed(() => [
  { to: `/m/${mid.value}/gym`, label: '首页' },
  { to: `/m/${mid.value}/gym/memberships`, label: '会籍' },
  { to: `/m/${mid.value}/gym/classes`, label: '团课' },
  { to: `/m/${mid.value}/gym/shop`, label: '商城' },
  { to: `/m/${mid.value}/gym/coupons`, label: '卡券' },
  { to: `/m/${mid.value}/gym/access`, label: '通行' },
])

const cateringTabs = computed(() => [
  { to: `/m/${mid.value}/catering`, label: '点餐' },
  { to: `/m/${mid.value}/catering/orders`, label: '订单' },
  { to: '/me', label: '我的' },
])

const tabs = computed(() => (isCatering.value ? cateringTabs.value : gymTabs.value))
const systemLabel = computed(() => (isCatering.value ? '观野BAR' : '观野FIT'))

function switchStore() {
  router.push({ name: 'stores' })
}

function goMe() {
  router.push({ name: 'me' })
}
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <button class="topbar__user" type="button" @click="goMe" title="个人中心">
        <div class="topbar__avatar" aria-hidden="true">{{ auth.me?.name?.slice(0, 1) || '会' }}</div>
        <div class="topbar__meta">
          <div class="topbar__name">{{ auth.currentMerchant?.name || '门店' }}</div>
          <div class="topbar__phone">{{ systemLabel }} · {{ auth.me?.name }}</div>
        </div>
      </button>
      <div class="topbar__actions">
        <button class="mw-btn mw-btn--ghost mw-btn--sm" type="button" @click="switchStore">切换</button>
        <button class="mw-btn mw-btn--ghost mw-btn--sm" type="button" @click="goMe">我的</button>
      </div>
    </header>

    <main class="content">
      <RouterView />
    </main>

    <nav class="tabbar" aria-label="底部导航">
      <RouterLink v-for="t in tabs" :key="t.to" :to="t.to" class="tabbar__item">
        {{ t.label }}
      </RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.shell {
  max-width: var(--mw-shell-max);
  margin: 0 auto;
  min-height: 100vh;
  padding-bottom: calc(var(--mw-tab-h) + var(--mw-safe-bottom) + 8px);
  background: var(--mw-bg);
}

.topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mw-space-3);
  padding: var(--mw-space-3) var(--mw-space-4);
  border-bottom: 1px solid var(--mw-border);
  background: var(--mw-bg-elevated);
  position: sticky;
  top: 0;
  z-index: 20;
}

.topbar__user {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.topbar__avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--mw-brand);
  color: var(--mw-brand-ink);
  font-weight: 700;
  flex-shrink: 0;
}

.topbar__name {
  font-weight: 700;
  font-size: 0.92rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 42vw;
}

.topbar__phone {
  font-size: 0.72rem;
  color: var(--mw-text-secondary);
}

.topbar__actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.content {
  padding: var(--mw-space-4);
}

.tabbar {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 0;
  width: min(100%, var(--mw-shell-max));
  height: calc(var(--mw-tab-h) + var(--mw-safe-bottom));
  padding-bottom: var(--mw-safe-bottom);
  display: flex;
  background: var(--mw-bg-elevated);
  border-top: 1px solid var(--mw-border);
  z-index: 30;
}

.tabbar__item {
  flex: 1;
  display: grid;
  place-items: center;
  font-size: 0.78rem;
  color: var(--mw-text-tertiary);
  text-decoration: none;
}

.tabbar__item.router-link-active {
  color: var(--mw-brand);
  font-weight: 700;
}
</style>
