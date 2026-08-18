<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import http from '../api/http'
import { payMemberOrder } from '../api/pay'
import { useAuthStore } from '../stores/auth'

type Store = {
  id: number
  name: string
  tagline: string | null
  description: string | null
  business_hours: string | null
  contact_phone: string | null
  business_address: string | null
  cover_image_url: string | null
  gallery_image_urls: string[]
}

type Coach = {
  id: number
  display_name: string
  title: string | null
  specialties: string | null
  avatar_url: string | null
}

type Membership = {
  id: number
  name: string
  price: string
  effective_price?: string | null
  duration_days: number | null
  session_count: number | null
  is_trial: boolean
}

type PtPackage = {
  id: number
  name: string
  price: string
  effective_price?: string | null
  session_count: number
  valid_days: number
}

type Session = {
  id: number
  course_name: string
  starts_at: string
  ends_at: string
  remaining: number
  capacity: number
  coach_name: string | null
  coach_id: number
}

type Activity = {
  id: number
  name: string
  category: string | null
  cover_url: string | null
  starts_at: string
  remaining_capacity: number | null
  capacity: number
  price: string
}

type Home = {
  merchant: Store
  coaches: Coach[]
  memberships: Membership[]
  pt_packages: PtPackage[]
  sessions: Session[]
  activities: Activity[]
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const mid = computed(() => Number(route.params.merchantId) || auth.merchantId)
const home = ref<Home | null>(null)
const err = ref('')
const msg = ref('')
const loading = ref(true)
const busyId = ref<number | null>(null)

const store = computed(() => home.value?.merchant || null)

function money(raw?: string | null) {
  if (raw == null || raw === '') return '—'
  const n = Number(raw)
  if (Number.isNaN(n)) return raw
  return Number.isInteger(n) ? String(n) : n.toFixed(2)
}

function sellPrice(p: { price: string; effective_price?: string | null }) {
  return money(p.effective_price || p.price)
}

function fmt(iso?: string | null) {
  if (!iso) return '—'
  return iso.slice(0, 16).replace('T', ' ')
}

function cardMeta(p: Membership) {
  if (p.duration_days) return `${p.duration_days} 天`
  if (p.session_count) return `${p.session_count} 次`
  return p.is_trial ? '体验卡' : '会籍'
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await http.get<Home>('/member/home', { params: { merchant_id: mid.value } })
    home.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
    home.value = null
  } finally {
    loading.value = false
  }
}

async function buyCard(productId: number) {
  msg.value = ''
  err.value = ''
  busyId.value = productId
  try {
    const { data: order } = await http.post('/member/orders/membership', {
      merchant_id: mid.value,
      product_id: productId,
    })
    const paid = await payMemberOrder(order.id)
    msg.value = `购卡成功，实付 ¥${paid.amount || order.amount}`
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '购买失败'
  } finally {
    busyId.value = null
  }
}

async function buyPt(productId: number) {
  msg.value = ''
  err.value = ''
  busyId.value = productId
  try {
    const { data: order } = await http.post('/member/orders/pt-package', {
      merchant_id: mid.value,
      product_id: productId,
    })
    const paid = await payMemberOrder(order.id)
    msg.value = `购买成功，实付 ¥${paid.amount || order.amount}`
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '购买失败'
  } finally {
    busyId.value = null
  }
}

function goCoach(id: number) {
  router.push(`/m/${mid.value}/gym/coaches/${id}`)
}

onMounted(load)
</script>

