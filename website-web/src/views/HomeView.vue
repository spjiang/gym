<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import http from '../api/http'
import type { BrandBlock, BrandKey, NewsBrief, Page } from '../api/types'
import { COPYRIGHT_OWNER } from '../copyright'
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

function excerpt(brand: BrandBlock, n = 86) {
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
  return d.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

async function loadLists() {
  try {
    const [news, jobs, partners] = await Promise.all([
      http.get<Page<NewsBrief>>('/public/website/articles', { params: { channel: 'news', page: 1, page_size: 6 } }),
      http.get<Page<NewsBrief>>('/public/website/articles', { params: { channel: 'jobs', page: 1, page_size: 4 } }),
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
  <div>
    <section class="hero">
      <img v-if="site.data?.home.hero_image_url" :src="site.data.home.hero_image_url" alt="" />
      <div class="veil" />
      <div class="copy">
        <p class="kicker">{{ site.data?.site.display_name || '观野SPACE' }}</p>
        <h1>{{ site.data?.home.headline || '运动 · 夜生活 · 社区' }}</h1>
        <p class="sub">{{ site.data?.home.subheadline }}</p>
        <p class="lead">{{ site.data?.site.seo_description }}</p>
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

    <section class="facts">
      <div>
        <span>地址</span>
        <strong>{{ site.data?.contact.address || '回龙观公园' }}</strong>
      </div>
      <div>
        <span>电话</span>
        <strong>{{ site.data?.contact.service_phone || '见前台' }}</strong>
      </div>
      <div>
        <span>营业时间</span>
        <strong>{{ site.data?.contact.business_hours || '以当场公示为准' }}</strong>
      </div>
    </section>

    <section class="wrap">
      <div class="intro">
        <h2>一座园子，三种节奏</h2>
        <p>
          观野SPACE 把健身房、清吧和公共客厅放在回龙观公园里。你可以先训练、再坐一会儿，再决定是回家还是留下喝一杯。办卡、约课、点餐请走会员中心；官网只负责把场地讲清楚。平台由{{ COPYRIGHT_OWNER }}运营并享有版权。
        </p>
      </div>

      <ol class="rhythm">
        <li>
          <em>06:00</em>
          <strong>FIT 开训</strong>
          <span>力量区与团课，门禁走会籍或临访。</span>
        </li>
        <li>
          <em>白天</em>
          <strong>SPACE 客厅</strong>
          <span>中庭、草坪与市集，邻居可以只来坐坐。</span>
        </li>
        <li>
          <em>17:00</em>
          <strong>BAR 开档</strong>
          <span>简餐、特调与驻场，未成年人谢绝酒水。</span>
        </li>
      </ol>

      <div class="cards">
        <RouterLink v-for="b in brands" :key="b.key" class="card" :to="`/${b.key}`">
          <img v-if="b.cover_image_url" :src="b.cover_image_url" alt="" />
          <div v-else class="ph">{{ b.key.toUpperCase() }}</div>
          <div class="card-body">
            <span class="tag">{{ b.key.toUpperCase() }}</span>
            <strong>{{ b.title }}</strong>
            <p>{{ excerpt(b) }}</p>
            <em>了解更多</em>
          </div>
        </RouterLink>
      </div>
    </section>

    <section class="wrap">
      <div v-if="newsItems.length" class="block">
        <div class="head-row">
          <h2>新闻动态</h2>
          <RouterLink class="more" to="/news">全部新闻</RouterLink>
        </div>
        <div class="news-grid">
          <RouterLink v-for="n in newsItems" :key="n.id" class="news-card" :to="`/news/${n.id}`">
            <img v-if="n.cover_image_url" :src="n.cover_image_url" alt="" />
            <div>
              <small>{{ formatDay(n.published_at) }}</small>
              <strong>{{ n.title }}</strong>
              <span>{{ n.summary }}</span>
            </div>
          </RouterLink>
        </div>
      </div>

      <div class="split">
        <div v-if="jobItems.length">
          <div class="head-row">
            <h2>招聘</h2>
            <RouterLink class="more" to="/jobs">全部职位</RouterLink>
          </div>
          <RouterLink v-for="n in jobItems" :key="n.id" class="line" :to="`/jobs/${n.id}`">
            <strong>{{ n.title }}</strong>
            <span>{{ n.summary }}</span>
          </RouterLink>
        </div>
        <div v-if="partnerItems.length">
          <div class="head-row">
            <h2>招商</h2>
            <RouterLink class="more" to="/partners">入驻说明</RouterLink>
          </div>
          <RouterLink v-for="n in partnerItems" :key="n.id" class="line" :to="`/partners/${n.id}`">
            <strong>{{ n.title }}</strong>
            <span>{{ n.summary }}</span>
          </RouterLink>
        </div>
      </div>

      <div class="faq">
        <h2>到店前先看这几句</h2>
        <dl>
          <div>
            <dt>能直接在官网办卡吗？</dt>
            <dd>不能。访客只阅读。办卡、约课、点餐请进入会员中心或微信搜索「观野SPACE」。</dd>
          </div>
          <div>
            <dt>第一次来要预约吗？</dt>
            <dd>逛园区和中庭不用预约。器械区需会籍或临访；BAR 高峰可能等位。</dd>
          </div>
          <div>
            <dt>怎么应聘或谈铺位？</dt>
            <dd>官网不收集简历和意向表。请看招聘/招商页说明，到前台或致电页脚电话。</dd>
          </div>
          <div>
            <dt>地址和营业时间以谁为准？</dt>
            <dd>与综合管理平台「观野SPACE 介绍」同一套场地资料，见本页页脚。</dd>
          </div>
        </dl>
      </div>

      <div class="cta-band">
        <div>
          <h2>准备好进园了？</h2>
          <p>{{ site.data?.site.miniprogram_hint || '业务请走会员中心，不在官网留资。' }}</p>
        </div>
        <a
          v-if="site.data?.site.member_web_url"
          class="btn"
          :href="site.data.site.member_web_url"
          target="_blank"
          rel="noreferrer"
        >
          进入会员中心
        </a>
      </div>
    </section>
  </div>
</template>

<style scoped>
.hero {
  position: relative;
  min-height: 78vh;
  display: flex;
  align-items: flex-end;
  overflow: hidden;
  background: #1c2229;
}
.hero img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.veil {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(18, 21, 26, 0.12), rgba(18, 21, 26, 0.92));
}
.copy {
  position: relative;
  padding: 56px 28px 48px;
  max-width: 960px;
}
.kicker {
  letter-spacing: 0.28em;
  text-transform: uppercase;
  font-size: 12px;
  color: var(--cyan);
  margin: 0 0 8px;
}
h1 {
  margin: 0;
  font-size: clamp(32px, 5.4vw, 56px);
}
.sub {
  margin: 12px 0 0;
  color: var(--muted);
  letter-spacing: 0.12em;
  text-transform: uppercase;
  font-size: 13px;
}
.lead {
  margin: 16px 0 0;
  max-width: 42em;
  color: #d7cdc0;
  font-size: 16px;
}
.hero-actions,
.cta-band {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}
.hero-actions {
  margin-top: 24px;
}
.btn {
  background: var(--orange);
  color: #171b1f;
  padding: 10px 18px;
  border-radius: 999px;
  font-weight: 600;
  font-size: 14px;
}
.btn.ghost {
  background: transparent;
  color: var(--text);
  border: 1px solid var(--line);
}
.facts {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 1px;
  background: var(--line);
  border-bottom: 1px solid var(--line);
}
.facts div {
  background: var(--bg-2);
  padding: 18px 22px;
}
.facts span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  letter-spacing: 0.08em;
}
.facts strong {
  display: block;
  margin-top: 4px;
  font-weight: 600;
}
.wrap {
  padding: 48px 28px 72px;
  max-width: 1100px;
  margin: 0 auto;
}
.intro {
  max-width: 46em;
  margin-bottom: 36px;
}
.intro h2,
.block h2,
.split h2,
.faq h2,
.cta-band h2 {
  margin: 0 0 12px;
}
.intro p {
  margin: 0;
  color: #d7cdc0;
  font-size: 17px;
}
.rhythm {
  list-style: none;
  padding: 0;
  margin: 0 0 40px;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.rhythm li {
  border: 1px solid var(--line);
  background: var(--bg-2);
  padding: 18px 16px;
}
.rhythm em {
  font-style: normal;
  color: var(--orange);
  font-size: 13px;
}
.rhythm strong {
  display: block;
  margin: 6px 0 8px;
}
.rhythm span {
  color: var(--muted);
  font-size: 14px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.card {
  background: var(--bg-2);
  border: 1px solid var(--line);
  overflow: hidden;
}
.card img,
.ph {
  height: 220px;
  object-fit: cover;
  width: 100%;
}
.ph {
  display: grid;
  place-items: center;
  font-family: Montserrat, sans-serif;
  font-weight: 800;
  letter-spacing: 0.12em;
  background: #252b33;
  color: var(--muted);
}
.card-body {
  padding: 16px 16px 18px;
}
.tag {
  font-size: 11px;
  letter-spacing: 0.16em;
  color: var(--cyan);
}
.card-body strong {
  display: block;
  margin: 6px 0 8px;
  font-size: 18px;
}
.card-body p {
  margin: 0 0 12px;
  color: var(--muted);
  font-size: 14px;
  min-height: 3.2em;
}
.card-body em {
  font-style: normal;
  color: var(--orange);
  font-size: 13px;
}
.block {
  margin-bottom: 48px;
}
.head-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}
.head-row h2 {
  margin: 0;
}
.more {
  color: var(--orange);
  font-size: 14px;
}
.news-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.news-card {
  background: var(--bg-2);
  border: 1px solid var(--line);
  overflow: hidden;
}
.news-card img {
  height: 140px;
  width: 100%;
  object-fit: cover;
}
.news-card div {
  padding: 14px 14px 16px;
}
.news-card small {
  color: var(--cyan);
  font-size: 12px;
}
.news-card strong {
  display: block;
  margin: 6px 0 8px;
}
.news-card span {
  color: var(--muted);
  font-size: 13px;
}
.split {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 28px;
  margin-bottom: 48px;
}
.line {
  display: block;
  padding: 14px 0;
  border-top: 1px solid var(--line);
}
.line span {
  display: block;
  color: var(--muted);
  font-size: 13px;
  margin-top: 4px;
}
.faq dl {
  margin: 0;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.faq div {
  border: 1px solid var(--line);
  padding: 16px 16px 18px;
  background: var(--bg-2);
}
.faq dt {
  font-weight: 600;
  margin-bottom: 8px;
}
.faq dd {
  margin: 0;
  color: var(--muted);
  font-size: 14px;
}
.cta-band {
  margin-top: 48px;
  padding: 28px 24px;
  border: 1px solid var(--line);
  background: #1c2229;
  justify-content: space-between;
}
.cta-band p {
  margin: 0;
  color: var(--muted);
}
@media (max-width: 900px) {
  .facts,
  .rhythm,
  .cards,
  .news-grid,
  .split,
  .faq dl {
    grid-template-columns: 1fr 1fr;
  }
}
@media (max-width: 640px) {
  .hero {
    min-height: 70vh;
  }
  .facts,
  .rhythm,
  .cards,
  .news-grid,
  .split,
  .faq dl {
    grid-template-columns: 1fr;
  }
  .card img,
  .ph {
    height: 180px;
  }
}
</style>
