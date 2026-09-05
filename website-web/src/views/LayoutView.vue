<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import BrandMark from '../components/BrandMark.vue'
import { copyrightLine } from '../copyright'
import { useSiteStore } from '../stores/site'

const site = useSiteStore()
const route = useRoute()
const overHero = computed(() => route.name === 'home')

onMounted(() => {
  void site.load()
})
</script>

<template>
  <div class="shell">
    <header class="nav" :class="{ over: overHero }">
      <RouterLink to="/" class="logo" aria-label="首页">
        <BrandMark compact />
      </RouterLink>
      <nav>
        <RouterLink to="/" exact-active-class="router-link-active" active-class="">首页</RouterLink>
        <RouterLink to="/space">SPACE</RouterLink>
        <RouterLink to="/fit">FIT</RouterLink>
        <RouterLink to="/bar">BAR</RouterLink>
        <RouterLink to="/news">新闻</RouterLink>
        <RouterLink to="/jobs">招聘</RouterLink>
        <RouterLink to="/partners">招商</RouterLink>
      </nav>
      <a
        v-if="site.data?.site.member_web_url"
        class="cta"
        :href="site.data.site.member_web_url"
        target="_blank"
        rel="noreferrer"
      >
        进入会员中心
      </a>
    </header>

    <p v-if="site.error" class="fail">暂时无法加载</p>
    <RouterView />

    <footer class="foot">
      <BrandMark compact />
      <nav class="foot-links">
        <RouterLink to="/space">SPACE</RouterLink>
        <RouterLink to="/fit">FIT</RouterLink>
        <RouterLink to="/bar">BAR</RouterLink>
        <RouterLink to="/news">新闻</RouterLink>
        <RouterLink to="/jobs">招聘</RouterLink>
        <RouterLink to="/partners">招商</RouterLink>
      </nav>
      <p class="place">{{ site.data?.contact.address || '回龙观公园' }}</p>
      <p class="meta">
        <a v-if="site.data?.contact.service_phone" :href="`tel:${site.data.contact.service_phone}`">
          {{ site.data.contact.service_phone }}
        </a>
        <span v-if="site.data?.contact.service_phone && site.data?.contact.business_hours">·</span>
        <span v-if="site.data?.contact.business_hours">{{ site.data.contact.business_hours }}</span>
      </p>
      <p class="legal">
        {{ copyrightLine() }}
        <template v-if="site.data?.site.icp_beian"> · {{ site.data.site.icp_beian }}</template>
      </p>
    </footer>
  </div>
</template>

<style scoped>
.shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}
.nav {
  display: flex;
  align-items: center;
  gap: 28px;
  padding: 16px 32px;
  border-bottom: 1px solid rgba(242, 230, 210, 0.08);
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(8, 9, 11, 0.92);
  backdrop-filter: blur(16px);
}
.nav.over {
  position: absolute;
  left: 0;
  right: 0;
  background: linear-gradient(180deg, rgba(8, 9, 11, 0.72), transparent);
  border-bottom: none;
  backdrop-filter: none;
}
.nav nav {
  display: flex;
  flex-wrap: wrap;
  gap: 18px;
  flex: 1;
  font-size: 14px;
  letter-spacing: 0.04em;
}
.nav nav a {
  color: var(--muted);
}
.nav nav a.router-link-active {
  color: var(--text);
}
.cta {
  background: var(--orange);
  color: #171b1f;
  padding: 8px 14px;
  border-radius: 999px;
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}
.fail {
  text-align: center;
  color: var(--muted);
  padding: 48px 16px;
}
.foot {
  margin-top: auto;
  padding: 56px 24px 40px;
  background: #08090b;
  border-top: 1px solid rgba(242, 230, 210, 0.08);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.foot-links {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 8px 22px;
  margin: 28px 0 0;
  font-size: 13px;
  letter-spacing: 0.12em;
}
.foot-links a {
  color: var(--muted);
}
.foot-links a.router-link-active {
  color: var(--text);
}
.place {
  margin: 28px 0 0;
  color: var(--text);
  font-size: 15px;
  letter-spacing: 0.06em;
}
.meta {
  margin: 10px 0 0;
  color: var(--muted);
  font-size: 14px;
}
.meta a {
  color: inherit;
}
.legal {
  margin: 28px 0 0;
  color: rgba(138, 145, 152, 0.75);
  font-size: 12px;
}
@media (max-width: 800px) {
  .nav {
    flex-wrap: wrap;
    padding: 12px 16px;
    gap: 12px;
  }
  .cta {
    margin-left: auto;
  }
  .foot {
    padding: 40px 20px 32px;
  }
}
</style>
