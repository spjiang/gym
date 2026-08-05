<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

type Membership = {
  id: number
  status: string
  ends_at: string | null
  remaining_sessions: number | null
  product_id: number
  product_name: string | null
  product_type: string
}
type PtPackage = {
  id: number
  status: string
  remaining_sessions: number
  ends_at: string | null
  product_name: string | null
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const mid = computed(() => Number(route.params.merchantId) || auth.merchantId)
const memberships = ref<Membership[]>([])
const packages = ref<PtPackage[]>([])
const err = ref('')

const statusLabel: Record<string, string> = {
  active: '有效',
  frozen: '冻结',
  expired: '已过期',
  void: '作废',
  exhausted: '已用尽',
}

function statusClass(status: string) {
  if (status === 'active') return 'mw-status mw-status--ok'
  if (status === 'expired' || status === 'void' || status === 'exhausted') return 'mw-status mw-status--danger'
  return 'mw-status mw-status--neutral'
}

async function load() {
  err.value = ''
  try {
    const merchantId = mid.value
    const [m, p] = await Promise.all([
      http.get('/member/memberships', { params: { merchant_id: merchantId } }),
      http.get('/member/pt-packages', { params: { merchant_id: merchantId } }),
    ])
    memberships.value = m.data
    packages.value = p.data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
  }
}

onMounted(load)
</script>

<template>
  <section class="mw-page">
    <h1 class="mw-page__title">会籍与课包</h1>
    <p class="mw-page__desc">点击卡片查看详情</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <h2 class="mw-section-title">会籍</h2>
    <button
      v-for="m in memberships"
      :key="m.id"
      type="button"
      class="mw-card card-btn"
      @click="router.push(`/m/${mid}/gym/memberships/${m.id}`)"
    >
      <div class="mw-list-row">
        <div class="mw-list-row__main">
          <div class="mw-list-row__title">{{ m.product_name || `会籍 #${m.id}` }}</div>
          <div class="mw-list-row__meta">
            到期 {{ m.ends_at?.slice(0, 10) || '—' }} · 剩余次 {{ m.remaining_sessions ?? '—' }}
          </div>
        </div>
        <div class="card-btn__right">
          <span :class="statusClass(m.status)">{{ statusLabel[m.status] || m.status }}</span>
          <span class="card-btn__go">详情</span>
        </div>
      </div>
    </button>
    <div v-if="!memberships.length" class="mw-empty">暂无会籍</div>

    <h2 class="mw-section-title">私教课包</h2>
    <button
      v-for="p in packages"
      :key="p.id"
      type="button"
      class="mw-card card-btn"
      @click="router.push(`/m/${mid}/gym/pt-packages/${p.id}`)"
    >
      <div class="mw-list-row">
        <div class="mw-list-row__main">
          <div class="mw-list-row__title">{{ p.product_name || `课包 #${p.id}` }}</div>
          <div class="mw-list-row__meta">
            剩余课时 {{ p.remaining_sessions }} · 到期 {{ p.ends_at?.slice(0, 10) || '—' }}
          </div>
        </div>
        <div class="card-btn__right">
          <span :class="statusClass(p.status)">{{ statusLabel[p.status] || p.status }}</span>
          <span class="card-btn__go">详情</span>
        </div>
      </div>
    </button>
    <div v-if="!packages.length" class="mw-empty">暂无课包</div>
  </section>
</template>

<style scoped>
.card-btn {
  width: 100%;
  text-align: left;
  cursor: pointer;
  font: inherit;
  color: inherit;
  display: block;
}

.card-btn:hover {
  background: var(--mw-surface-hover);
  border-color: var(--mw-border-strong);
}

.card-btn__right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  flex-shrink: 0;
}

.card-btn__go {
  font-size: 12px;
  font-weight: 600;
  color: var(--mw-brand);
}
</style>