<template>
  <section class="home">
    <div class="hero" :class="{ 'hero--photo': !!store?.cover_image_url }">
      <img v-if="store?.cover_image_url" class="hero__cover" :src="store.cover_image_url" alt="" />
      <div class="hero__wash" />
      <div class="hero__mark">FIT</div>
      <div class="hero__bars" aria-hidden="true">
        <span class="hero__bar hero__bar--orange" />
        <span class="hero__bar hero__bar--cyan" />
      </div>
      <div class="hero__copy">
        <p class="hero__kicker">{{ store?.tagline || '训练即生活' }}</p>
        <h1>{{ store?.name || auth.currentMerchant?.name || '观野FIT' }}</h1>
        <p class="hero__meta">
          <template v-if="store?.business_hours">{{ store.business_hours }}</template>
          <template v-if="store?.business_address">
            <template v-if="store.business_hours"> · </template>{{ store.business_address }}
          </template>
        </p>
      </div>
    </div>

    <p v-if="loading" class="mw-page__desc">加载中…</p>
    <p v-else-if="err && !home" class="mw-msg mw-msg--error">{{ err }}</p>

    <template v-else>
      <p v-if="msg" class="mw-msg mw-msg--ok">{{ msg }}</p>
      <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

      <div class="quick">
        <RouterLink class="quick__item" :to="`/m/${mid}/gym/classes`">
          <span>团课</span>
          <small>立即预约</small>
        </RouterLink>
        <RouterLink class="quick__item" :to="`/m/${mid}/gym/shop`">
          <span>购卡</span>
          <small>会籍课包</small>
        </RouterLink>
        <RouterLink class="quick__item" :to="`/m/${mid}/gym/activities`">
          <span>活动</span>
          <small>报名参与</small>
        </RouterLink>
        <RouterLink class="quick__item" :to="`/m/${mid}/gym/coupons`">
          <span>卡券</span>
          <small>领优惠</small>
        </RouterLink>
      </div>

      <section class="block">
        <div class="block__head">
          <h2>活动报名</h2>
          <RouterLink class="more" :to="`/m/${mid}/gym/activities`">全部活动 ›</RouterLink>
        </div>
        <button
          v-for="a in home?.activities || []"
          :key="a.id"
          class="promo"
          type="button"
          @click="router.push(`/m/${mid}/gym/activities/${a.id}`)"
        >
          <div class="promo__cover">
            <img v-if="a.cover_url" :src="a.cover_url" alt="" />
            <span v-else class="promo__mark">FIT</span>
          </div>
          <div class="promo__copy">
            <small>{{ a.category || '活动' }}</small>
            <strong>{{ a.name }}</strong>
            <span>
              {{ fmt(a.starts_at) }}
              <template v-if="a.capacity > 0 && a.remaining_capacity != null"> · 余 {{ a.remaining_capacity }}</template>
            </span>
          </div>
        </button>
        <p v-if="!home?.activities?.length" class="mw-empty">暂无可报活动，后台发布后会出现在这里</p>
      </section>

      <section class="block">
        <div class="block__head">
          <h2>场馆介绍</h2>
        </div>
        <p class="intro">{{ store?.description || '力量训练、团课与私教，一站完成你的每一次到店。' }}</p>
        <p v-if="store?.contact_phone" class="intro-meta">咨询 {{ store.contact_phone }}</p>
        <div v-if="store?.gallery_image_urls.length" class="gallery">
          <img v-for="url in store.gallery_image_urls" :key="url" :src="url" alt="" />
        </div>
      </section>

      <section id="home-coaches" class="block">
        <div class="block__head">
          <h2>教练团队</h2>
        </div>
        <div v-if="home?.coaches.length" class="coaches">
          <button
            v-for="c in home.coaches"
            :key="c.id"
            class="coach"
            type="button"
            @click="goCoach(c.id)"
          >
            <div class="coach__avatar">
              <img v-if="c.avatar_url" :src="c.avatar_url" alt="" />
              <span v-else>{{ c.display_name.slice(0, 1) }}</span>
            </div>
            <strong>{{ c.display_name }}</strong>
            <small>{{ c.title || c.specialties || '教练' }}</small>
          </button>
        </div>
        <p v-else class="mw-empty">教练档案即将上线</p>
      </section>

      <section class="block">
        <div class="block__head">
          <h2>会籍卡种</h2>
          <RouterLink class="more" :to="`/m/${mid}/gym/shop`">更多套餐 ›</RouterLink>
        </div>
        <div v-if="home?.memberships.length" class="packs">
          <article v-for="p in home.memberships" :key="p.id" class="pack">
            <div class="pack__name">{{ p.name }}</div>
            <div class="pack__meta">{{ cardMeta(p) }}</div>
            <div class="pack__price">¥ {{ sellPrice(p) }}</div>
            <button
              class="pack__buy"
              type="button"
              :disabled="busyId === p.id"
              @click="buyCard(p.id)"
            >
              {{ busyId === p.id ? '支付中' : '立即购买' }}
            </button>
          </article>
        </div>
        <p v-else class="mw-empty">暂无可售会籍</p>
      </section>

      <section class="block">
        <div class="block__head">
          <h2>私教课包</h2>
          <RouterLink class="more" :to="`/m/${mid}/gym/shop`">全部课包 ›</RouterLink>
        </div>
        <div v-if="home?.pt_packages.length" class="packs">
          <article v-for="p in home.pt_packages" :key="p.id" class="pack pack--pt">
            <div class="pack__name">{{ p.name }}</div>
            <div class="pack__meta">{{ p.session_count }} 次 · {{ p.valid_days }} 天</div>
            <div class="pack__price">¥ {{ sellPrice(p) }}</div>
            <button
              class="pack__buy"
              type="button"
              :disabled="busyId === p.id"
              @click="buyPt(p.id)"
            >
              {{ busyId === p.id ? '支付中' : '立即购买' }}
            </button>
          </article>
        </div>
        <p v-else class="mw-empty">暂无私教课包</p>
      </section>

      <section class="block">
        <div class="block__head">
          <h2>可约团课</h2>
          <RouterLink class="more" :to="`/m/${mid}/gym/classes`">全部场次 ›</RouterLink>
        </div>
        <button
          v-for="s in home?.sessions || []"
          :key="s.id"
          class="session"
          type="button"
          @click="router.push(`/m/${mid}/gym/classes/${s.id}`)"
        >
          <div>
            <div class="session__name">{{ s.course_name }}</div>
            <div class="session__meta">
              {{ fmt(s.starts_at) }}
              <template v-if="s.coach_name"> · {{ s.coach_name }}</template>
            </div>
          </div>
          <strong>余 {{ s.remaining }}</strong>
        </button>
        <p v-if="!home?.sessions.length" class="mw-empty">暂无可约场次</p>
      </section>
    </template>
  </section>
