<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '../api/http'

type Promotion = {
  code: string | null
  link: string | null
  is_active: boolean
  rebate_rate: string
  downline_discount_rate: string
  downline_count: number
  visit_count: number
  upline_name: string | null
  my_discount_rate: string
  balance: string
  frozen_amount: string
  total_earned: string
  total_withdrawn: string
  min_withdraw_amount: string
  withdraw_hold_days?: number
  held_amount?: string
  available_balance?: string
}
type Downline = {
  name: string
  phone_masked: string
  paid_amount: string
  rebate_amount: string
}
type Ledger = {
  id: number
  kind: string
  amount: string
  balance_after: string
  from_member_name: string | null
  note: string | null
  created_at: string
}
type Payout = {
  id: number
  amount: string
  status: string
  reject_reason: string | null
  created_at: string
  paid_at: string | null
}
type Page<T> = { items: T[]; total: number }

const KIND: Record<string, string> = {
  earn: '入账',
  reverse: '冲回',
  withdraw_freeze: '冻结',
  withdraw_paid: '打款',
  withdraw_revert: '退回',
  adjust: '调整',
}
const STATUS: Record<string, string> = {
  requested: '待审核',
  approved: '待打款',
  paid: '已打款',
  rejected: '已驳回',
}

const router = useRouter()
const me = ref<Promotion | null>(null)
const downlines = ref<Downline[]>([])
const ledgers = ref<Ledger[]>([])
const payouts = ref<Payout[]>([])
const qr = ref('')
const err = ref('')
const tip = ref('')
const amount = ref('')
const submitting = ref(false)
const tab = ref<'downline' | 'ledger' | 'payout'>('downline')

function pct(v: string | number | null | undefined) {
  return `${(Number(v || 0) * 100).toFixed(1).replace(/\.0$/, '')}%`
}

function fmt(iso: string | null) {
  if (!iso) return '—'
  return iso.slice(0, 16).replace('T', ' ')
}

async function load() {
  err.value = ''
  const { data } = await http.get<Promotion>('/member/promotion')
  me.value = data
  if (data.link) {
    const QRCode = (await import('qrcode')).default
    qr.value = await QRCode.toDataURL(data.link, { width: 220, margin: 1 })
  }
  const [d, l, w] = await Promise.all([
    http.get<Page<Downline>>('/member/promotion/downline', { params: { page: 1, page_size: 20 } }),
    http.get<Page<Ledger>>('/member/promotion/ledgers', { params: { page: 1, page_size: 20 } }),
    http.get<Page<Payout>>('/member/promotion/withdrawals', { params: { page: 1, page_size: 20 } }),
  ])
  downlines.value = d.data.items
  ledgers.value = l.data.items
  payouts.value = w.data.items
}

async function copyLink() {
  if (!me.value?.link) return
  try {
    await navigator.clipboard.writeText(me.value.link)
    tip.value = '推广链接已复制'
  } catch {
    err.value = '复制失败，请长按二维码保存'
  }
}

async function withdraw() {
  err.value = ''
  tip.value = ''
  const n = Number(amount.value)
  if (!n || n <= 0) {
    err.value = '请填写提现金额'
    return
  }
  submitting.value = true
  try {
    await http.post('/member/promotion/withdrawals', { amount: amount.value })
    tip.value = '已提交提现申请，运营线下打款后状态会更新'
    amount.value = ''
    await load()
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '申请失败'
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  void load().catch((e: unknown) => {
    err.value = e instanceof Error ? e.message : '加载失败'
  })
})
</script>

