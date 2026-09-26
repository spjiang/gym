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
  balance?: string | number | null
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
  if (status === 'active') return 'ok'
  if (status === 'expired' || status === 'void' || status === 'exhausted') return 'danger'
  return 'neutral'
}

function typeText(code: string) {
  const map: Record<string, string> = { term: '期限卡', count: '次卡', value: '储值卡' }
  return map[code] || '会籍'
}

function daysLeft(iso: string | null) {
  if (!iso) return null
  const end = new Date(iso)
  if (Number.isNaN(end.getTime())) return null
  return Math.ceil((end.getTime() - Date.now()) / 86400000)
}

function money(raw: string | number | null | undefined) {
  if (raw == null || raw === '') return ''
  const n = Number(raw)
  if (Number.isNaN(n)) return String(raw)
  return Number.isInteger(n) ? String(n) : n.toFixed(2)
}

function membershipSpec(m: Membership) {
  if (m.remaining_sessions != null) return { num: String(m.remaining_sessions), unit: '次' }
  const amount = money((m as Membership & { balance?: string | number | null }).balance)
  if (amount) return { num: amount, unit: '元' }
  const days = daysLeft(m.ends_at)
  if (days != null) return { num: String(Math.max(days, 0)), unit: '天' }
  return { num: '会籍', unit: '' }
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
    <p class="mw-page__desc">当前持有的会籍和私教课时</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <h2 class="mw-section-title">会籍</h2>
    <button
      v-for="m in memberships"
      :key="m.id"
      type="button"
      class="pass"
      :class="{ 'pass--dim': m.status !== 'active' }"
      @click="router.push(`/m/${mid}/gym/memberships/${m.id}`)"
    >
      <div class="mark" :class="{ 'mark--dim': m.status !== 'active' }">
        <div class="mark__num">{{ membershipSpec(m).num }}</div>
        <div v-if="membershipSpec(m).unit" class="mark__unit">{{ membershipSpec(m).unit }}</div>
      </div>
      <div class="pass__main">
        <div class="pass__top">
          <div class="pass__name">{{ m.product_name || `会籍 #${m.id}` }}</div>
          <span class="state" :class="`state--${statusClass(m.status)}`">{{ statusLabel[m.status] || m.status }}</span>
        </div>
        <div class="pass__meta">{{ typeText(m.product_type) }}</div>
        <div class="pass__meta">到期 {{ m.ends_at?.slice(0, 10) || '—' }}</div>
      </div>
    </button>
    <div v-if="!memberships.length" class="mw-empty">暂无会籍</div>

    <h2 class="mw-section-title">私教课包</h2>
    <button
      v-for="p in packages"
      :key="p.id"
      type="button"
      class="pass"
      :class="{ 'pass--dim': p.status !== 'active' }"
      @click="router.push(`/m/${mid}/gym/pt-packages/${p.id}`)"
    >
      <div class="mark mark--pt" :class="{ 'mark--dim': p.status !== 'active' }">
        <div class="mark__num">{{ p.remaining_sessions }}</div>
        <div class="mark__unit">次</div>
      </div>
      <div class="pass__main">
        <div class="pass__top">
          <div class="pass__name">{{ p.product_name || `课包 #${p.id}` }}</div>
          <span class="state" :class="`state--${statusClass(p.status)}`">{{ statusLabel[p.status] || p.status }}</span>
        </div>
        <div class="pass__meta">私教课包</div>
        <div class="pass__meta">到期 {{ p.ends_at?.slice(0, 10) || '—' }}</div>
      </div>
    </button>
    <div v-if="!packages.length" class="mw-empty">暂无课包</div>
  </section>
</template>

<style scoped>
.pass {
  display: flex;
  gap: 12px;
  width: 100%;
  box-sizing: border-box;
  margin-bottom: 12px;
  padding: 12px;
  text-align: left;
  font: inherit;
  color: inherit;
  border: 1px solid rgba(242, 230, 210, 0.08);
  border-radius: 14px;
  background: #1f252b;
  cursor: pointer;
}

.pass--dim {
  opacity: 0.72;
}

.mark {
  width: 72px;
  height: 72px;
  flex: none;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff7ec;
  background: linear-gradient(160deg, #f36b21 0%, #c45a1c 48%, #7a3010 100%);
}

.mark--pt {
  background: linear-gradient(160deg, #2dd4bf 0%, #0f8f9a 48%, #134e4a 100%);
}

.mark--dim {
  background: linear-gradient(160deg, #4a525a, #2a3138);
}

.mark__num {
  font-size: 22px;
  font-weight: 800;
  line-height: 1;
}

.mark__unit {
  margin-top: 4px;
  font-size: 12px;
  opacity: 0.88;
}

.pass__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.pass__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}

.pass__name {
  font-size: 16px;
  font-weight: 700;
  line-height: 1.3;
}

.pass__meta {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(242, 230, 210, 0.55);
}

.state {
  flex: none;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
}

.state--ok {
  color: #34d399;
  background: rgba(52, 211, 153, 0.14);
}

.state--danger {
  color: #f87171;
  background: rgba(248, 113, 113, 0.14);
}

.state--neutral {
  color: #9aa3af;
  background: rgba(154, 163, 175, 0.12);
}
</style>
