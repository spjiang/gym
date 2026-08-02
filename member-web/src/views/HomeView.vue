<script setup lang="ts">
import { useAuthStore } from '../stores/auth'
import { RouterLink } from 'vue-router'

const auth = useAuthStore()
</script>

<template>
  <section>
    <h2>你好，{{ auth.me?.name }}</h2>
    <p class="muted">当前商户 #{{ auth.merchantId }}</p>
    <div class="card">
      <RouterLink to="/memberships">查看会籍与课包 →</RouterLink>
    </div>
    <div class="card">
      <RouterLink to="/classes">预约团课 →</RouterLink>
    </div>
    <div class="card">
      <RouterLink to="/shop">购卡 / 买课包 →</RouterLink>
    </div>
    <div class="card">
      <RouterLink to="/coupons">领券中心 →</RouterLink>
    </div>
    <div class="card">
      <RouterLink to="/access">通行记录 →</RouterLink>
    </div>
    <div class="card">
      <RouterLink to="/notifications">消息通知 →</RouterLink>
    </div>
  </section>
</template>

<style scoped>
a {
  color: var(--accent);
  text-decoration: none;
  font-weight: 600;
}
</style>
