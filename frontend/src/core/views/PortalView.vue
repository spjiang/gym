<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref, type Component } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowRight,
  Bell,
  Calendar,
  CircleCheck,
  Collection,
  Money,
  Plus,
  TrendCharts,
  User,
  Warning,
} from '@element-plus/icons-vue'
import { useAuthStore } from '../stores/auth'
import { canAny } from '../nav/systems'
import http from '../api/http'
import { orderStatusLabel, orderTypeLabel as mapOrderType } from '../labels'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type OrderRow = { id: number; title: string; amount: string; status: string; order_type: string }
type NoteRow = {
  id: number
  event_type: string
  title: string
  body: string
  created_at: string
}
type ChannelRow = { channel: string; charge_total: string; refund_total: string; net_total: string }
type OrderTypeRow = { order_type: string; charge_total: string; refund_total: string; net_total: string }
type CommerceSummary = {
  charge_total: string
  refund_total: string
  net_total: string
  by_channel: ChannelRow[]
  by_order_type: OrderTypeRow[]
}
type MembershipSummary = {
  new_count: number
  renew_count: number
  active_count: number
  frozen_count: number
  expired_in_range: number
}
type CourseSummary = {
  session_count: number
  booking_count: number
  full_session_count: number
  attended_count: number
  pt_consume_count: number
}

const auth = useAuthStore()
const router = useRouter()

const now = ref(new Date())

const loading = ref(true)
const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const memberTotal = ref(0)
const orders = ref<OrderRow[]>([])
const orderTotal = ref(0)
const notes = ref<NoteRow[]>([])
const commerce = ref<CommerceSummary | null>(null)
const commerceTypes = computed(() => commerce.value?.by_order_type || [])
const membership = ref<MembershipSummary | null>(null)
const course = ref<CourseSummary | null>(null)

// 各区块按权限独立加载，失败不阻塞整页
const sectionState = reactive({
  merchants: false,
  members: false,
  orders: false,
  notes: false,
  commerce: false,
  membership: false,
  course: false,
})

const perms = computed(() => auth.me?.permissions || [])

const orderTypeLabel = mapOrderType

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

