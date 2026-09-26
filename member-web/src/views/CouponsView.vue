<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'
import { couponStatusLabel } from '../utils/labels'

type Claimable = {
  id: number
  name: string
  discount_type: string
  fixed_amount: string | null
  percent_off: number | null
  threshold_amount: string
  applicable_to: string
  ends_at?: string
}
type Mine = {
  id: number
  template_id: number
  status: string
  ends_at: string
  template_name?: string | null
  discount_type?: string | null
  fixed_amount?: string | null
  percent_off?: number | null
  threshold_amount?: string | null
  applicable_to?: string | null
}

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const system = computed(() => (route.path.includes('/catering') ? 'catering' : 'gym'))
const merchantId = computed(() => Number(route.params.merchantId) || auth.merchantId)
const claimable = ref<Claimable[]>([])
const mine = ref<Mine[]>([])
const msg = ref('')
const err = ref('')
const busyId = ref<number | null>(null)

async function load() {
  const mid = merchantId.value
  const [c, m] = await Promise.all([
    http.get('/member/coupons/claimable', { params: { merchant_id: mid, system: system.value } }),
    http.get('/member/coupons', { params: { merchant_id: mid, system: system.value } }),
  ])
  claimable.value = c.data
  mine.value = m.data
}

async function claim(id: number) {
  msg.value = ''
  err.value = ''
  busyId.value = id
  try {
    await http.post('/member/coupons/claim', {
      merchant_id: merchantId.value,
      template_id: id,
    })
    msg.value = '领取成功'
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '领取失败'
    await load()
  } finally {
    busyId.value = null
  }
}

function money(raw: string | number | null | undefined) {
  if (raw == null || raw === '') return ''
  const n = Number(raw)
  if (Number.isNaN(n)) return String(raw)
  return Number.isInteger(n) ? String(n) : n.toFixed(2)
}

function face(item: { discount_type?: string | null; fixed_amount?: string | null; percent_off?: number | null }) {
  if (item.discount_type === 'percent' && item.percent_off) {
    const zhe = (100 - Number(item.percent_off)) / 10
    return { num: Number.isInteger(zhe) ? String(zhe) : zhe.toFixed(1), unit: '折', kind: '折扣' }
  }
  const amount = money(item.fixed_amount)
  return { num: amount || '券', unit: amount ? '元' : '', kind: '满减' }
}

function rule(amount: string | null | undefined) {
  const n = Number(amount)
  return n > 0 ? `满 ¥${money(amount)} 可用` : '无门槛'
}

function scopeOf(code: string | null | undefined) {
  const map: Record<string, string> = {
    membership: '仅办卡',
    retail: '仅零售',
    both: '办卡与零售',
    gym: '办卡与零售',
    dining: '酒吧消费',
  }
  return (code && map[code]) || ''
}

onMounted(load)
</script>

<template>
  <section class="mw-page">
    <h1 class="mw-page__title">优惠卡券</h1>
    <p class="mw-page__desc">{{ system === 'catering' ? '领取餐饮券，点餐结算时使用' : '领取可用优惠券，并在购卡或消费时使用' }}</p>
    <button
      v-if="system === 'catering' && merchantId"
      class="mw-btn mw-btn--ghost mw-btn--sm"
      type="button"
      style="margin-bottom: 12px"
      @click="router.push(`/m/${merchantId}/catering`)"
    >
      去点餐使用
    </button>
    <p v-if="msg" class="mw-msg mw-msg--ok">{{ msg }}</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <h2 class="mw-section-title">可领取</h2>
    <div v-if="!claimable.length" class="mw-empty">暂无可领券</div>
    <article v-for="c in claimable" :key="c.id" class="ticket">
      <div class="stub">
        <div class="stub__num">{{ face(c).num }}</div>
        <div v-if="face(c).unit" class="stub__unit">{{ face(c).unit }}</div>
        <div class="stub__kind">{{ face(c).kind }}</div>
      </div>
      <div class="ticket__main">
        <div class="ticket__name">{{ c.name }}</div>
        <div class="ticket__meta">{{ rule(c.threshold_amount) }}<template v-if="scopeOf(c.applicable_to)"> · {{ scopeOf(c.applicable_to) }}</template></div>
        <div class="ticket__foot">
          <span class="ticket__until">{{ c.ends_at ? `至 ${c.ends_at.slice(0, 10)}` : '' }}</span>
          <button class="claim" type="button" :disabled="busyId === c.id" @click="claim(c.id)">
            {{ busyId === c.id ? '领取中' : '领取' }}
          </button>
        </div>
      </div>
    </article>

    <h2 class="mw-section-title">我的券</h2>
    <article v-for="c in mine" :key="c.id" class="ticket" :class="{ 'ticket--dim': c.status !== 'unused' }">
      <div class="stub" :class="{ 'stub--dim': c.status !== 'unused' }">
        <div class="stub__num">{{ face(c).num }}</div>
        <div v-if="face(c).unit" class="stub__unit">{{ face(c).unit }}</div>
        <div class="stub__kind">{{ face(c).kind }}</div>
      </div>
      <div class="ticket__main">
        <div class="ticket__name">{{ c.template_name || `券 #${c.id}` }}</div>
        <div class="ticket__meta">
          {{ rule(c.threshold_amount) }}
          <template v-if="scopeOf(c.applicable_to)"> · {{ scopeOf(c.applicable_to) }}</template>
        </div>
        <div class="ticket__foot">
          <span class="ticket__until">至 {{ c.ends_at?.slice(0, 10) }}</span>
          <span class="state" :class="`state--${c.status}`">{{ couponStatusLabel(c.status) }}</span>
        </div>
      </div>
    </article>
    <div v-if="!mine.length" class="mw-empty">暂无卡券</div>
  </section>
</template>

<style scoped>
.ticket {
  display: flex;
  margin-bottom: 12px;
  border-radius: 14px;
  overflow: hidden;
  background: #1f252b;
  border: 1px solid rgba(242, 230, 210, 0.08);
}

.ticket--dim {
  opacity: 0.72;
}

.stub {
  width: 84px;
  flex: none;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #fff7ec;
  background: linear-gradient(160deg, #f36b21 0%, #c45a1c 48%, #7a3010 100%);
}

.stub--dim {
  background: linear-gradient(160deg, #4a525a, #2a3138);
}

.stub__num {
  font-size: 26px;
  font-weight: 800;
  line-height: 1;
}

.stub__unit,
.stub__kind {
  margin-top: 4px;
  font-size: 11px;
  opacity: 0.88;
}

.ticket__main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  padding: 12px 12px 10px;
}

.ticket__name {
  font-size: 16px;
  font-weight: 700;
}

.ticket__meta,
.ticket__until {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(242, 230, 210, 0.55);
}

.ticket__foot {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  margin-top: auto;
  padding-top: 8px;
}

.claim {
  border: 0;
  border-radius: 999px;
  padding: 6px 14px;
  background: #f36b21;
  color: #171b1f;
  font: inherit;
  font-size: 13px;
  font-weight: 700;
  cursor: pointer;
}

.claim:disabled {
  opacity: 0.6;
}

.state {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 700;
}

.state--unused {
  color: #34d399;
  background: rgba(52, 211, 153, 0.14);
}

.state--used {
  color: rgba(242, 230, 210, 0.55);
  background: rgba(242, 230, 210, 0.08);
}

.state--expired,
.state--void {
  color: #f87171;
  background: rgba(248, 113, 113, 0.14);
}
</style>
