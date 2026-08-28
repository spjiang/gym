<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView } from 'vue-router'
import BrandMark from '../components/BrandMark.vue'
import { copyrightLine } from '../copyright'
import { useSiteStore } from '../stores/site'

const site = useSiteStore()

onMounted(() => {
  void site.load()
})
</script>

<template>
  <div class="shell">
    <header class="nav">
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
      <div class="cols">
        <div>
          <p class="name">{{ site.data?.site.display_name || '观野SPACE' }}</p>
          <p v-if="site.data?.contact.address">{{ site.data.contact.address }}</p>
          <p>
            <span v-if="site.data?.contact.service_phone">{{ site.data.contact.service_phone }}</span>
            <span v-if="site.data?.contact.business_hours"> · {{ site.data.contact.business_hours }}</span>
          </p>
        </div>
        <div>
          <p>品牌</p>
          <RouterLink to="/space">观野SPACE</RouterLink>
          <RouterLink to="/fit">观野FIT</RouterLink>
          <RouterLink to="/bar">观野BAR</RouterLink>
        </div>
        <div>
          <p>资讯</p>
          <RouterLink to="/news">新闻动态</RouterLink>
          <RouterLink to="/jobs">招聘信息</RouterLink>
          <RouterLink to="/partners">招商入驻</RouterLink>
        </div>
      </div>
      <p v-if="site.data?.site.miniprogram_hint" class="hint">{{ site.data.site.miniprogram_hint }}</p>
      <p v-if="site.data?.site.footer_note" class="hint">{{ site.data.site.footer_note }}</p>
      <p class="copy">{{ copyrightLine() }} 版权所有</p>
      <p v-if="site.data?.site.icp_beian" class="hint">{{ site.data.site.icp_beian }}</p>
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
  gap: 24px;
  padding: 16px 28px;
  border-bottom: 1px solid var(--line);
  position: sticky;
  top: 0;
  z-index: 10;
  background: rgba(18, 21, 26, 0.92);
  backdrop-filter: blur(10px);
}
.nav nav {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
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
  padding: 40px 28px 48px;
  border-top: 1px solid var(--line);
  color: var(--muted);
  font-size: 13px;
}
.cols {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 24px;
  margin-bottom: 20px;
}
.cols p {
  margin: 0 0 8px;
}
.name {
  color: var(--text);
  font-size: 16px;
}
.cols a {
  display: block;
  margin: 0 0 6px;
  color: var(--muted);
}
.hint {
  opacity: 0.8;
  margin: 0 0 6px;
}
.copy {
  margin: 12px 0 4px;
  color: var(--text);
}
@media (max-width: 800px) {
  .nav {
    flex-wrap: wrap;
    padding: 12px 16px;
  }
  .cta {
    width: 100%;
    text-align: center;
  }
  .cols {
    grid-template-columns: 1fr;
  }
}
</style>
