<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import { orderTypeLabel } from '../../../core/labels'

type OrderStore = {
  id: number
  name: string
  status?: string | null
  legal_name?: string | null
  business_address?: string | null
  contact_phone?: string | null
  business_hours?: string | null
  tagline?: string | null
}
type OrderBuyer = {
  id: number
  name: string
  phone: string
  gender?: string | null
  email?: string | null
  remark?: string | null
  created_at?: string | null
}
type OrderPayment = {
  id: number
  kind: string
  channel: string
  amount: string
  note?: string | null
  created_at?: string
}
type OrderDetail = {
  id: number
  order_no?: string
  title: string
  amount: string
  original_amount?: string | null
  promotion_discount_amount?: string
  refunded_amount?: string
  status: string
  order_type: string
  created_at?: string
  paid_at?: string | null
  out_trade_no?: string | null
  wechat_transaction_id?: string | null
  pickup_code?: string | null
  customer_note?: string | null
  store?: OrderStore | null
  buyer?: OrderBuyer | null
  payments?: OrderPayment[]
  wechat_payload?: Record<string, unknown> | null
}
type RefundRow = {
  id: number
  order_id: number
  order_no: string
  title: string
  merchant_id: number
  merchant_name?: string | null
  member_name?: string | null
  member_phone?: string | null
  amount: string
  channel: string
  status: string
  reason?: string | null
  out_refund_no: string
  provider_ref?: string | null
  actor_name?: string | null
  created_at?: string | null
  succeeded_at?: string | null
  error_message?: string | null
  out_trade_no?: string | null
  suggested_amount?: string | null
  force?: boolean
  wechat_payload?: Record<string, unknown> | null
  order?: OrderDetail
}