function greeting() {
  const h = now.value.getHours()
  if (h < 6) return '夜深了'
  if (h < 11) return '早上好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}

function weekday() {
  return `星期${'日一二三四五六'[now.value.getDay()]}`
}

function fmtDate() {
  const d = now.value
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日`
}

function fmtTime(iso: string) {
  const d = new Date(iso)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function statusType(status: string) {
  if (status === 'paid') return 'success'
  if (status === 'pending') return 'warning'
  if (status === 'refunded') return 'danger'
  return 'info'
}

function statusLabel(status: string) {
  return orderStatusLabel(status)
}

function go(path: string) {
  router.push(path)
}

function quickActions() {
  const codes = new Set(merchants.value.flatMap((m) => m.subsystem_codes || []))
  const isSiteAdmin = perms.value.includes('*')
  const hasGym = isSiteAdmin || codes.has('gym')
  const hasCatering = isSiteAdmin || codes.has('catering')
  const actions: { label: string; path: string; icon: Component; show: boolean }[] = [
    { label: '会员建档', path: '/members', icon: User, show: canAny(perms.value, ['member:write', '*']) },
    {
      label: '办卡收款',
      path: '/memberships',
      icon: Money,
      show: hasGym && canAny(perms.value, ['membership:sell', '*']),
    },
    {
      label: '登记临访',
      path: '/visits',
      icon: Plus,
      show: canAny(perms.value, ['access:manage', '*']),
    },
    {
      label: '经营报表',
      path: '/reports',
      icon: TrendCharts,
      show: canAny(perms.value, ['report:read', '*']),
    },
    {
      label: '餐饮点单',
      path: '/catering/orders',
      icon: Collection,
      show: hasCatering && canAny(perms.value, ['catering:order', '*']),
    },
    {
      label: '订单收款',
      path: '/orders',
      icon: Collection,
      show: canAny(perms.value, ['order:write', '*']),
    },
  ]
  return actions.filter((a) => a.show)
}

async function loadMerchants() {
  if (!canAny(perms.value, ['org:read', '*'])) return
  try {
    const { data } = await http.get('/merchants')
    merchants.value = data
    sectionState.merchants = true
  } catch {
    sectionState.merchants = false
  }
}

async function loadMembers() {
  if (!canAny(perms.value, ['member:read', '*'])) return
  try {
    const { data } = await http.get('/members', { params: { page: 1, page_size: 1 } })
    members.value = data.items
    memberTotal.value = data.total
    sectionState.members = true
  } catch {
    sectionState.members = false
  }
}

async function loadOrders() {
  if (!canAny(perms.value, ['order:read', '*'])) return
  try {
    const { data } = await http.get('/orders', { params: { page: 1, page_size: 20 } })
    orders.value = data.items
    orderTotal.value = data.total
    sectionState.orders = true
  } catch {
    sectionState.orders = false
  }
}

async function loadNotes() {
  if (!canAny(perms.value, ['order:read', 'member:read', 'access:read'])) return
  try {
    const { data } = await http.get('/notifications', { params: { page: 1, page_size: 8 } })
    notes.value = data.items
    sectionState.notes = true
  } catch {
    sectionState.notes = false
  }
}

async function loadReports() {
  if (!canAny(perms.value, ['report:read', '*'])) return
  const today = todayStr()
  try {
    const { data } = await http.get('/reports/commerce-summary', {
      params: { date_from: today, date_to: today },
    })
    commerce.value = data
    sectionState.commerce = true
  } catch {
    sectionState.commerce = false
  }
  try {
    const { data } = await http.get('/reports/membership-summary', {
      params: { date_from: today, date_to: today },
    })
    membership.value = data
    sectionState.membership = true
  } catch {
    sectionState.membership = false
  }
  try {
    const { data } = await http.get('/reports/course-summary', {
      params: { date_from: today, date_to: today },
    })
    course.value = data
    sectionState.course = true
  } catch {
    sectionState.course = false
  }
}

let timer: number | undefined

async function refresh() {
  loading.value = true
  await Promise.all([loadMerchants(), loadMembers(), loadOrders(), loadNotes(), loadReports()])
  loading.value = false
}

onMounted(() => {
  refresh()
  timer = window.setInterval(() => {
    now.value = new Date()
  }, 30000)
})

onUnmounted(() => {
  if (timer) window.clearInterval(timer)
})

function valueSize(value: string) {
  // ¥990000.00 ≈ 11 字符：靠更小字号单行显示
  const n = value.length
  if (n >= 12) return 'xs'
  if (n >= 10) return 'sm'
  if (n >= 8) return 'md'
  return 'lg'
}

function formatMoney(amount: string | number) {
  const n = Number(amount)
  if (!Number.isFinite(n)) return '¥0.00'
  // 不加千分位，避免拉长；99 万级靠字号单行展示
  return `¥${n.toFixed(2)}`
}

function kpi() {
  const items: { label: string; value: string; sub: string; icon: Component; tone: string }[] = []
  if (sectionState.commerce && commerce.value) {
    items.push({
      label: '今日实收',
      value: formatMoney(commerce.value.charge_total),
      sub: '含退款前入账',
      icon: Money,
      tone: 'green',
    })
    items.push({
      label: '今日净收',
      value: formatMoney(commerce.value.net_total),
      sub: '实收扣退款',
      icon: TrendCharts,
      tone: 'copper',
    })
  }
  if (sectionState.membership && membership.value) {
    items.push({
      label: '在籍会籍',
      value: String(membership.value.active_count),
      sub: `今日新开 ${membership.value.new_count} · 停卡 ${membership.value.frozen_count}`,
      icon: CircleCheck,
      tone: 'green',
    })
  }
  if (sectionState.members) {
    items.push({
      label: '会员总数',
      value: String(memberTotal.value),
      sub: '本场地会员档案',
      icon: User,
      tone: 'slate',
    })
  }
  if (sectionState.course && course.value) {
    items.push({
      label: '今日团课',
      value: String(course.value.session_count),
      sub: `预约 ${course.value.booking_count} · 出勤 ${course.value.attended_count}`,
      icon: Calendar,
      tone: 'copper',
    })
  }
  if (sectionState.notes) {
    items.push({
      label: '最新通知',
      value: String(notes.value.length),
      sub: '近 8 条业务动态',
      icon: Bell,
      tone: 'slate',
    })
  }
  return items
}

function maxCharge() {
  const rows = commerce.value?.by_order_type || []
  const max = Math.max(1, ...rows.map((r) => Number(r.charge_total)))
  return max
}
</script>

<template>
  <div class="portal">
    <!-- 欢迎区 -->
    <section class="welcome">
      <div class="welcome-text">
        <p class="eyebrow">运营工作台 · {{ fmtDate() }} {{ weekday() }}</p>
        <h2>{{ greeting() }}，{{ auth.me?.display_name || '管理员' }}</h2>
        <p class="lead">观野SPACE 综合管理平台 · 今日关键数据与待办事项一目了然。</p>
      </div>
      <div class="welcome-actions">
        <el-button
          v-for="a in quickActions()"
          :key="a.path"
          :icon="a.icon"
          type="primary"
          plain
          round
          @click="go(a.path)"
        >
          {{ a.label }}
        </el-button>
      </div>
    </section>

    <!-- KPI -->
    <el-skeleton v-if="loading && !kpi().length" :rows="3" animated class="kpi-skeleton" />
    <section v-else-if="kpi().length" class="kpi-grid">
      <div v-for="(k, i) in kpi()" :key="i" class="kpi-card" :data-tone="k.tone">
        <div class="kpi-icon"><el-icon :size="20"><component :is="k.icon" /></el-icon></div>
        <div class="kpi-meta">
          <div class="kpi-label">{{ k.label }}</div>
          <div class="kpi-value" :data-size="valueSize(k.value)">{{ k.value }}</div>
          <div class="kpi-sub">{{ k.sub }}</div>
        </div>
      </div>
    </section>

    <div class="portal-grid">
      <!-- 左：经营概览 -->
      <section class="panel">
        <header class="panel-head">
          <div>
            <p class="eyebrow">Overview</p>
            <h3>今日经营概览</h3>
          </div>
          <el-button
            v-if="sectionState.commerce"
            text
            type="primary"
            @click="go('/reports')"
          >
            查看报表 <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </header>

        <div v-if="!sectionState.commerce" class="panel-empty">
          <el-icon><Warning /></el-icon>
          <p>暂无报表查看权限或数据未加载</p>
        </div>
        <template v-else>
          <div v-if="commerceTypes.length" class="type-bars">
            <div v-for="row in commerceTypes" :key="row.order_type" class="type-bar">
              <div class="type-bar-top">
                <span class="type-name">{{ orderTypeLabel(row.order_type) }}</span>
                <span class="type-amount">¥{{ Number(row.charge_total).toFixed(2) }}</span>
              </div>
              <el-progress
                :percentage="Math.round((Number(row.charge_total) / maxCharge()) * 100)"
                :show-text="false"
                :stroke-width="8"
              />
            </div>
          </div>
          <div v-else class="panel-empty">
            <el-icon><CircleCheck /></el-icon>
            <p>今日暂无收款记录</p>
          </div>

          <h4 class="sub-title">最近订单</h4>
          <div v-if="orders.length" class="order-list">
            <div v-for="o in orders.slice(0, 6)" :key="o.id" class="order-row" @click="go('/orders')">
              <span class="order-title">{{ o.title }}</span>
              <span class="order-type">{{ orderTypeLabel(o.order_type) }}</span>
              <el-tag size="small" :type="statusType(o.status)">{{ statusLabel(o.status) }}</el-tag>
              <span class="order-amount">¥{{ o.amount }}</span>
            </div>
          </div>
          <div v-else class="panel-empty">
            <el-icon><Collection /></el-icon>
            <p>暂无订单，可前往「订单收款」创建线下收款订单</p>
          </div>
          <div v-if="orders.length > 6" class="panel-foot">
            <el-button text type="primary" @click="go('/orders')">查看全部订单</el-button>
          </div>
        </template>
      </section>

      <!-- 右：通知 -->
      <section class="panel">
        <header class="panel-head">
          <div>
            <p class="eyebrow">Feed</p>
            <h3>最新通知</h3>
          </div>
          <el-button v-if="sectionState.notes" text type="primary" @click="go('/notifications')">
            查看全部 <el-icon class="el-icon--right"><ArrowRight /></el-icon>
          </el-button>
        </header>
        <div v-if="!sectionState.notes" class="panel-empty">
          <el-icon><Warning /></el-icon>
          <p>暂无通知查看权限</p>
        </div>
        <div v-else-if="notes.length" class="note-list">
          <div v-for="n in notes.slice(0, 5)" :key="n.id" class="note-row">
            <div class="note-head">
              <span class="note-type">{{ n.event_type }}</span>
              <time>{{ fmtTime(n.created_at) }}</time>
            </div>
            <div class="note-title">{{ n.title }}</div>
            <p class="note-body">{{ n.body }}</p>
          </div>
        </div>
        <div v-else class="panel-empty">
          <el-icon><Bell /></el-icon>
          <p>暂无新通知</p>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.portal {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.welcome {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 18px;
  flex-wrap: wrap;
  padding: 22px 24px;
  border-radius: 18px;
  background:
    radial-gradient(520px 160px at 92% 0%, rgba(166, 124, 82, 0.16), transparent 62%),
    linear-gradient(160deg, #fffdf9 0%, #f4efe6 100%);
  border: 1px solid var(--admin-line);
  box-shadow: var(--admin-shadow);
}

.eyebrow {
  margin: 0 0 6px;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--admin-copper);
  font-weight: 600;
}

.welcome h2 {
  margin: 0;
  font-size: 1.6rem;
  letter-spacing: -0.03em;
}

.lead {
  margin-top: 8px;
  color: var(--admin-ink-muted);
  font-size: 0.9rem;
}

.welcome-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.kpi-skeleton {
  padding: 4px 2px;
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
}

.kpi-card {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  min-width: 0;
  padding: 18px 16px 16px;
  border-radius: 16px;
  background: var(--admin-surface-elevated);
  border: 1px solid var(--admin-line);
  box-shadow: var(--admin-shadow);
}

.kpi-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  color: var(--admin-accent-strong);
  background: var(--admin-accent-soft);
  flex-shrink: 0;
}

.kpi-card[data-tone='copper'] .kpi-icon {
  color: #7a5634;
  background: rgba(166, 124, 82, 0.16);
}

.kpi-card[data-tone='slate'] .kpi-icon {
  color: #4b5563;
  background: rgba(75, 85, 99, 0.12);
}

.kpi-meta {
  min-width: 0;
  flex: 1;
  overflow: hidden;
}

.kpi-label {
  font-size: 0.78rem;
  color: var(--admin-ink-muted);
  font-weight: 600;
  letter-spacing: 0.03em;
}

.kpi-value {
  margin-top: 4px;
  font-size: 1.05rem;
  font-weight: 700;
  letter-spacing: -0.04em;
  color: var(--admin-ink);
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
  overflow: hidden;
  max-width: 100%;
}

.kpi-value[data-size='md'] {
  font-size: 0.98rem;
}

.kpi-value[data-size='sm'] {
  font-size: 0.9rem;
}

.kpi-value[data-size='xs'] {
  font-size: 0.82rem;
}

.kpi-sub {
  margin-top: 4px;
  font-size: 0.74rem;
  color: var(--admin-ink-muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.portal-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.9fr) minmax(0, 1fr);
  gap: 18px;
  align-items: start;
}

.panel {
  padding: 18px 20px;
  border-radius: 16px;
  background: var(--admin-surface-elevated);
  border: 1px solid var(--admin-line);
  box-shadow: var(--admin-shadow);
}

.panel-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.panel-head h3 {
  margin: 0;
  font-size: 1.05rem;
}

.sub-title {
  margin: 18px 0 10px;
  font-size: 0.92rem;
}

.type-bars {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.type-bar-top {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 5px;
  font-size: 0.84rem;
}

.type-name {
  color: var(--admin-ink);
  font-weight: 600;
}

.type-amount {
  color: var(--admin-ink-muted);
  font-variant-numeric: tabular-nums;
}

.order-list {
  display: flex;
  flex-direction: column;
}

.order-row {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto auto;
  align-items: center;
  gap: 12px;
  padding: 10px 8px;
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.16s ease;
}

.order-row:hover {
  background: #f4f7f5;
}

.order-title {
  font-size: 0.88rem;
  font-weight: 600;
  color: var(--admin-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.order-type {
  font-size: 0.76rem;
  color: var(--admin-ink-muted);
}

.order-amount {
  font-size: 0.86rem;
  font-weight: 700;
  color: var(--admin-ink);
  font-variant-numeric: tabular-nums;
}

.panel-foot {
  margin-top: 10px;
  text-align: center;
}

.panel-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 28px 12px;
  color: var(--admin-ink-muted);
  font-size: 0.86rem;
}

.panel-empty .el-icon {
  font-size: 30px;
  color: #c9c2b6;
}

.note-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.note-row {
  padding: 10px 8px;
  border-radius: 10px;
  transition: background 0.16s ease;
}

.note-row:hover {
  background: #f7f2ea;
}

.note-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.note-type {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: var(--admin-copper);
}

.note-head time {
  font-size: 0.72rem;
  color: var(--admin-ink-muted);
}

.note-title {
  font-size: 0.86rem;
  font-weight: 600;
  color: var(--admin-ink);
}

.note-body {
  margin-top: 3px;
  font-size: 0.8rem;
  color: var(--admin-ink-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

@media (max-width: 1100px) {
  .portal-grid {
    grid-template-columns: 1fr;
  }
}
</style>
