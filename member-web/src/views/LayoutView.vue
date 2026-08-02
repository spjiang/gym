<script setup lang="ts">
import { RouterLink, RouterView, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}
</script>

<template>
  <div class="shell">
    <header class="top">
      <div>
        <strong>{{ auth.me?.name }}</strong>
        <div class="muted">{{ auth.me?.phone }}</div>
      </div>
      <div class="right">
        <select
          v-if="(auth.me?.merchant_ids.length || 0) > 1"
          :value="auth.merchantId"
          @change="auth.setMerchantId(Number(($event.target as HTMLSelectElement).value))"
        >
          <option v-for="id in auth.me?.merchant_ids || []" :key="id" :value="id">商户 #{{ id }}</option>
        </select>
        <button class="ghost" @click="logout">退出</button>
      </div>
    </header>
    <main class="main">
      <RouterView />
    </main>
    <nav class="tabs">
      <RouterLink to="/">我的</RouterLink>
      <RouterLink to="/memberships">会籍</RouterLink>
      <RouterLink to="/classes">团课</RouterLink>
      <RouterLink to="/shop">商城</RouterLink>
      <RouterLink to="/coupons">领券</RouterLink>
      <RouterLink to="/access">通行</RouterLink>
    </nav>
  </div>
</template>

<style scoped>
.shell {
  max-width: 480px;
  margin: 0 auto;
  min-height: 100vh;
  padding-bottom: 4.5rem;
}
.top {
  display: flex;
  justify-content: space-between;
  gap: 1rem;
  padding: 1rem;
}
.right {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}
.main {
  padding: 0 1rem 1rem;
}
.tabs {
  position: fixed;
  left: 50%;
  transform: translateX(-50%);
  bottom: 0;
  width: min(480px, 100%);
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  background: #fff;
  border-top: 1px solid var(--border);
  padding: 0.5rem 0 calc(0.5rem + env(safe-area-inset-bottom));
}
.tabs a {
  text-align: center;
  text-decoration: none;
  color: var(--muted);
  font-size: 0.8rem;
  padding: 0.35rem;
}
.tabs a.router-link-active {
  color: var(--accent);
  font-weight: 600;
}
</style>
