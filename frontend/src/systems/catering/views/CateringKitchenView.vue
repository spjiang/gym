<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'
import { diningStatusLabel } from '../../../core/labels'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'
import CateringDeskSwitch from '../components/CateringDeskSwitch.vue'

type Merchant = { id: number; name: string; subsystem_codes: string[] }
type TicketItem = { menu_item_id: number; name: string; quantity: number; line_amount: string | number }
type Ticket = {
  id: number
  merchant_id: number
  pickup_code?: string | null
  dining_status: string
  amount: string | number
  title: string
  table_no?: string | null
  customer_note?: string | null
  member_name?: string | null
  created_at: string
  items: TicketItem[]
}

const POLL_MS = 3000

const route = useRoute()
const merchants = ref<Merchant[]>([])
const tickets = ref<Ticket[]>([])
const booted = ref(false)
const syncing = ref(false)
const syncErr = ref('')
const lastSyncAt = ref<number | null>(null)
const now = ref(Date.now())
const busyId = ref<number | null>(null)
const freshIds = ref<Set<number>>(new Set())
const seenIds = new Set<number>()
const { merchantId } = useOpsMerchant(() => void refresh(true))

let pollTimer: number | null = null
let clockTimer: number | null = null
let inFlight = false
let pendingForce = false
let revealedTicketId = 0

const cateringMerchants = () =>
  merchants.value.filter((m) => (m.subsystem_codes || []).includes('catering'))

const preparing = computed(() =>
  tickets.value.filter((t) => (t.dining_status || 'preparing') !== 'ready'),
)
const ready = computed(() => tickets.value.filter((t) => t.dining_status === 'ready'))

const liveLabel = computed(() => {
  if (syncErr.value) return '同步失败，将自动重试'
  if (!lastSyncAt.value) return '正在接入订单…'
  const sec = Math.max(0, Math.floor((now.value - lastSyncAt.value) / 1000))
  return sec <= 2 ? '实时接入中' : `${sec} 秒前已同步`
})

function waitText(iso: string) {
  const mins = Math.max(0, Math.floor((now.value - new Date(iso).getTime()) / 60000))
  if (mins < 1) return '刚刚流入'
  if (mins < 60) return `已等 ${mins} 分钟`
  return `已等 ${Math.floor(mins / 60)} 小时 ${mins % 60} 分`
}

function isFresh(id: number) {
  return freshIds.value.has(id)
}

function markFresh(ids: number[]) {
  if (!ids.length) return
  const next = new Set(freshIds.value)
  for (const id of ids) next.add(id)
  freshIds.value = next
  window.setTimeout(() => {
    const trimmed = new Set(freshIds.value)
    for (const id of ids) trimmed.delete(id)
    freshIds.value = trimmed
  }, 12000)
}

function playNewTicketChime() {
  try {
    const AudioCtx = window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    const ctx = new AudioCtx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.type = 'sine'
    osc.frequency.value = 880
    gain.gain.value = 0.08
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.start()
    osc.stop(ctx.currentTime + 0.16)
    window.setTimeout(() => void ctx.close(), 300)
  } catch {
    /* 部分浏览器拦截自动播放 */
  }
}

async function refresh(force = false) {
  if (inFlight) {
    if (force) pendingForce = true
    return
  }
  if (document.hidden && !force) return
  inFlight = true
  if (!booted.value) syncing.value = true
  try {
    if (!merchants.value.length) {
      const { data } = await http.get('/merchants')
      merchants.value = data
    }
    const { data } = await http.get<Ticket[]>('/catering/kitchen', {
      params: { merchant_id: merchantId.value },
    })
    const incoming = booted.value ? data.filter((t) => !seenIds.has(t.id)).map((t) => t.id) : []
    tickets.value = data
    for (const t of data) seenIds.add(t.id)
    if (incoming.length) {
      markFresh(incoming)
      playNewTicketChime()
    }
    lastSyncAt.value = Date.now()
    syncErr.value = ''
    booted.value = true
    await revealQueryTicket()
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : '出餐看板加载失败'
    syncErr.value = message
    if (!booted.value) ElMessage.error(message)
  } finally {
    inFlight = false
    syncing.value = false
    if (pendingForce) {
      pendingForce = false
      void refresh(true)
    }
  }
}

