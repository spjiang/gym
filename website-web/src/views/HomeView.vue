<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import http from '../api/http'
import type { BrandBlock, BrandKey, NewsBrief, Page } from '../api/types'
import HeroCarousel from '../components/HeroCarousel.vue'
import { useSiteStore } from '../stores/site'

const site = useSiteStore()
const newsItems = ref<NewsBrief[]>([])
const jobItems = ref<NewsBrief[]>([])
const partnerItems = ref<NewsBrief[]>([])

const brands = computed(() => {
  const d = site.data
  if (!d) return []
  const keys: BrandKey[] = []
  if (d.home.show_space) keys.push('space')
  if (d.home.show_fit) keys.push('fit')
  if (d.home.show_bar) keys.push('bar')
  return keys.map((k) => d.brands[k])
})

const slideUrls = computed(() => {
  const d = site.data
  if (!d) return []
  const urls: string[] = []
  const add = (url?: string | null) => {
    if (url && !urls.includes(url)) urls.push(url)
  }
  add(d.home.hero_image_url)
  for (const brand of brands.value) {
    add(brand.cover_image_url)
    add(brand.gallery_image_urls[0])
  }
  return urls.slice(0, 6)
})

function excerpt(brand: BrandBlock, n = 88) {
  const line = (brand.body || '')
    .split('\n')
    .map((s) => s.replace(/^#+\s*/, '').replace(/[*_`]/g, '').trim())
    .find((s) => s.length > 12)
  return (line || '').slice(0, n)
}

function formatDay(iso: string | null) {
  if (!iso) return ''
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return d.toLocaleDateString('zh-CN', { year: 'numeric', month: 'short', day: 'numeric' })
}

async function loadLists() {
  try {
    const [news, jobs, partners] = await Promise.all([
      http.get<Page<NewsBrief>>('/public/website/articles', { params: { channel: 'news', page: 1, page_size: 4 } }),
      http.get<Page<NewsBrief>>('/public/website/articles', { params: { channel: 'jobs', page: 1, page_size: 3 } }),
      http.get<Page<NewsBrief>>('/public/website/articles', { params: { channel: 'partners', page: 1, page_size: 3 } }),
    ])
    newsItems.value = news.data.items
    jobItems.value = jobs.data.items
    partnerItems.value = partners.data.items
  } catch {
    newsItems.value = site.data?.latest_news || []
  }
}

onMounted(() => {
  void loadLists()
})
</script>

<template>
  <div class="home">
    <section class="hero">
      <HeroCarousel :urls="slideUrls" />
      <div class="hero-copy">
        <p class="kicker">{{ site.data?.site.display_name || '晨曦观野SPACE' }}</p>
        <h1>{{ site.data?.home.headline || '运动 · 夜生活 · 社区' }}</h1>
        <p v-if="site.data?.home.subheadline" class="sub">{{ site.data.home.subheadline }}</p>
        <div class="hero-actions">
          <a
            v-if="site.data?.site.member_web_url"
            class="btn"
            :href="site.data.site.member_web_url"
            target="_blank"
            rel="noreferrer"
          >
            进入会员中心
          </a>
          <RouterLink class="btn ghost" to="/space">了解园区</RouterLink>
        </div>
      </div>
    </section>

    <section class="band">
      <div class="inner">
        <p class="eyebrow">PARK · SPACE · COMMUNITY</p>
        <h2>一座园子，三种节奏</h2>
        <p class="lead">{{ site.data?.site.seo_description }}</p>
        <div class="houses">
          <RouterLink v-for="b in brands" :key="b.key" class="house" :to="`/${b.key}`">
            <span class="tag">{{ b.key.toUpperCase() }}</span>
            <strong>{{ b.title }}</strong>
            <p>{{ excerpt(b) }}</p>
          </RouterLink>
        </div>
      </div>
    </section>

    <section v-if="newsItems.length || jobItems.length || partnerItems.length" class="band">
      <div class="inner lists">
        <div v-if="newsItems.length">
          <div class="head-row">
            <h2>新闻动态</h2>
            <RouterLink class="more" to="/news">全部</RouterLink>
          </div>
          <RouterLink v-for="n in newsItems" :key="n.id" class="line" :to="`/news/${n.id}`">
            <small>{{ formatDay(n.published_at) }}</small>
            <strong>{{ n.title }}</strong>
          </RouterLink>
        </div>
        <div v-if="jobItems.length">
          <div class="head-row">
            <h2>招聘</h2>
            <RouterLink class="more" to="/jobs">全部</RouterLink>
          </div>
          <RouterLink v-for="n in jobItems" :key="n.id" class="line" :to="`/jobs/${n.id}`">
            <strong>{{ n.title }}</strong>
          </RouterLink>
        </div>
        <div v-if="partnerItems.length">
          <div class="head-row">
            <h2>招商</h2>
            <RouterLink class="more" to="/partners">全部</RouterLink>
          </div>
          <RouterLink v-for="n in partnerItems" :key="n.id" class="line" :to="`/partners/${n.id}`">
            <strong>{{ n.title }}</strong>
          </RouterLink>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.home {
  background: #0c0e11;
}
.hero {
  position: relative;
}
.hero-copy {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 4;
  padding: 0 48px 88px;
  background: linear-gradient(180deg, transparent, rgba(5, 6, 7, 0.82) 55%);
  pointer-events: none;
}
.hero-copy > * {
  pointer-events: auto;
}
.kicker,
.eyebrow {
  margin: 0 0 12px;
  font-family: Montserrat, sans-serif;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.34em;
  text-transform: uppercase;
  color: var(--cyan);
}
.eyebrow {
  color: rgba(242, 230, 210, 0.42);
}
h1 {
  margin: 0;
  max-width: 12em;
  font-size: clamp(32px, 4.4vw, 60px);
  font-weight: 600;
  line-height: 1.18;
}
.sub {
  margin: 14px 0 0;
  color: rgba(242, 230, 210, 0.55);
  letter-spacing: 0.22em;
  text-transform: uppercase;
  font-size: 12px;
  font-family: Montserrat, sans-serif;
}
.hero-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-top: 28px;
}
.btn {
  background: var(--orange);
  color: #171b1f;
  padding: 12px 22px;
  border-radius: 999px;
  font-weight: 600;
  font-size: 14px;
}
.btn.ghost {
  background: transparent;
  color: var(--text);
  border: 1px solid rgba(242, 230, 210, 0.28);
}
.band {
  padding: 72px 48px;
  border-top: 1px solid rgba(242, 230, 210, 0.08);
}
.inner {
  width: 100%;
}
.lead {
  margin: 0 0 40px;
  max-width: 36em;
  color: #d7cdc0;
  font-size: 17px;
  line-height: 1.8;
}
h2 {
  margin: 0 0 16px;
  font-size: 28px;
  font-weight: 600;
}
.houses {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
}
.house {
  padding: 24px 22px 28px;
  background: #14181e;
  border: 1px solid rgba(242, 230, 210, 0.08);
}
.tag {
  font-size: 11px;
  letter-spacing: 0.2em;
  color: var(--cyan);
  font-family: Montserrat, sans-serif;
}
.house strong {
  display: block;
  margin: 8px 0 10px;
  font-size: 20px;
}
.house p {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
  line-height: 1.7;
}
.lists {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 40px;
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 8px;
}
.head-row h2 {
  margin: 0;
  font-size: 22px;
}
.more {
  color: var(--orange);
  font-size: 13px;
}
.line {
  display: block;
  padding: 14px 0;
  border-top: 1px solid rgba(242, 230, 210, 0.08);
}
.line:first-of-type {
  border-top: none;
}
.line small {
  display: block;
  color: var(--cyan);
  font-size: 12px;
  margin-bottom: 4px;
}
.line strong {
  font-size: 16px;
  font-weight: 600;
}
@media (max-width: 900px) {
  .houses,
  .lists {
    grid-template-columns: 1fr;
  }
  .hero-copy {
    padding: 0 20px 56px;
  }
  .band {
    padding: 48px 20px;
  }
}
</style>