</template>

<style scoped>
.home {
  margin: calc(-1 * var(--mw-space-4));
  padding: 0 var(--mw-space-4) var(--mw-space-4);
}

.hero {
  position: relative;
  overflow: hidden;
  min-height: 220px;
  margin: 0 calc(-1 * var(--mw-space-4)) var(--mw-space-4);
  padding: 28px var(--mw-space-4) 22px;
  background:
    radial-gradient(120% 90% at 88% 8%, rgba(243, 107, 33, 0.38), transparent 52%),
    radial-gradient(90% 80% at 0% 100%, rgba(20, 184, 212, 0.18), transparent 46%),
    linear-gradient(165deg, #1c2228 0%, #14181c 58%, #101317 100%);
  color: var(--mw-text);
}

.hero__cover {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.hero__wash {
  position: absolute;
  inset: 0;
  background: linear-gradient(180deg, rgba(16, 19, 23, 0.28) 0%, rgba(16, 19, 23, 0.82) 100%);
}

.hero--photo .hero__wash {
  background: linear-gradient(180deg, rgba(16, 19, 23, 0.2) 10%, rgba(16, 19, 23, 0.88) 100%);
}

.hero__mark {
  position: absolute;
  right: -8px;
  top: 8px;
  font-family: Montserrat, Arial, sans-serif;
  font-size: 92px;
  font-weight: 800;
  letter-spacing: -0.06em;
  color: rgba(242, 230, 210, 0.08);
  line-height: 1;
  pointer-events: none;
}

.hero__bars {
  position: relative;
  display: flex;
  align-items: flex-end;
  width: 140px;
  margin-bottom: 18px;
}

.hero__bar {
  display: block;
  height: 5px;
}

.hero__bar--orange {
  width: 64%;
  background: var(--mw-brand);
}

.hero__bar--cyan {
  width: 36%;
  height: 3px;
  background: var(--mw-cyan);
}

.hero__copy {
  position: relative;
}

.hero__kicker {
  margin: 0 0 6px;
  font-size: 12px;
  letter-spacing: 0.22em;
  text-transform: uppercase;
  color: var(--mw-brand);
  font-weight: 700;
}

.hero h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.hero__meta {
  margin: 8px 0 0;
  font-size: 12px;
  color: rgba(242, 230, 210, 0.72);
}

.quick {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: var(--mw-space-5);
}

.quick__item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 6px;
  border-radius: var(--mw-radius-md);
  background: var(--mw-surface);
  border: 1px solid var(--mw-border);
  color: inherit;
  text-decoration: none;
  text-align: center;
}

.quick__item span {
  font-size: 13px;
  font-weight: 700;
}

.quick__item small {
  font-size: 10px;
  color: var(--mw-text-secondary);
}

.block {
  margin-bottom: var(--mw-space-6);
}

.block__head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: var(--mw-space-3);
}

