<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'

type Membership = {
  id: number
  merchant_id: number
  product_id: number
  product_type: string
  status: string
  starts_at: string | null
  ends_at: string | null
  remaining_sessions: number | null
  balance: string | number | null
  product_name: string | null
}

const route = useRoute()
const router = useRouter()
const mid = computed(() => Number(route.params.merchantId))
const membershipId = computed(() => Number(route.params.membershipId))
const item = ref<Membership | null>(null)
const err = ref('')
const loading = ref(true)

const statusLabel: Record<string, string> = {
  active: '有效',
  frozen: '冻结',
  expired: '已过期',
  void: '作废',
}

const typeLabel: Record<string, string> = {
  term: '期限卡',
  count: '次卡',
  value: '储值卡',
}

function statusClass(status: string) {
  if (status === 'active') return 'mw-status mw-status--ok'
  if (status === 'expired' || status === 'void') return 'mw-status mw-status--danger'
  return 'mw-status mw-status--neutral'
}

function fmtDate(v: string | null) {
  return v?.slice(0, 10) || '—'
}

async function load() {
  loading.value = true
  err.value = ''
  try {
    const { data } = await http.get<Membership>(`/member/memberships/${membershipId.value}`)
    if (data.merchant_id !== mid.value) {
      err.value = '该会籍不属于当前门店'
      item.value = null
      return
    }
    item.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '加载失败'
    item.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="mw-page">
    <button class="back" type="button" @click="router.push(`/m/${mid}/gym/memberships`)">← 会籍列表</button>

    <p v-if="loading" class="mw-page__desc">加载中…</p>
    <p v-else-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <template v-else-if="item">
      <div class="hero mw-card">
        <div class="hero__top">
          <span class="hero__badge">会籍</span>
          <span :class="statusClass(item.status)">{{ statusLabel[item.status] || item.status }}</span>
        </div>
        <h1 class="hero__title">{{ item.product_name || `会籍 #${item.id}` }}</h1>
        <p class="hero__sub">#{{ item.id }} · {{ typeLabel[item.product_type] || item.product_type }}</p>
      </div>

      <div class="mw-card">
        <div class="row"><span>卡种类型</span><span>{{ typeLabel[item.product_type] || item.product_type }}</span></div>
        <div class="row"><span>生效日期</span><span>{{ fmtDate(item.starts_at) }}</span></div>
        <div class="row"><span>到期日期</span><span>{{ fmtDate(item.ends_at) }}</span></div>
        <div class="row"><span>剩余次数</span><span>{{ item.remaining_sessions ?? '—' }}</span></div>
        <div class="row"><span>储值余额</span><span>{{ item.balance != null ? `¥${item.balance}` : '—' }}</span></div>
        <div class="row"><span>卡种 ID</span><span>{{ item.product_id }}</span></div>
      </div>

      <p class="tip">如需冻结、续费或变更，请到店联系前台办理。</p>
    </template>
  </section>
</template>

<style scoped>
.back {
  border: 0;
  background: transparent;
  color: var(--mw-brand);
  padding: 0;
  margin-bottom: var(--mw-space-4);
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: 600;
}

.hero__top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--mw-space-3);
}

.hero__badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 8px;
  border-radius: 6px;
  background: var(--mw-brand-muted);
  color: var(--mw-brand);
}

.hero__title {
  margin: 0;
  font-size: 20px;
}

.hero__sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: var(--mw-text-secondary);
}

.row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--mw-border);
  font-size: 14px;
}

.row:last-child {
  border-bottom: 0;
  padding-bottom: 0;
}

.row span:first-child {
  color: var(--mw-text-secondary);
}

.tip {
  margin: var(--mw-space-4) 0 0;
  font-size: 12px;
  color: var(--mw-text-tertiary);
}
</style>