<template>
  <section class="mw-page promo">
    <button class="mw-back" type="button" @click="router.push({ name: 'me' })">← 我的</button>
    <h1 class="mw-page__title">我的推广</h1>
    <p class="mw-page__desc">分享二维码邀请新会员，下级消费按比例进入返点余额。只统计一级下级。</p>
    <p v-if="tip" class="mw-msg mw-msg--ok">{{ tip }}</p>
    <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

    <div v-if="me" class="mw-card qr-card">
      <img v-if="qr" :src="qr" alt="推广二维码" class="qr" />
      <div class="code">{{ me.code || '暂无推广码' }}</div>
      <p class="meta">返点 {{ pct(me.rebate_rate) }} · 下级折扣 {{ pct(me.downline_discount_rate) }}</p>
      <p v-if="me.upline_name" class="meta">我的推荐人 {{ me.upline_name }} · 我享折扣 {{ pct(me.my_discount_rate) }}</p>
      <button class="mw-btn mw-btn--ghost mw-btn--block" type="button" :disabled="!me.link" @click="copyLink">
        复制推广链接
      </button>
    </div>

    <div class="kpis">
      <div class="kpi">
        <div class="kpi__n">¥{{ me?.available_balance ?? me?.balance ?? '0.00' }}</div>
        <div class="kpi__l">可提现</div>
      </div>
      <div class="kpi">
        <div class="kpi__n">{{ me?.downline_count ?? 0 }}</div>
        <div class="kpi__l">一级下级</div>
      </div>
      <div class="kpi">
        <div class="kpi__n">¥{{ me?.total_earned ?? '0.00' }}</div>
        <div class="kpi__l">累计入账</div>
      </div>
    </div>
    <p v-if="me && Number(me.frozen_amount) > 0" class="meta freeze">提现冻结 ¥{{ me.frozen_amount }}</p>
    <p v-if="me && Number(me.held_amount || 0) > 0" class="meta freeze">
      冷却中 ¥{{ me.held_amount }}（返点满 {{ me.withdraw_hold_days || 0 }} 天可提）
    </p>

    <div class="mw-card withdraw">
      <label class="mw-field__label" for="amt">申请提现</label>
      <div class="row">
        <input
          id="amt"
          v-model="amount"
          class="mw-input"
          type="number"
          min="0"
          step="0.01"
          :placeholder="`最低 ¥${me?.min_withdraw_amount ?? '1.00'}`"
        />
        <button class="mw-btn" type="button" :disabled="submitting" @click="withdraw">
          {{ submitting ? '提交中' : '申请' }}
        </button>
      </div>
      <p class="meta">打款在线下完成，审核通过后运营登记即为到账。</p>
      <p v-if="me && Number(me.withdraw_hold_days || 0) > 0" class="meta">
        返点满 {{ me.withdraw_hold_days }} 天后才可提现。
      </p>
    </div>

    <div class="tabs">
      <button type="button" :class="{ on: tab === 'downline' }" @click="tab = 'downline'">下级</button>
      <button type="button" :class="{ on: tab === 'ledger' }" @click="tab = 'ledger'">流水</button>
      <button type="button" :class="{ on: tab === 'payout' }" @click="tab = 'payout'">提现</button>
    </div>

    <div v-if="tab === 'downline'">
      <p v-if="!downlines.length" class="mw-empty">还没有下级会员</p>
      <div v-for="(d, i) in downlines" :key="i" class="mw-card mw-list-row">
        <div>
          <div class="mw-list-row__title">{{ d.name }} {{ d.phone_masked }}</div>
          <div class="mw-list-row__meta">实付 ¥{{ d.paid_amount }} · 贡献返点 ¥{{ d.rebate_amount }}</div>
        </div>
      </div>
    </div>
    <div v-else-if="tab === 'ledger'">
      <p v-if="!ledgers.length" class="mw-empty">暂无流水</p>
      <div v-for="l in ledgers" :key="l.id" class="mw-card mw-list-row">
        <div>
          <div class="mw-list-row__title">{{ KIND[l.kind] || l.kind }} ¥{{ l.amount }}</div>
          <div class="mw-list-row__meta">
            {{ fmt(l.created_at) }} · 余额 ¥{{ l.balance_after }}
            <span v-if="l.from_member_name"> · {{ l.from_member_name }}</span>
          </div>
        </div>
      </div>
    </div>
    <div v-else>
      <p v-if="!payouts.length" class="mw-empty">暂无提现记录</p>
      <div v-for="p in payouts" :key="p.id" class="mw-card mw-list-row">
        <div>
          <div class="mw-list-row__title">¥{{ p.amount }} · {{ STATUS[p.status] || p.status }}</div>
          <div class="mw-list-row__meta">
            {{ fmt(p.created_at) }}
            <span v-if="p.reject_reason"> · {{ p.reject_reason }}</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.mw-back {
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
.qr-card {
  text-align: center;
}
.qr {
  width: 220px;
  height: 220px;
}
.code {
  margin: 8px 0 4px;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 2px;
}
.meta {
  margin: 4px 0 10px;
  font-size: 13px;
  color: var(--mw-text-secondary);
}
.kpis {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}
.kpi {
  background: var(--mw-surface);
  border: 1px solid var(--mw-border);
  border-radius: var(--mw-radius-md);
  padding: 12px 8px;
  text-align: center;
}
.kpi__n {
  font-weight: 700;
  font-size: 16px;
}
.kpi__l {
  margin-top: 4px;
  font-size: 12px;
  color: var(--mw-text-secondary);
}
.freeze {
  margin-top: -4px;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
}
.tabs {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 8px;
  margin: 12px 0;
}
.tabs button {
  height: 36px;
  border: 1px solid var(--mw-border);
  border-radius: var(--mw-radius-sm);
  background: transparent;
  color: var(--mw-text-secondary);
  font: inherit;
}
.tabs button.on {
  border-color: var(--mw-brand);
  color: var(--mw-text);
  background: var(--mw-brand-muted);
}
.mw-empty {
  color: var(--mw-text-secondary);
  font-size: 13px;
}
</style>