const router = useRouter()
const rows = ref<RefundRow[]>([])
const merchants = ref<{ id: number; name: string }[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<RefundRow | null>(null)
const query = reactive({
  q: '',
  status: '',
  merchant_id: undefined as number | undefined,
  createdRange: null as [string, string] | null,
})

const statusMeta: Record<string, { type: 'success' | 'warning' | 'info' | 'danger'; label: string }> = {
  succeeded: { type: 'success', label: '已到账' },
  processing: { type: 'warning', label: '处理中' },
  created: { type: 'info', label: '已发起' },
  failed: { type: 'danger', label: '失败' },
}

const orderStatusMeta: Record<string, { type: 'success' | 'warning' | 'info' | 'danger'; label: string }> = {
  paid: { type: 'success', label: '已收款' },
  pending: { type: 'warning', label: '待支付' },
  refunded: { type: 'danger', label: '已退款' },
  cancelled: { type: 'info', label: '已取消' },
}

function statusOf(status: string) {
  return statusMeta[status] || { type: 'info' as const, label: status }
}

function orderStatusOf(status: string) {
  return orderStatusMeta[status] || { type: 'info' as const, label: status }
}

function channelLabel(channel: string) {
  return (
    {
      wechat_original: '退回微信',
      offline_cash: '现金',
      offline_transfer: '转账',
      online: '线上',
    }[channel] || channel
  )
}

function payChannelLabel(channel: string) {
  return (
    {
      offline_cash: '线下现金',
      offline_transfer: '线下转账',
      online: '线上支付',
      wechat_original: '微信原路',
    }[channel] || channel
  )
}

function payKindLabel(kind: string) {
  return { charge: '收款', refund: '退款' }[kind] || kind
}

function memberLabel(row: RefundRow) {
  if (!row.member_name && !row.member_phone) return '—'
  return [row.member_name, row.member_phone].filter(Boolean).join(' ')
}

function formatTime(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

function genderLabel(value?: string | null) {
  return { male: '男', female: '女', unknown: '未填' }[value || ''] || value || '—'
}

function merchantStatusLabel(status?: string | null) {
  return { active: '营业中', preparing: '筹备中', disabled: '已停用' }[status || ''] || status || '—'
}

function showText(value?: string | null) {
  return value && value.trim() ? value : ''
}

function fenYuan(value: unknown) {
  if (value == null || value === '') return '—'
  const n = Number(value)
  if (!Number.isFinite(n)) return '—'
  return `¥${(n / 100).toFixed(2)}`
}

function wechatRefundStatus(status: string) {
  return (
    {
      SUCCESS: '退款成功',
      PROCESSING: '退款处理中',
      CLOSED: '退款关闭',
      ABNORMAL: '退款异常',
    }[status] || status || '—'
  )
}

function wechatRefundChannel(channel: string) {
  return (
    {
      ORIGINAL: '原路退回',
      BALANCE: '退回余额',
      OTHER_BALANCE: '退回其他余额',
      OTHER_BANKCARD: '退回银行卡',
    }[channel] || channel || '—'
  )
}

function fundsAccountLabel(account: string) {
  return (
    {
      UNSETTLED: '未结算资金',
      AVAILABLE: '可用余额',
      UNAVAILABLE: '不可用余额',
      OPERATION: '运营账户',
      BASIC: '基本账户',
    }[account] || account || '—'
  )
}

const refundWechatSummary = computed(() => {
  const raw = detail.value?.wechat_payload
  if (!raw) return []
  const amount = raw.amount as { refund?: number; payer_refund?: number } | undefined
  const status = String(raw.status || raw.refund_status || '')
  return [
    ['退款状态', wechatRefundStatus(status)],
    ['退款入账账户', String(raw.user_received_account || '—')],
    ['退款成功时间', formatTime(raw.success_time ? String(raw.success_time) : null)],
    ['微信退款单号', String(raw.refund_id || detail.value?.provider_ref || '—')],
    ['微信支付订单号', String(raw.transaction_id || '—')],
    ['商户退款单号', String(raw.out_refund_no || detail.value?.out_refund_no || '—')],
    ['商户订单号', String(raw.out_trade_no || detail.value?.out_trade_no || '—')],
    ['退款渠道', wechatRefundChannel(String(raw.channel || ''))],
    ['资金账户', fundsAccountLabel(String(raw.funds_account || ''))],
    ['退款金额', fenYuan(amount?.payer_refund ?? amount?.refund)],
  ]
})

const payWechatSummary = computed(() => {
  const raw = detail.value?.order?.wechat_payload
  if (!raw) return []
  const amount = raw.amount as { total?: number; payer_total?: number } | undefined
  const payer = raw.payer as { openid?: string } | undefined
  return [
    ['交易状态', String(raw.trade_state_desc || raw.trade_state || '—')],
    ['支付完成时间', formatTime(raw.success_time ? String(raw.success_time) : null)],
    ['付款银行', String(raw.bank_type || '') === 'OTHERS' ? '零钱或其他' : String(raw.bank_type || '—')],
    ['用户支付', fenYuan(amount?.payer_total ?? amount?.total)],
    ['付款人 OpenID', String(payer?.openid || '—')],
  ]
})

async function loadMerchants() {
  try {
    const { data } = await http.get<{ id: number; name: string }[]>('/merchants')
    merchants.value = data
  } catch {
    merchants.value = []
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<{ items: RefundRow[]; total: number }>('/orders/refunds', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        q: query.q || undefined,
        status: query.status || undefined,
        merchant_id: query.merchant_id,
        created_from: query.createdRange?.[0],
        created_to: query.createdRange?.[1],
      },
    })
    rows.value = data.items
    total.value = data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  load()
}

function resetSearch() {
  query.q = ''
  query.status = ''
  query.merchant_id = undefined
  query.createdRange = null
  search()
}

async function openDetail(row: RefundRow) {
  detail.value = row
  detailVisible.value = true
  detailLoading.value = true
  try {
    const { data } = await http.get<RefundRow>(`/orders/refunds/${row.id}`)
    detail.value = data
    const index = rows.value.findIndex((item) => item.id === row.id)
    if (index >= 0) {
      rows.value[index] = { ...rows.value[index], ...data }
    }
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载退款详情失败')
  } finally {
    detailLoading.value = false
  }
}

onMounted(() => {
  loadMerchants()
  load()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>退款记录</h3>
      <el-button @click="router.push('/orders')">返回订单收款</el-button>
    </div>

    <div class="filters">
      <el-input
        v-model="query.q"
        clearable
        placeholder="订单号 / 标题 / 会员 / 退款单号"
        style="width: 240px"
        @keyup.enter="search"
      />
      <el-select v-model="query.status" clearable placeholder="状态" style="width: 140px">
        <el-option label="已到账" value="succeeded" />
        <el-option label="处理中" value="processing" />
        <el-option label="已发起" value="created" />
        <el-option label="失败" value="failed" />
      </el-select>
      <el-select v-model="query.merchant_id" clearable placeholder="商户" style="width: 180px">
        <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-date-picker
        v-model="query.createdRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="退款开始"
        end-placeholder="退款结束"
        range-separator="至"
        style="width: 260px"
      />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="order_no" label="订单号" min-width="210" />
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column label="会员" min-width="160">
        <template #default="{ row }">{{ memberLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="商户" width="140">
        <template #default="{ row }">{{ row.merchant_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="退款金额" width="110">
        <template #default="{ row }"><b>¥{{ row.amount }}</b></template>
      </el-table-column>
      <el-table-column label="退款方式" width="110">
        <template #default="{ row }">{{ channelLabel(row.channel) }}</template>
      </el-table-column>
      <el-table-column label="原因" min-width="140">
        <template #default="{ row }">{{ row.reason || '—' }}</template>
      </el-table-column>
      <el-table-column prop="out_refund_no" label="退款单号" min-width="180" />
      <el-table-column label="操作人" width="110">
        <template #default="{ row }">{{ row.actor_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="发起时间" min-width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="到账时间" min-width="170">
        <template #default="{ row }">{{ formatTime(row.succeeded_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusOf(row.status).type" size="small">{{ statusOf(row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" @click="openDetail(row)">详情</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="load"
        @size-change="
          () => {
            page = 1
            load()
          }
        "
      />
    </div>

    <el-dialog v-model="detailVisible" title="退款详情" width="840px" align-center destroy-on-close>
      <div v-loading="detailLoading" class="bill">
        <template v-if="detail">
          <header class="bill-hero">
            <div>
              <p class="bill-kicker">{{ detail.merchant_name || '—' }} · {{ channelLabel(detail.channel) }}</p>
              <h3>{{ detail.title }}</h3>
              <p class="bill-no">{{ detail.out_refund_no }}</p>
            </div>
            <div class="bill-sum">
              <span class="bill-status" :data-tone="statusOf(detail.status).type">{{ statusOf(detail.status).label }}</span>
              <strong>¥{{ detail.amount }}</strong>
              <span>退款</span>
            </div>
          </header>

          <div class="bill-metrics">
            <div>
              <span>建议退款</span>
              <b>¥{{ detail.suggested_amount || '—' }}</b>
            </div>
            <div>
              <span>原因</span>
              <b>{{ detail.reason || '—' }}</b>
            </div>
            <div>
              <span>操作人</span>
              <b>{{ detail.actor_name || '系统' }}</b>
            </div>
            <div>
              <span>发起</span>
              <b>{{ formatTime(detail.created_at) }}</b>
            </div>
            <div>
              <span>到账</span>
              <b>{{ formatTime(detail.succeeded_at) }}</b>
            </div>
          </div>
          <p v-if="detail.error_message" class="bill-note danger">{{ detail.error_message }}</p>

          <section class="bill-card">
            <h4>微信退款返回</h4>
            <dl v-if="refundWechatSummary.length" class="kv">
              <div v-for="item in refundWechatSummary" :key="item[0]">
                <dt>{{ item[0] }}</dt>
                <dd>{{ item[1] }}</dd>
              </div>
            </dl>
            <p v-else class="empty-line">暂无微信退款回传。处理中的退款会在打开详情时向微信核对。</p>
            <el-collapse v-if="detail.wechat_payload" class="raw-fold">
              <el-collapse-item title="查看微信退款原始数据" name="refund-raw">
                <pre class="raw-json">{{ JSON.stringify(detail.wechat_payload, null, 2) }}</pre>
              </el-collapse-item>
            </el-collapse>
          </section>

          <section v-if="detail.order" class="bill-card">
            <h4>原收款订单</h4>
            <div class="origin">
              <div>
                <b>{{ detail.order.title }}</b>
                <small>{{ detail.order.order_no }} · {{ orderTypeLabel(detail.order.order_type) }}</small>
              </div>
              <div class="origin-sum">
                <span class="bill-status" :data-tone="orderStatusOf(detail.order.status).type">
                  {{ orderStatusOf(detail.order.status).label }}
                </span>
                <strong>¥{{ detail.order.amount }}</strong>
              </div>
            </div>
            <dl class="kv">
              <div>
                <dt>下单</dt>
                <dd>{{ formatTime(detail.order.created_at) }}</dd>
              </div>
              <div>
                <dt>支付</dt>
                <dd>{{ formatTime(detail.order.paid_at) }}</dd>
              </div>
              <div>
                <dt>优惠</dt>
                <dd>¥{{ detail.order.promotion_discount_amount || '0.00' }}</dd>
              </div>
              <div>
                <dt>已退</dt>
                <dd>¥{{ detail.order.refunded_amount || '0.00' }}</dd>
              </div>
            </dl>
            <ul v-if="detail.order.payments?.length" class="ledger">
              <li v-for="row in detail.order.payments" :key="row.id">
                <i :data-kind="row.kind" />
                <div>
                  <b>{{ payKindLabel(row.kind) }} · {{ payChannelLabel(row.channel) }}</b>
                  <small>{{ formatTime(row.created_at) }}<template v-if="row.note"> · {{ row.note }}</template></small>
                </div>
                <em>¥{{ row.amount }}</em>
              </li>
            </ul>
            <div v-if="detail.order.out_trade_no || detail.order.wechat_transaction_id" class="id-row">
              <span v-if="detail.order.out_trade_no">商户订单号 <code>{{ detail.order.out_trade_no }}</code></span>
              <span v-if="detail.order.wechat_transaction_id">微信支付订单号 <code>{{ detail.order.wechat_transaction_id }}</code></span>
            </div>
            <template v-if="payWechatSummary.length">
              <h4 class="subhead">微信收款返回</h4>
              <dl class="kv">
                <div v-for="item in payWechatSummary" :key="item[0]">
                  <dt>{{ item[0] }}</dt>
                  <dd>{{ item[1] }}</dd>
                </div>
              </dl>
            </template>
          </section>

          <div class="people">
            <article class="bill-card">
              <h4>店铺</h4>
              <template v-if="detail.order?.store">
                <strong>{{ detail.order.store.name }}</strong>
                <p class="people-sub">{{ merchantStatusLabel(detail.order.store.status) }}</p>
                <ul>
                  <li v-if="showText(detail.order.store.legal_name)"><span>主体</span>{{ detail.order.store.legal_name }}</li>
                  <li v-if="showText(detail.order.store.business_address)"><span>地址</span>{{ detail.order.store.business_address }}</li>
                  <li v-if="showText(detail.order.store.contact_phone)"><span>电话</span>{{ detail.order.store.contact_phone }}</li>
                  <li v-if="showText(detail.order.store.business_hours)"><span>营业</span>{{ detail.order.store.business_hours }}</li>
                </ul>
              </template>
              <p v-else class="empty-line">{{ detail.merchant_name || '—' }}</p>
            </article>
            <article class="bill-card">
              <h4>会员</h4>
              <template v-if="detail.order?.buyer">
                <strong>{{ detail.order.buyer.name }}</strong>
                <p class="people-sub">{{ detail.order.buyer.phone }} · {{ genderLabel(detail.order.buyer.gender) }}</p>
                <ul>
                  <li v-if="showText(detail.order.buyer.email)"><span>邮箱</span>{{ detail.order.buyer.email }}</li>
                  <li><span>注册</span>{{ formatTime(detail.order.buyer.created_at) }}</li>
                  <li v-if="showText(detail.order.buyer.remark)"><span>备注</span>{{ detail.order.buyer.remark }}</li>
                </ul>
              </template>
              <p v-else class="empty-line">{{ memberLabel(detail) }}</p>
            </article>
          </div>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.toolbar h3 {
  margin: 0;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.bill {
  max-height: 72vh;
  overflow: auto;
  padding-right: 2px;
}
.bill-hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  padding: 4px 2px 16px;
}
.bill-kicker,
.people-sub,
.empty-line {
  margin: 0;
  color: var(--admin-ink-muted);
  font-size: 13px;
}
.bill-hero h3 {
  margin: 4px 0 0;
  font-size: 22px;
  line-height: 1.3;
}
.bill-no {
  margin: 6px 0 0;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 13px;
  color: var(--admin-ink-muted);
}
.bill-sum {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 4px;
  min-width: 120px;
}
.bill-sum strong {
  font-size: 32px;
  line-height: 1;
  letter-spacing: -0.03em;
}
.bill-sum > span:last-child {
  color: var(--admin-ink-muted);
  font-size: 12px;
}
.bill-status {
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 12px;
  background: #efe9e0;
  color: #44403c;
}
.bill-status[data-tone='success'] {
  background: #e7f6ee;
  color: #0f7b45;
}
.bill-status[data-tone='warning'] {
  background: #fff1e4;
  color: #c2410c;
}
.bill-status[data-tone='danger'] {
  background: #fdecec;
  color: #b42318;
}
.bill-metrics {
  display: grid;
  grid-template-columns: 0.8fr 1fr 0.8fr 1.2fr 1.2fr;
  gap: 8px;
  margin-bottom: 14px;
}
.bill-metrics div {
  padding: 10px 12px;
  border-radius: 12px;
  background: #f7f2ea;
}
.bill-metrics span {
  display: block;
  margin-bottom: 4px;
  color: var(--admin-ink-muted);
  font-size: 12px;
}
.bill-metrics b {
  font-size: 13px;
  font-weight: 600;
}
.bill-note {
  margin: 0 0 14px;
  color: #44403c;
  font-size: 13px;
}
.bill-note.danger {
  color: #b42318;
}
.bill-card {
  margin-bottom: 12px;
  padding: 14px 16px;
  border: 1px solid #efe9e0;
  border-radius: 14px;
  background: #fff;
}
.bill-card h4 {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: #57534e;
}
.subhead {
  margin-top: 14px;
}
.origin {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.origin b {
  display: block;
}
.origin small {
  color: var(--admin-ink-muted);
}
.origin-sum {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
}
.origin-sum strong {
  font-size: 20px;
}
.ledger {
  list-style: none;
  margin: 12px 0 0;
  padding: 0;
}
.ledger li {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 0;
}
.ledger li + li {
  border-top: 1px solid #f3eee6;
}
.ledger i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #0f7b45;
  flex: none;
}
.ledger i[data-kind='refund'] {
  background: #b42318;
}
.ledger div {
  flex: 1;
  min-width: 0;
}
.ledger b {
  display: block;
  font-size: 14px;
}
.ledger small,
.id-row {
  color: var(--admin-ink-muted);
  font-size: 12px;
}
.ledger em {
  font-style: normal;
  font-weight: 650;
}
.id-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}
.kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
  margin: 0;
}
.kv dt {
  margin-bottom: 2px;
  color: var(--admin-ink-muted);
  font-size: 12px;
}
.kv dd,
.id-row code {
  margin: 0;
  font-size: 13px;
  word-break: break-all;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.people {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.people strong {
  display: block;
  font-size: 16px;
}
.people ul {
  list-style: none;
  margin: 10px 0 0;
  padding: 0;
}
.people li {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  font-size: 13px;
}
.people li span {
  flex: none;
  width: 36px;
  color: var(--admin-ink-muted);
}
.raw-fold {
  margin-top: 8px;
  border: none;
}
.raw-json {
  margin: 0;
  max-height: 220px;
  overflow: auto;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
