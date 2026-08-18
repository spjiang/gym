<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '../api/http'
import { pathForMerchant, useAuthStore, type MemberMerchant } from '../stores/auth'

type AccessEvent = {
  id: number
  access_point_id: number
  allowed: boolean
  reason: string | null
  created_at: string
}

const auth = useAuthStore()
const router = useRouter()
const events = ref<AccessEvent[]>([])
const fileInput = ref<HTMLInputElement | null>(null)
const uploading = ref(false)
const avatarTip = ref('')

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

function fmtTime(iso?: string) {
  if (!iso) return '—'
  return iso.slice(0, 16).replace('T', ' ')
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

function goPromotion() {
  router.push({ name: 'me-promotion' })
}

function logout() {
  auth.logout()
  router.push({ name: 'login' })
}

function pickAvatar() {
  avatarTip.value = ''
  fileInput.value?.click()
}

async function onAvatarFile(ev: Event) {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploading.value = true
  avatarTip.value = ''
  try {
    const fd = new FormData()
    fd.append('file', file)
    const { data } = await http.post('/member/avatar', fd, { timeout: 30000 })
    await auth.fetchMe()
    avatarTip.value = '头像已更新'
  } catch (e: unknown) {
    avatarTip.value = e instanceof Error ? e.message : '上传失败'
  } finally {
    uploading.value = false
  }
}

onMounted(async () => {
  void auth.fetchMe().catch(() => undefined)
  try {
    const { data } = await http.get<AccessEvent[]>('/member/access-events')
    events.value = data.slice(0, 8)
  } catch {
    events.value = []
  }
})
</script>

<template>
  <section class="me">
    <header class="me__head">
      <button class="me__back" type="button" @click="goStores">← 选店</button>
      <h1>我的</h1>
      <p class="me__site">观野SPACE · 会员中心</p>
    </header>

    <div class="me__card me__profile">
      <input
        ref="fileInput"
        class="me__file"
        type="file"
        accept="image/jpeg,image/png,image/webp"
        @change="onAvatarFile"
      />
      <button class="me__avatar" type="button" :disabled="uploading" @click="pickAvatar">
        <img v-if="auth.me?.avatar_url" :src="auth.me.avatar_url" alt="" />
        <span v-else>{{ auth.me?.name?.slice(0, 1) || '会' }}</span>
      </button>
      <div class="me__info">
        <div class="me__name">{{ auth.me?.name || '—' }}</div>
        <div class="me__phone">{{ maskPhone(auth.me?.phone) }}</div>
        <button class="me__avatar-btn" type="button" :disabled="uploading" @click="pickAvatar">
          {{ uploading ? '上传中…' : auth.me?.avatar_url ? '更换头像' : '上传头像' }}
        </button>
        <p v-if="avatarTip" class="me__hint me__hint--tight">{{ avatarTip }}</p>
      </div>
    </div>

    <div class="me__card">
      <div class="me__row">
        <span class="me__label">人脸通行</span>
        <span :class="faceOk ? 'me__pill me__pill--ok' : 'me__pill'">{{ faceText }}</span>
      </div>
      <p class="me__hint">人脸采集请到店内 Pad 完成，此处仅展示状态。</p>
      <div v-if="events.length" class="me__events">
        <div v-for="e in events" :key="e.id" class="me__event">
          <div>
            <div class="me__event-title">门禁点 {{ e.access_point_id }}</div>
            <div class="me__event-meta">
              {{ fmtTime(e.created_at) }}
              <template v-if="e.reason"> · {{ e.reason }}</template>
            </div>
          </div>
          <span class="me__pill" :class="e.allowed ? 'me__pill--ok' : 'me__pill--danger'">
            {{ e.allowed ? '放行' : '拒绝' }}
          </span>
        </div>
      </div>
      <p v-else class="me__hint me__hint--tight">暂无通行记录</p>
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

    <button class="me__card me__link" type="button" @click="goPromotion">我的推广</button>
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
  border: 0;
  padding: 0;
  overflow: hidden;
  cursor: pointer;
  font-family: inherit;
  font-weight: 700;
  font-size: 18px;
}

.me__avatar:disabled {
  opacity: 0.7;
}

.me__avatar img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.me__file {
  display: none;
}

.me__avatar-btn {
  margin-top: 8px;
  border: 0;
  padding: 0;
  background: transparent;
  color: var(--mw-brand);
  font: inherit;
  font-size: 12px;
  font-weight: 600;
  cursor: pointer;
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

.me__pill--danger {
  background: var(--mw-danger-muted);
  color: var(--mw-danger);
}

.me__hint--tight {
  margin-top: var(--mw-space-2);
}

.me__events {
  margin-top: var(--mw-space-3);
  display: flex;
  flex-direction: column;
  gap: var(--mw-space-2);
}

.me__event {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--mw-space-3);
  padding-top: var(--mw-space-2);
  border-top: 1px solid var(--mw-border);
}

.me__event-title {
  font-size: 13px;
  font-weight: 500;
}

.me__event-meta {
  margin-top: 2px;
  font-size: 12px;
  color: var(--mw-text-tertiary);
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