.block__head h2 {
  font-size: 16px;
  font-weight: 700;
}

.more {
  font-size: 12px;
  color: var(--mw-text-secondary);
  text-decoration: none;
}

.intro {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: rgba(242, 230, 210, 0.88);
}

.intro-meta {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--mw-text-secondary);
}

.gallery {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 8px;
  margin-top: 12px;
}

.gallery img {
  width: 100%;
  height: 110px;
  object-fit: cover;
  border-radius: var(--mw-radius-md);
  border: 1px solid var(--mw-border);
}

.gallery img:first-child {
  height: 228px;
  grid-row: span 2;
}

.coaches {
  display: flex;
  gap: 10px;
  overflow-x: auto;
  padding-bottom: 4px;
  scrollbar-width: none;
}

.coaches::-webkit-scrollbar {
  display: none;
}

.coach {
  flex: 0 0 92px;
  border: 0;
  padding: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  text-align: center;
  cursor: pointer;
}

.coach__avatar {
  width: 72px;
  height: 72px;
  margin: 0 auto 8px;
  border-radius: 50%;
  overflow: hidden;
  display: grid;
  place-items: center;
  background: linear-gradient(145deg, var(--mw-brand), #c94b12);
  color: var(--mw-brand-ink);
  font-weight: 700;
  font-size: 22px;
  box-shadow: 0 0 0 2px rgba(243, 107, 33, 0.28);
}

.coach__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.coach strong {
  display: block;
  font-size: 13px;
}

.coach small {
  display: block;
  margin-top: 2px;
  font-size: 11px;
  color: var(--mw-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.packs {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.pack {
  display: flex;
  flex-direction: column;
  min-height: 168px;
  padding: 14px 12px 12px;
  border-radius: 12px;
  background: linear-gradient(180deg, #3a2a1c 0%, #2a221c 100%);
  border: 1px solid rgba(243, 107, 33, 0.35);
}

.pack--pt {
  background: linear-gradient(180deg, #1c2c32 0%, #1a2328 100%);
  border-color: rgba(20, 184, 212, 0.32);
}

.pack__name {
  font-size: 14px;
  font-weight: 700;
  line-height: 1.35;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  min-height: 38px;
}

.pack__meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--mw-text-secondary);
}

.pack__price {
  margin-top: auto;
  padding: 10px 0 8px;
  color: var(--mw-brand);
  font-size: 22px;
  font-weight: 800;
  font-variant-numeric: tabular-nums;
}

.pack--pt .pack__price {
  color: var(--mw-cyan);
}

.pack__buy {
  width: 100%;
  min-height: 34px;
  border: 0;
  border-radius: 999px;
  background: linear-gradient(90deg, #f7c56a, var(--mw-brand));
  color: var(--mw-brand-ink);
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.pack__buy:disabled {
  opacity: 0.7;
}

.session {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
  padding: 12px 14px;
  border: 1px solid var(--mw-border);
  border-radius: var(--mw-radius-md);
  background: var(--mw-surface);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.promo {
  width: 100%;
  display: flex;
  align-items: stretch;
  gap: 12px;
  margin-bottom: 10px;
  padding: 0;
  overflow: hidden;
  border: 1px solid var(--mw-border);
  border-radius: 12px;
  background: var(--mw-surface);
  color: inherit;
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.promo__cover {
  width: 112px;
  min-height: 88px;
  flex-shrink: 0;
  background: linear-gradient(145deg, #3a2a1c, #14181c);
  display: grid;
  place-items: center;
}

.promo__cover img {
  width: 112px;
  height: 100%;
  object-fit: cover;
}

.promo__mark {
  font-family: Montserrat, Arial, sans-serif;
  font-size: 22px;
  font-weight: 800;
  color: rgba(242, 230, 210, 0.35);
}

.promo__copy {
  min-width: 0;
  flex: 1;
  padding: 12px 12px 12px 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
}

.promo__copy small {
  color: var(--mw-brand);
  font-size: 11px;
  font-weight: 700;
}

.promo__copy strong {
  font-size: 15px;
  line-height: 1.35;
}

.promo__copy span {
  font-size: 12px;
  color: var(--mw-text-secondary);
}

.session__name {
  font-weight: 700;
  font-size: 14px;
}

.session__meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--mw-text-secondary);
}

.session strong {
  color: var(--mw-brand);
  font-size: 13px;
  white-space: nowrap;
}
</style>
