<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const tabs = [
  { to: '/', label: '首页' },
  { to: '/memberships', label: '会籍' },
  { to: '/classes', label: '团课' },
  { to: '/shop', label: '商城' },
  { to: '/coupons', label: '卡券' },
  { to: '/access', label: '通行' },
]

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="shell">
    <header class="topbar">
      <div class="topbar__user">
        <div class="topbar__avatar" aria-hidden="true">{{ auth.me?.name?.slice(0, 1) || '会' }}</div>
        <div class="topbar__meta">
          <div class="topbar__name">{{ auth.me?.name }}</div>
          <div class="topbar__phone">{{ auth.me?.phone }}</div>
        </div>
      </div>
      <div class="topbar__actions">
        <select
          v-if="(auth.me?.merchant_ids.length || 0) > 1"
          class="mw-input mw-select topbar__merchant"
          :value="auth.merchantId"
          aria-label="切换商户"
          @change="auth.setMerchantId(Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="id in auth.me?.merchant_ids || []" :key="id" :value="id">商户 #{{ id }}</option>
        </select>
        <button class="mw-btn mw-btn--ghost mw-btn--sm" type="button" @click="logout">退出</button>
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
  gap: var(--mw-space-3);
  min-width: 0;
}

.topbar__avatar {
  width: 36px;
  height: 36px;
  border-radius: var(--mw-radius-sm);
  display: grid;
  place-items: center;
  font-size: 14px;
  font-weight: 700;
  color: var(--mw-brand-ink);
  background: var(--mw-brand);
  flex-shrink: 0;
}

.topbar__name {
  font-size: 14px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 8.5rem;
}

.topbar__phone {
  font-size: 12px;
  color: var(--mw-text-secondary);
}

.topbar__actions {
  display: flex;
  align-items: center;
  gap: var(--mw-space-2);
}

.topbar__merchant {
  width: auto;
  min-width: 6.5rem;
  min-height: 32px;
  font-size: 12px;
  padding: 0 24px 0 8px;
}

.content {
  padding: var(--mw-space-4);
}

.tabbar {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 0;
  width: min(var(--mw-shell-max), 100%);
  height: calc(var(--mw-tab-h) + var(--mw-safe-bottom));
  padding-bottom: var(--mw-safe-bottom);
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  background: var(--mw-bg-elevated);
  border-top: 1px solid var(--mw-border);
  z-index: 30;
}

.tabbar__item {
  display: flex;
  align-items: center;
  justify-content: center;
  text-decoration: none;
  color: var(--mw-text-tertiary);
  font-size: 12px;
  font-weight: 500;
  border-top: 2px solid transparent;
  margin-top: -1px;
}

.tabbar__item.router-link-active {
  color: var(--mw-brand);
  font-weight: 600;
  border-top-color: var(--mw-brand);
}
</style>