async function markReady(row: Ticket) {
  busyId.value = row.id
  try {
    await http.post(`/catering/orders/${row.id}/ready`)
    ElMessage.success(`取餐号 ${row.pickup_code || row.id} 已出餐，待取餐`)
    await refresh(true)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '出餐失败')
  } finally {
    busyId.value = null
  }
}

async function markComplete(row: Ticket) {
  try {
    await ElMessageBox.confirm(
      `确认完成取餐？取餐号 ${row.pickup_code || row.id}`,
      '完成取餐',
      { type: 'warning', confirmButtonText: '确认完成', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  busyId.value = row.id
  try {
    await http.post(`/catering/orders/${row.id}/complete`)
    ElMessage.success(`取餐号 ${row.pickup_code || row.id} 已完成`)
    await refresh(true)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '完成失败')
  } finally {
    busyId.value = null
  }
}

async function undoTicket(row: Ticket) {
  busyId.value = row.id
  try {
    await http.post(`/catering/orders/${row.id}/undo`)
    ElMessage.success(`已回退取餐号 ${row.pickup_code || row.id}`)
    await refresh(true)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '回退失败')
  } finally {
    busyId.value = null
  }
}

function ticketFromQuery() {
  const raw = route.query.ticket
  const n = Number(Array.isArray(raw) ? raw[0] : raw)
  return Number.isFinite(n) && n > 0 ? n : 0
}

async function revealQueryTicket() {
  const id = ticketFromQuery()
  if (!id || revealedTicketId === id) return
  if (!tickets.value.some((t) => t.id === id)) return
  revealedTicketId = id
  markFresh([id])
  await nextTick()
  document.getElementById(`ticket-${id}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

function onVisibility() {
  if (!document.hidden) void refresh(true)
}

watch(
  () => route.query.ticket,
  () => {
    void revealQueryTicket()
  },
)

onMounted(() => {
  void refresh(true)
  pollTimer = window.setInterval(() => void refresh(), POLL_MS)
  clockTimer = window.setInterval(() => {
    now.value = Date.now()
  }, 1000)
  document.addEventListener('visibilitychange', onVisibility)
})
onUnmounted(() => {
  if (pollTimer != null) window.clearInterval(pollTimer)
  if (clockTimer != null) window.clearInterval(clockTimer)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<template>
  <div class="kds">
    <CateringDeskSwitch :queue-count="tickets.length" />
    <div class="toolbar">
      <p class="live" :class="{ 'live--err': !!syncErr, 'live--on': !syncErr && booted }">
        <i />
        {{ liveLabel }}
        <span v-if="syncing && !booted">首次加载中…</span>
      </p>
      <el-form inline>
        <el-form-item label="餐饮商户">
          <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 220px">
            <el-option v-for="m in cateringMerchants()" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button @click="refresh(true)">立即刷新</el-button>
        </el-form-item>
      </el-form>
    </div>

    <el-alert v-if="syncErr && booted" type="warning" :closable="false" :title="syncErr" style="margin-bottom: 12px" />

    <div v-if="!booted && syncing" class="empty">正在接入已支付订单…</div>

    <div v-else class="board">
      <section class="col">
        <header class="col__head col__head--prep">
          制作中 <b>{{ preparing.length }}</b>
        </header>
        <article
          v-for="t in preparing"
          :key="t.id"
          :id="`ticket-${t.id}`"
          class="ticket ticket--prep"
          :class="{ 'ticket--new': isFresh(t.id) }"
        >
          <div class="ticket__top">
            <div class="ticket__code">{{ t.pickup_code || `#${t.id}` }}</div>
            <span v-if="isFresh(t.id)" class="badge">新单</span>
          </div>
          <div class="ticket__meta">
            {{ t.table_no ? `桌 ${t.table_no} · ` : '' }}{{ waitText(t.created_at) }} · {{ t.member_name || '散客' }} · ¥{{ t.amount }}
          </div>
          <ul class="ticket__items">
            <li v-for="(it, i) in t.items" :key="i">{{ it.name }} ×{{ it.quantity }}</li>
          </ul>
          <p v-if="t.customer_note" class="ticket__note">备注：{{ t.customer_note }}</p>
          <el-button type="primary" :loading="busyId === t.id" @click="markReady(t)">出餐 · 待取</el-button>
        </article>
        <div v-if="!preparing.length" class="empty">暂无制作中订单，支付成功后会自动出现</div>
      </section>

      <section class="col">
        <header class="col__head col__head--ready">
          待取餐 <b>{{ ready.length }}</b>
        </header>
        <article
          v-for="t in ready"
          :key="t.id"
          :id="`ticket-${t.id}`"
          class="ticket ticket--ready"
          :class="{ 'ticket--new': isFresh(t.id) }"
        >
          <div class="ticket__top">
            <div class="ticket__code">{{ t.pickup_code || `#${t.id}` }}</div>
            <span class="badge badge--ready">{{ diningStatusLabel(t.dining_status) }}</span>
          </div>
          <div class="ticket__meta">
            {{ t.table_no ? `桌 ${t.table_no} · ` : '' }}{{ waitText(t.created_at) }} · {{ t.member_name || '散客' }} · ¥{{ t.amount }}
          </div>
          <ul class="ticket__items">
            <li v-for="(it, i) in t.items" :key="i">{{ it.name }} ×{{ it.quantity }}</li>
          </ul>
          <p v-if="t.customer_note" class="ticket__note">备注：{{ t.customer_note }}</p>
          <div class="ticket__actions">
            <el-button type="success" :loading="busyId === t.id" @click="markComplete(t)">完成取餐</el-button>
            <el-button :loading="busyId === t.id" @click="undoTicket(t)">回退制作</el-button>
          </div>
        </article>
        <div v-if="!ready.length" class="empty">暂无待取餐订单</div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0;
}
.hint {
  margin: 4px 0 6px;
  color: var(--admin-ink-muted);
  font-size: 13px;
}
.live {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 13px;
  color: var(--admin-ink-muted);
}
.live i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #9ca3af;
}
.live--on i {
  background: #16a34a;
  box-shadow: 0 0 0 4px rgba(22, 163, 74, 0.18);
  animation: pulse 1.6s ease-out infinite;
}
.live--err {
  color: #b45309;
}
.live--err i {
  background: #d97706;
}
.board {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  align-items: start;
}
.col {
  min-height: 320px;
  padding: 12px;
  border-radius: 12px;
  background: #f7f4ef;
}
.col__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 700;
  margin-bottom: 12px;
}
.col__head--prep {
  color: #b45309;
}
.col__head--ready {
  color: #0f766e;
}
.ticket {
  padding: 14px;
  border-radius: 12px;
  background: #fff;
  margin-bottom: 12px;
  box-shadow: 0 1px 0 rgba(28, 25, 23, 0.06);
}
.ticket--prep {
  border-left: 4px solid #d97706;
}
.ticket--ready {
  border-left: 4px solid #0f766e;
}
.ticket--new {
  animation: inflow 0.45s ease-out;
  box-shadow: 0 0 0 2px rgba(243, 107, 33, 0.35);
}
.ticket__top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
}
.ticket__code {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: 0.06em;
  line-height: 1.1;
}
.badge {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 700;
  color: #9a3412;
  background: #ffedd5;
  border-radius: 999px;
  padding: 2px 8px;
}
.badge--ready {
  color: #0f766e;
  background: #ccfbf1;
}
.ticket__meta {
  margin: 4px 0 8px;
  color: var(--admin-ink-muted);
  font-size: 13px;
}
.ticket__items {
  margin: 0 0 10px;
  padding-left: 18px;
}
.ticket__note {
  margin: 0 0 10px;
  font-size: 13px;
  color: #9a3412;
}
.ticket__actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ticket .el-button {
  width: 100%;
}
.empty {
  color: var(--admin-ink-muted);
  font-size: 13px;
  padding: 24px 0;
  text-align: center;
}
@keyframes pulse {
  0% {
    box-shadow: 0 0 0 0 rgba(22, 163, 74, 0.35);
  }
  100% {
    box-shadow: 0 0 0 8px rgba(22, 163, 74, 0);
  }
}
@keyframes inflow {
  from {
    transform: translateY(-8px);
    opacity: 0.2;
  }
  to {
    transform: none;
    opacity: 1;
  }
}
@media (max-width: 900px) {
  .board {
    grid-template-columns: 1fr;
  }
}
</style>
