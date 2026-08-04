<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

type Membership = {
  id: number
  status: string
  ends_at: string | null
  remaining_sessions: number | null
  product_id: number
}
type PtPackage = {
  id: number
  status: string
  remaining_sessions: number
  ends_at: string | null
}

const auth = useAuthStore()
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
    const mid = auth.merchantId
    const [m, p] = await Promise.all([
      http.get('/member/memberships', { params: { merchant_id: mid } }),
      http.get('/member/pt-packages', { params: { merchant_id: mid } }),
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
    <p class="mw-page__desc">展示当前商户下的会籍与私教课包状态</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <h2 class="mw-section-title">会籍</h2>
    <div v-for="m in memberships" :key="m.id" class="mw-card">
      <div class="mw-list-row">
        <div class="mw-list-row__main">
          <div class="mw-list-row__title">会籍 #{{ m.id }}</div>
          <div class="mw-list-row__meta">
            到期 {{ m.ends_at?.slice(0, 10) || '—' }} · 剩余次 {{ m.remaining_sessions ?? '—' }}
          </div>
        </div>
        <span :class="statusClass(m.status)">{{ statusLabel[m.status] || m.status }}</span>
      </div>
    </div>
    <div v-if="!memberships.length" class="mw-empty">暂无会籍</div>

    <h2 class="mw-section-title">私教课包</h2>
    <div v-for="p in packages" :key="p.id" class="mw-card">
      <div class="mw-list-row">
        <div class="mw-list-row__main">
          <div class="mw-list-row__title">课包 #{{ p.id }}</div>
          <div class="mw-list-row__meta">
            剩余课时 {{ p.remaining_sessions }} · 到期 {{ p.ends_at?.slice(0, 10) || '—' }}
          </div>
        </div>
        <span :class="statusClass(p.status)">{{ statusLabel[p.status] || p.status }}</span>
      </div>
    </div>
    <div v-if="!packages.length" class="mw-empty">暂无课包</div>
  </section>
</template>
