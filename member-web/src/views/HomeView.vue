<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const mid = computed(() => Number(route.params.merchantId) || auth.merchantId)

const menus = computed(() => [
  { to: `/m/${mid.value}/gym/memberships`, title: '会籍与课包', desc: '查看有效期、剩余次数与课时' },
  { to: `/m/${mid.value}/gym/classes`, title: '团课预约', desc: '浏览场次并预约 / 取消' },
  { to: `/m/${mid.value}/gym/shop`, title: '在线商城', desc: '购买会籍卡种与私教课包' },
  { to: `/m/${mid.value}/gym/coupons`, title: '优惠卡券', desc: '领取优惠券并查看我的券' },
  { to: `/m/${mid.value}/gym/access`, title: '通行记录', desc: '门禁进出记录查询' },
  { to: `/m/${mid.value}/gym/notifications`, title: '消息中心', desc: '系统通知与业务提醒' },
  { to: '/me', title: '个人中心', desc: '资料、人脸状态、关联门店与退出' },
])
</script>

<template>
  <section class="mw-page">
    <h1 class="mw-page__title">你好，{{ auth.me?.name }}</h1>
    <p class="mw-page__desc">{{ auth.currentMerchant?.name || `商户 #${mid}` }} · 选择下方功能继续操作</p>

    <div class="menu">
      <RouterLink v-for="m in menus" :key="m.to" :to="m.to" class="mw-card mw-link-card">
        <div class="mw-link-card__title">{{ m.title }}</div>
        <div class="mw-link-card__desc">{{ m.desc }}</div>
      </RouterLink>
    </div>
  </section>
</template>

<style scoped>
.menu {
  display: flex;
  flex-direction: column;
}
</style>
