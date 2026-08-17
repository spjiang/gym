<script setup lang="ts">
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { pathForMerchant, useAuthStore, type MemberMerchant } from '../stores/auth'
import BrandMark from '../components/BrandMark.vue'

const auth = useAuthStore()
const router = useRouter()

const faceLabel: Record<string, string> = {
  not_enrolled: '人脸未录入',
  enrolled: '人脸已录入',
}

function maskPhone(phone?: string) {
  if (!phone || phone.length < 7) return phone || ''
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`
}

function systemOf(m: MemberMerchant) {
  return m.primary_system || m.subsystem_codes[0] || 'other'
}

type Section = {
  key: string
  title: string
  subtitle: string
  items: MemberMerchant[]
}

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
    out.push({
      key: 'gym',
      title: '观野FIT',
      subtitle: '会籍 · 团课 · 商城 · 通行',
      items: buckets.gym,
    })
  }
  if (buckets.catering.length) {
    out.push({
      key: 'catering',
      title: '观野BAR',
      subtitle: '点餐 · 取餐号 · 订单',
      items: buckets.catering,
    })
  }
  if (buckets.other.length) {
    out.push({
      key: 'other',
      title: '其它门店',
      subtitle: '进入查看可用服务',
      items: buckets.other,
    })
  }
  return out
})

const faceText = computed(() => faceLabel[auth.me?.face_status || ''] || '人脸状态未知')

function enter(m: MemberMerchant) {
  auth.setMerchantId(m.id)
  router.push(pathForMerchant(m))
}

function goMe() {
  router.push({ name: 'me' })
}
</script>

<template>
  <section class="stores">
    <div class="stores__glow" aria-hidden="true" />

    <header class="stores__brand">
      <div class="stores__brand-row">
        <BrandMark variant="space" compact />
        <div class="stores__actions">
          <button class="mw-btn mw-btn--ghost mw-btn--sm" type="button" @click="goMe">我的</button>
        </div>
      </div>
      <h1 class="stores__hello">你好，{{ auth.me?.name }}</h1>
      <p class="stores__lead">选择门店进入对应业态服务</p>
      <button class="stores__meta" type="button" @click="goMe">
        <span>{{ maskPhone(auth.me?.phone) }}</span>
        <span class="stores__dot" aria-hidden="true" />
        <span>{{ faceText }}</span>
        <span class="stores__meta-go">个人中心 →</span>
      </button>
    </header>

    <div v-if="!sections.length" class="mw-card stores__empty">
      暂无关联门店，请到店由前台为你建档关联。
    </div>

    <section v-for="(sec, si) in sections" :key="sec.key" class="stores__section" :style="{ '--i': si }">
      <div class="stores__section-head">
        <h2>{{ sec.title }}</h2>
        <p>{{ sec.subtitle }}</p>
      </div>

      <button
        v-for="(m, mi) in sec.items"
        :key="m.id"
        type="button"
        class="store-card"
        :class="`store-card--${sec.key}`"
        :style="{ '--j': mi }"
        @click="enter(m)"
      >
        <div class="store-card__accent" aria-hidden="true" />
        <div class="store-card__body">
          <div class="store-card__top">
            <span class="store-card__badge">{{ sec.title }}</span>
            <span class="store-card__go">进入</span>
          </div>
          <div class="store-card__name">{{ m.name }}</div>
          <div class="store-card__hint">{{ sec.subtitle }}</div>
        </div>
      </button>
    </section>

    <p v-if="sections.length" class="stores__tip">进入后可随时点顶栏「切换」回到本页</p>
  </section>
</template>

<style scoped>
.stores {
  position: relative;
  max-width: var(--mw-shell-max);
  margin: 0 auto;
  min-height: 100vh;
  padding: var(--mw-space-5) var(--mw-space-4) var(--mw-space-8);
  overflow: hidden;
}

.stores__glow {
  position: absolute;
  inset: -20% -30% auto;
  height: 280px;
  background:
    radial-gradient(ellipse 70% 60% at 20% 30%, rgba(242, 230, 210, 0.08), transparent 60%),
    radial-gradient(ellipse 50% 50% at 85% 20%, rgba(20, 184, 212, 0.08), transparent 55%);
  pointer-events: none;
  animation: glow-in 0.8s var(--mw-ease) both;
}

.stores__brand {
  position: relative;
  margin-bottom: var(--mw-space-6);
  animation: rise 0.45s var(--mw-ease) both;
}

.stores__brand-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mw-space-3);
  margin-bottom: var(--mw-space-3);
}

.stores__hello {
  margin: 0;
  font-size: 26px;
  line-height: 1.25;
  letter-spacing: -0.03em;
}

.stores__lead {
  margin: var(--mw-space-2) 0 0;
  font-size: 14px;
  color: var(--mw-text-secondary);
}

.stores__actions {
  display: flex;
  gap: 6px;
}

.stores__meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--mw-space-2);
  width: 100%;
  margin-top: var(--mw-space-4);
  padding: var(--mw-space-3) var(--mw-space-4);
  border-radius: var(--mw-radius-md);
  border: 1px solid var(--mw-border);
  background: var(--mw-surface);
  font-size: 13px;
  color: var(--mw-text-secondary);
  font: inherit;
  text-align: left;
  cursor: pointer;
}

.stores__meta-go {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: var(--mw-brand);
}

.stores__dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--mw-text-tertiary);
}

.stores__section {
  position: relative;
  margin-bottom: var(--mw-space-5);
  animation: rise 0.5s var(--mw-ease) both;
  animation-delay: calc(0.08s * (var(--i) + 1));
}

.stores__section-head {
  margin-bottom: var(--mw-space-3);
}

.stores__section-head h2 {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--mw-text-secondary);
}

.stores__section-head p {
  margin: 4px 0 0;
  font-size: 12px;
  color: var(--mw-text-tertiary);
}

.store-card {
  position: relative;
  display: flex;
  width: 100%;
  margin: 0 0 var(--mw-space-3);
  padding: 0;
  overflow: hidden;
  text-align: left;
  cursor: pointer;
  border: 1px solid var(--mw-border);
  border-radius: var(--mw-radius-md);
  background: var(--mw-surface);
  color: inherit;
  font: inherit;
  box-shadow: var(--mw-shadow);
  transition:
    transform var(--mw-ease),
    border-color var(--mw-ease),
    background var(--mw-ease);
  animation: rise 0.45s var(--mw-ease) both;
  animation-delay: calc(0.06s * (var(--j) + 1) + 0.1s * (var(--i) + 1));
}

.store-card:hover {
  transform: translateY(-2px);
  border-color: var(--mw-border-strong);
  background: var(--mw-surface-hover);
}

.store-card:active {
  transform: translateY(0);
}

.store-card__accent {
  width: 4px;
  flex-shrink: 0;
  background: var(--mw-brand);
}

.store-card--catering .store-card__accent {
  background: var(--mw-cyan);
}

.store-card--other .store-card__accent {
  background: var(--mw-text-tertiary);
}

.store-card__body {
  flex: 1;
  min-width: 0;
  padding: var(--mw-space-4);
}

.store-card__top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mw-space-3);
  margin-bottom: var(--mw-space-2);
}

.store-card__badge {
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.04em;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--mw-brand-muted);
  color: var(--mw-brand);
}

.store-card--catering .store-card__badge {
  background: rgba(20, 184, 212, 0.14);
  color: #14b8d4;
}

.store-card__go {
  font-size: 12px;
  font-weight: 600;
  color: var(--mw-text-tertiary);
}

.store-card:hover .store-card__go {
  color: var(--mw-brand);
}

.store-card--catering:hover .store-card__go {
  color: #14b8d4;
}

.store-card__name {
  font-size: 17px;
  font-weight: 600;
  letter-spacing: -0.02em;
}

.store-card__hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--mw-text-tertiary);
}

.stores__empty {
  color: var(--mw-text-secondary);
  animation: rise 0.4s var(--mw-ease) both;
}

.stores__tip {
  position: relative;
  margin: var(--mw-space-2) 0 0;
  text-align: center;
  font-size: 12px;
  color: var(--mw-text-tertiary);
  animation: rise 0.5s var(--mw-ease) 0.25s both;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes glow-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@media (prefers-reduced-motion: reduce) {
  .stores__glow,
  .stores__brand,
  .stores__section,
  .store-card,
  .stores__empty,
  .stores__tip {
    animation: none;
  }

  .store-card:hover {
    transform: none;
  }
}
</style>
