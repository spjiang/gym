<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { pathForMerchant, useAuthStore, type MemberMerchant } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()

const faceLabel: Record<string, string> = {
  not_enrolled: '未录入',
  enrolled: '已录入',
}

const systemLabel: Record<string, string> = {
  gym: '健身',
  catering: '餐饮',
}

function maskPhone(phone?: string) {
  if (!phone || phone.length < 7) return phone || ''
  return `${phone.slice(0, 3)}****${phone.slice(-4)}`
}

function labelFor(m: MemberMerchant) {
  const sys = m.primary_system || m.subsystem_codes[0] || ''
  return systemLabel[sys] || m.subsystem_codes.map((c) => systemLabel[c] || c).join('·') || '门店'
}

const faceText = computed(() => faceLabel[auth.me?.face_status || ''] || auth.me?.face_status || '未知')
const faceOk = computed(() => auth.me?.face_status === 'enrolled')
const sourceText = computed(() => {
  if (auth.me?.acquisition_source === 'merchant') {
    return auth.me.first_merchant_name || `商户 #${auth.me.first_merchant_id}`
  }
  return '综合运营平台'
})

function enterStore(m: MemberMerchant) {
  auth.setMerchantId(m.id)
  router.push(pathForMerchant(m))
}

function goStores() {
  router.push({ name: 'stores' })
}

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}

onMounted(() => {
  void auth.fetchMe().catch(() => undefined)
})
</script>

<template>
  <section class="me">
    <header class="me__head">
      <button class="me__back" type="button" @click="goStores">← 选店</button>
      <h1>我的</h1>
      <p class="me__site">回龙观公园综合场地 · 会员中心</p>
    </header>

    <div class="me__card me__profile">
      <div class="me__avatar" aria-hidden="true">{{ auth.me?.name?.slice(0, 1) || '会' }}</div>
      <div class="me__info">
        <div class="me__name">{{ auth.me?.name || '—' }}</div>
        <div class="me__phone">{{ maskPhone(auth.me?.phone) }}</div>
      </div>
    </div>

    <div class="me__card">
      <div class="me__row">
        <span class="me__label">人脸通行</span>
        <span :class="faceOk ? 'me__pill me__pill--ok' : 'me__pill'">{{ faceText }}</span>
      </div>
      <p class="me__hint">人脸采集请到店内 Pad 完成，此处仅展示状态。</p>
    </div>

    <div class="me__card">
      <div class="me__row">
        <span class="me__label">首次来源</span>
        <span class="me__source">{{ sourceText }}</span>
      </div>
    </div>

    <h2 class="me__section">关联门店</h2>
    <p v-if="!(auth.me?.merchants || []).length" class="me__empty">暂无关联门店</p>
    <button
      v-for="m in auth.me?.merchants || []"
      :key="m.id"
      type="button"
      class="me__card me__store"
      @click="enterStore(m)"
    >
      <div>
        <div class="me__store-badge">{{ labelFor(m) }}</div>
        <div class="me__store-name">{{ m.name }}</div>
      </div>
      <span class="me__store-go">进入</span>
    </button>

    <button class="me__card me__link" type="button" @click="goStores">全部门店 / 切换业态</button>

    <button class="mw-btn mw-btn--ghost mw-btn--block me__logout" type="button" @click="logout">退出登录</button>
  </section>
</template>

<style scoped>
.me {
  max-width: var(--mw-shell-max);
  margin: 0 auto;
  min-height: 100vh;
  padding: var(--mw-space-4) var(--mw-space-4) var(--mw-space-8);
  background: var(--mw-bg);
}

.me__head {
  margin-bottom: var(--mw-space-5);
}

.me__back {
  border: 0;
  background: transparent;
  color: var(--mw-brand);
  padding: 0;
  margin-bottom: var(--mw-space-3);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
}

.me__head h1 {
  margin: 0;
  font-size: 24px;
}

.me__site {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--mw-text-tertiary);
}

.me__card {
  background: var(--mw-surface);
  border: 1px solid var(--mw-border);
  border-radius: var(--mw-radius-md);
  padding: var(--mw-space-4);
  margin-bottom: var(--mw-space-3);
}

.me__profile {
  display: flex;
  align-items: center;
  gap: var(--mw-space-4);
}

.me__avatar {
  width: 52px;
  height: 52px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: var(--mw-brand);
  color: var(--mw-brand-ink);
  font-weight: 700;
  font-size: 18px;
  flex-shrink: 0;
}

.me__name {
  font-size: 18px;
  font-weight: 600;
}

.me__phone {
  margin-top: 4px;
  font-size: 13px;
  color: var(--mw-text-secondary);
}

.me__row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mw-space-3);
}

.me__label {
  font-size: 14px;
  font-weight: 500;
}

.me__pill {
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 6px;
  background: rgba(230, 179, 90, 0.18);
  color: var(--mw-warning);
}

.me__pill--ok {
  background: var(--mw-success-muted);
  color: var(--mw-success);
}

.me__source {
  font-size: 13px;
  font-weight: 600;
  color: var(--mw-text);
}

.me__hint {
  margin: var(--mw-space-3) 0 0;
  font-size: 12px;
  color: var(--mw-text-tertiary);
  line-height: 1.45;
}

.me__section {
  margin: var(--mw-space-5) 0 var(--mw-space-3);
  font-size: 13px;
  font-weight: 600;
  color: var(--mw-text-secondary);
}

.me__empty {
  margin: 0 0 var(--mw-space-3);
  font-size: 13px;
  color: var(--mw-text-tertiary);
}

.me__store {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mw-space-3);
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: inherit;
}

.me__store-badge {
  display: inline-block;
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--mw-brand-muted);
  color: var(--mw-brand);
  margin-bottom: 6px;
}

.me__store-name {
  font-size: 15px;
  font-weight: 600;
}

.me__store-go {
  font-size: 12px;
  font-weight: 600;
  color: var(--mw-text-tertiary);
  flex-shrink: 0;
}

.me__link {
  width: 100%;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: var(--mw-text-secondary);
  font-size: 14px;
}

.me__logout {
  margin-top: var(--mw-space-6);
}
</style>
