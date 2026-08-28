<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '../api/http'
import { pathForMerchant, useAuthStore, type MemberMerchant } from '../stores/auth'
import BrandMark from '../components/BrandMark.vue'
import { copyrightLine } from '../copyright'

type SiteProfile = {
  id: number
  name: string
  tagline: string | null
  description: string | null
  address: string | null
  service_phone: string | null
  business_hours: string | null
  cover_image_url: string | null
  banner_image_urls: string[]
  gallery_image_urls: string[]
}

type Section = {
  key: string
  title: string
  subtitle: string
  items: MemberMerchant[]
}

const auth = useAuthStore()
const router = useRouter()
const site = ref<SiteProfile | null>(null)
const slide = ref(0)
let timer: number | null = null

function maskPhone(phone?: string) {
  if (!phone || phone.length < 7) return phone || ''
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`
}

function systemOf(m: MemberMerchant) {
  return m.primary_system || m.subsystem_codes[0] || 'other'
}

const slides = computed(() => {
  const banners = site.value?.banner_image_urls || []
  if (banners.length) return banners
  if (site.value?.cover_image_url) return [site.value.cover_image_url]
  return []
})

const sections = computed<Section[]>(() => {
  const list = auth.me?.merchants || []
  const buckets: Record<string, MemberMerchant[]> = { gym: [], catering: [], other: [] }
  for (const m of list) {
    const sys = systemOf(m)
    if (sys === 'gym' || sys === 'catering') buckets[sys].push(m)
    else buckets.other.push(m)
  }
  const out: Section[] = []
  if (buckets.gym.length) {
    out.push({ key: 'gym', title: '观野FIT', subtitle: '会籍 · 团课 · 商城 · 通行', items: buckets.gym })
  }
  if (buckets.catering.length) {
    out.push({ key: 'catering', title: '观野BAR', subtitle: '点餐 · 取餐号 · 订单', items: buckets.catering })
  }
  if (buckets.other.length) {
    out.push({ key: 'other', title: '其它门店', subtitle: '进入查看可用服务', items: buckets.other })
  }
  return out
})

function enter(m: MemberMerchant) {
  auth.setMerchantId(m.id)
  router.push(pathForMerchant(m))
}

function goMe() {
  router.push({ name: 'me' })
}

function nextSlide() {
  if (slides.value.length < 2) return
  slide.value = (slide.value + 1) % slides.value.length
}

onMounted(async () => {
  try {
    const { data } = await http.get<SiteProfile>('/member/site')
    site.value = data
  } catch {
    site.value = null
  }
  timer = window.setInterval(nextSlide, 5000)
})
onUnmounted(() => {
  if (timer != null) window.clearInterval(timer)
})
</script>

<template>
  <section class="portal">
    <header class="hero">
      <div class="hero__media" aria-hidden="true">
        <img v-if="slides.length" :src="slides[slide]" alt="" />
        <div v-else class="hero__fallback" />
        <div class="hero__veil" />
      </div>
      <div class="hero__bar">
        <BrandMark variant="space" compact />
        <button class="mw-btn mw-btn--ghost mw-btn--sm" type="button" @click="goMe">我的</button>
      </div>
      <div class="hero__copy">
        <p class="hero__kicker">{{ site?.name || '观野SPACE' }}</p>
        <h1>你好，{{ auth.me?.name }}</h1>
        <p class="hero__tag">{{ site?.tagline || '选择门店，进入对应业态' }}</p>
      </div>
      <div v-if="slides.length > 1" class="hero__dots">
        <button
          v-for="(_, i) in slides"
          :key="i"
          type="button"
          class="dot"
          :class="{ 'dot--on': slide === i }"
          :aria-label="`第 ${i + 1} 张`"
          @click="slide = i"
        />
      </div>
    </header>

    <div class="body">
      <div class="facts">
        <a v-if="site?.service_phone" class="fact" :href="`tel:${site.service_phone}`">
          <span class="fact__k">客服</span>
          <span>{{ site.service_phone }}</span>
        </a>
        <div v-if="site?.business_hours" class="fact">
          <span class="fact__k">营业</span>
          <span>{{ site.business_hours }}</span>
        </div>
        <div v-if="site?.address" class="fact fact--wide">
          <span class="fact__k">地址</span>
          <span>{{ site.address }}</span>
        </div>
        <button class="fact" type="button" @click="goMe">
          <span class="fact__k">会员</span>
          <span>{{ maskPhone(auth.me?.phone) }}</span>
        </button>
      </div>

      <div v-if="!sections.length" class="mw-empty">暂无可用门店，请联系门店开通业态。</div>

      <section v-for="sec in sections" :key="sec.key" class="brands">
        <div class="sec-head">
          <h2>入驻品牌 · {{ sec.title }}</h2>
          <p>{{ sec.subtitle }}</p>
        </div>
        <button
          v-for="m in sec.items"
          :key="m.id"
          type="button"
          class="brand"
          :class="`brand--${sec.key}`"
          @click="enter(m)"
        >
          <div class="brand__visual">
            <img v-if="m.cover_image_url" :src="m.cover_image_url" alt="" />
            <div v-else class="brand__wash">
              <span class="brand__mark">{{ sec.key === 'catering' ? 'BAR' : sec.key === 'gym' ? 'FIT' : 'STORE' }}</span>
            </div>
          </div>
          <div class="brand__body">
            <div class="brand__top">
              <span class="brand__badge">{{ sec.title }}</span>
              <span class="brand__go">进入</span>
            </div>
            <div class="brand__name">{{ m.name }}</div>
            <div class="brand__hint">{{ m.tagline || (sec.key === 'gym' ? '训练即生活' : sec.key === 'catering' ? '夜色刚刚开始' : sec.subtitle) }}</div>
          </div>
        </button>
      </section>

      <section v-if="site?.description || site?.gallery_image_urls?.length" class="about">
        <div class="sec-head">
          <h2>场地介绍</h2>
          <p>{{ site?.name }}</p>
        </div>
        <p v-if="site?.description" class="about__text">{{ site.description }}</p>
        <div v-if="site?.gallery_image_urls?.length" class="gallery">
          <img v-for="(url, i) in site.gallery_image_urls" :key="i" :src="url" alt="" />
        </div>
      </section>

      <p class="tip">进入后可随时点顶栏「切换」回到本页</p>
      <p class="tip">{{ copyrightLine() }}</p>
    </div>
  </section>
</template>

<style scoped>
.portal {
  max-width: var(--mw-shell-max);
  margin: 0 auto;
  min-height: 100vh;
  background: var(--mw-bg);
}

.hero {
  position: relative;
  min-height: 280px;
  padding: 14px 16px 28px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  overflow: hidden;
}

.hero__media,
.hero__media img,
.hero__fallback,
.hero__veil {
  position: absolute;
  inset: 0;
}

.hero__media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.hero__fallback {
  background:
    radial-gradient(ellipse 80% 70% at 18% 20%, rgba(243, 107, 33, 0.28), transparent 55%),
    radial-gradient(ellipse 60% 50% at 90% 10%, rgba(20, 184, 212, 0.22), transparent 50%),
    linear-gradient(160deg, #1a1510 0%, #171b1f 55%, #101418 100%);
}

.hero__veil {
  background: linear-gradient(180deg, rgba(23, 27, 31, 0.18) 0%, rgba(23, 27, 31, 0.55) 45%, rgba(23, 27, 31, 0.96) 100%);
}

.hero__bar,
.hero__copy,
.hero__dots {
  position: relative;
  z-index: 1;
}

.hero__bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.hero__kicker {
  margin: 0 0 6px;
  font-size: 11px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: var(--mw-brand);
  font-weight: 700;
}

.hero__copy h1 {
  margin: 0;
  font-size: 26px;
  letter-spacing: -0.03em;
}

.hero__tag {
  margin: 8px 0 0;
  font-size: 14px;
  color: var(--mw-text-secondary);
}

.hero__dots {
  display: flex;
  gap: 6px;
  margin-top: 16px;
}

.dot {
  width: 7px;
  height: 7px;
  min-height: 7px;
  padding: 0;
  border-radius: 99px;
  border: 0;
  background: rgba(242, 230, 210, 0.28);
}

.dot--on {
  width: 18px;
  background: var(--mw-brand);
}

.body {
  padding: 0 16px 40px;
}

.facts {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin: -8px 0 20px;
}

.fact {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-height: 58px;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid var(--mw-border);
  background: var(--mw-surface);
  color: inherit;
  text-decoration: none;
  font: inherit;
  text-align: left;
}

.fact--wide {
  grid-column: 1 / -1;
}

.fact__k {
  font-size: 11px;
  color: var(--mw-text-tertiary);
  letter-spacing: 0.06em;
}

.sec-head {
  margin: 8px 0 12px;
}

.sec-head h2 {
  margin: 0;
  font-size: 15px;
}

.sec-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--mw-text-secondary);
}

.brand {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  width: 100%;
  min-height: 0;
  margin: 0 0 12px;
  padding: 0;
  overflow: hidden;
  border: 1px solid rgba(243, 107, 33, 0.28);
  border-radius: 12px;
  background: #2a1c14;
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.brand--catering {
  border-color: rgba(20, 184, 212, 0.32);
  background: #142428;
}

.brand--other {
  border-color: var(--mw-border);
  background: var(--mw-surface);
}

.brand__visual {
  position: relative;
  width: 100%;
  height: 168px;
  flex-shrink: 0;
  overflow: hidden;
}

.brand__wash {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  background:
    radial-gradient(ellipse 90% 80% at 12% 20%, rgba(255, 186, 120, 0.45), transparent 55%),
    radial-gradient(ellipse 70% 60% at 92% 88%, rgba(243, 107, 33, 0.55), transparent 50%),
    linear-gradient(145deg, #f36b21 0%, #c45a1c 42%, #7a3010 100%);
}

.brand--catering .brand__wash {
  background:
    radial-gradient(ellipse 90% 80% at 12% 18%, rgba(125, 232, 245, 0.42), transparent 55%),
    radial-gradient(ellipse 70% 60% at 90% 90%, rgba(20, 184, 212, 0.5), transparent 50%),
    linear-gradient(145deg, #2dd4bf 0%, #0f8f9a 45%, #134e4a 100%);
}

.brand--other .brand__wash {
  background: linear-gradient(145deg, #4a525a, #2a3138);
}

.brand__mark {
  font-family: Montserrat, Arial, sans-serif;
  font-size: 52px;
  font-weight: 800;
  letter-spacing: 0.14em;
  color: rgba(255, 247, 236, 0.94);
  text-shadow: 0 8px 24px rgba(0, 0, 0, 0.28);
}

.brand__visual img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.brand__body {
  padding: 14px 16px 16px;
  background: linear-gradient(180deg, rgba(243, 107, 33, 0.16), rgba(42, 28, 20, 0.92));
}

.brand--catering .brand__body {
  background: linear-gradient(180deg, rgba(20, 184, 212, 0.16), rgba(20, 36, 40, 0.92));
}

.brand--other .brand__body {
  background: var(--mw-surface);
}

.brand__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.brand__badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--mw-brand-muted);
  color: var(--mw-brand);
}

.brand--catering .brand__badge {
  background: rgba(20, 184, 212, 0.14);
  color: #14b8d4;
}

.brand__go {
  font-size: 12px;
  font-weight: 700;
  color: var(--mw-brand);
}

.brand--catering .brand__go {
  color: #14b8d4;
}

.brand__name {
  margin-top: 6px;
  font-size: 17px;
  font-weight: 700;
}

.brand__hint {
  margin-top: 2px;
  font-size: 12px;
  color: var(--mw-text-secondary);
}

.about {
  margin-top: 8px;
}

.about__text {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--mw-text-secondary);
}

.gallery {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: none;
}

.gallery::-webkit-scrollbar {
  display: none;
}

.gallery img {
  width: 168px;
  height: 112px;
  object-fit: cover;
  border-radius: 10px;
  flex-shrink: 0;
  border: 1px solid var(--mw-border);
}

.tip {
  margin: 20px 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--mw-text-tertiary);
}
</style>
