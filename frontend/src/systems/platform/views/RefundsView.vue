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
  return value && value.trim() ? value : '—'
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
    ['退款成功时间', String(raw.success_time || '—')],
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
    ['支付完成时间', String(raw.success_time || '—')],
    ['付款银行', String(raw.bank_type || '—')],
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

    <el-dialog v-model="detailVisible" title="退款详情" width="920px" align-center destroy-on-close>
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <header class="detail-head">
            <div>
              <p class="detail-no">{{ detail.out_refund_no }}</p>
              <p class="detail-sub">{{ detail.title }} · 原订单 {{ detail.order_no }}</p>
            </div>
            <div class="detail-amount">
              <el-tag :type="statusOf(detail.status).type">{{ statusOf(detail.status).label }}</el-tag>
              <strong>¥{{ detail.amount }}</strong>
            </div>
          </header>

          <section class="detail-block">
            <h4>退款信息</h4>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="退款金额">¥{{ detail.amount }}</el-descriptions-item>
              <el-descriptions-item label="建议退款">¥{{ detail.suggested_amount || '—' }}</el-descriptions-item>
              <el-descriptions-item label="退款方式">{{ channelLabel(detail.channel) }}</el-descriptions-item>
              <el-descriptions-item label="退款原因">{{ detail.reason || '—' }}</el-descriptions-item>
              <el-descriptions-item label="商户退款单号">{{ detail.out_refund_no }}</el-descriptions-item>
              <el-descriptions-item label="微信退款单号">{{ detail.provider_ref || '—' }}</el-descriptions-item>
              <el-descriptions-item label="原商户订单号">{{ detail.out_trade_no || detail.order?.out_trade_no || '—' }}</el-descriptions-item>
              <el-descriptions-item label="操作人">{{ detail.actor_name || '系统' }}</el-descriptions-item>
              <el-descriptions-item label="发起时间">{{ formatTime(detail.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="到账时间">{{ formatTime(detail.succeeded_at) }}</el-descriptions-item>
              <el-descriptions-item v-if="detail.error_message" label="失败原因" :span="2">
                {{ detail.error_message }}
              </el-descriptions-item>
            </el-descriptions>
          </section>

          <section class="detail-block">
            <h4>微信退款返回</h4>
            <template v-if="refundWechatSummary.length">
              <el-descriptions :column="2" border>
                <el-descriptions-item v-for="item in refundWechatSummary" :key="item[0]" :label="item[0]">
                  {{ item[1] }}
                </el-descriptions-item>
              </el-descriptions>
              <el-collapse class="raw-fold">
                <el-collapse-item title="查看微信退款原始数据" name="refund-raw">
                  <pre class="raw-json">{{ JSON.stringify(detail.wechat_payload, null, 2) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </template>
            <p v-else class="empty-line">暂无微信退款回传。处理中的退款会在打开详情时向微信核对。</p>
          </section>

          <section v-if="detail.order" class="detail-block">
            <h4>原收款订单</h4>
            <header class="detail-head inner">
              <div>
                <p class="detail-no">{{ detail.order.order_no || '—' }}</p>
                <p class="detail-sub">{{ detail.order.title }} · {{ orderTypeLabel(detail.order.order_type) }}</p>
              </div>
              <div class="detail-amount">
                <el-tag :type="orderStatusOf(detail.order.status).type">
                  {{ orderStatusOf(detail.order.status).label }}
                </el-tag>
                <strong>¥{{ detail.order.amount }}</strong>
              </div>
            </header>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="下单时间">{{ formatTime(detail.order.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="支付时间">{{ formatTime(detail.order.paid_at) }}</el-descriptions-item>
              <el-descriptions-item label="订单金额">¥{{ detail.order.original_amount || detail.order.amount }}</el-descriptions-item>
              <el-descriptions-item label="优惠">¥{{ detail.order.promotion_discount_amount || '0.00' }}</el-descriptions-item>
              <el-descriptions-item label="实付">¥{{ detail.order.amount }}</el-descriptions-item>
              <el-descriptions-item label="已退">¥{{ detail.order.refunded_amount || '0.00' }}</el-descriptions-item>
              <el-descriptions-item label="商户订单号">{{ detail.order.out_trade_no || '—' }}</el-descriptions-item>
              <el-descriptions-item label="微信支付订单号">{{ detail.order.wechat_transaction_id || '—' }}</el-descriptions-item>
              <el-descriptions-item v-if="detail.order.pickup_code" label="取餐号">{{ detail.order.pickup_code }}</el-descriptions-item>
              <el-descriptions-item v-if="detail.order.customer_note" label="顾客备注" :span="2">
                {{ detail.order.customer_note }}
              </el-descriptions-item>
            </el-descriptions>
            <el-table v-if="detail.order.payments?.length" :data="detail.order.payments" size="small" class="pay-table">
              <el-table-column label="类型" width="80">
                <template #default="{ row }">{{ payKindLabel(row.kind) }}</template>
              </el-table-column>
              <el-table-column label="渠道" width="120">
                <template #default="{ row }">{{ payChannelLabel(row.channel) }}</template>
              </el-table-column>
              <el-table-column label="金额" width="100">
                <template #default="{ row }">¥{{ row.amount }}</template>
              </el-table-column>
              <el-table-column label="时间" min-width="160">
                <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
              </el-table-column>
              <el-table-column prop="note" label="备注" min-width="120" />
            </el-table>
            <template v-if="payWechatSummary.length">
              <h5>微信收款返回</h5>
              <el-descriptions :column="1" border>
                <el-descriptions-item v-for="item in payWechatSummary" :key="item[0]" :label="item[0]">
                  {{ item[1] }}
                </el-descriptions-item>
              </el-descriptions>
              <el-collapse class="raw-fold">
                <el-collapse-item title="查看微信收款原始数据" name="pay-raw">
                  <pre class="raw-json">{{ JSON.stringify(detail.order.wechat_payload, null, 2) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </template>
          </section>

          <div class="detail-grid">
            <section class="detail-block">
              <h4>店铺</h4>
              <el-descriptions v-if="detail.order?.store" :column="1" border>
                <el-descriptions-item label="名称">{{ detail.order.store.name }}</el-descriptions-item>
                <el-descriptions-item label="状态">{{ merchantStatusLabel(detail.order.store.status) }}</el-descriptions-item>
                <el-descriptions-item label="主体">{{ showText(detail.order.store.legal_name) }}</el-descriptions-item>
                <el-descriptions-item label="地址">{{ showText(detail.order.store.business_address) }}</el-descriptions-item>
                <el-descriptions-item label="电话">{{ showText(detail.order.store.contact_phone) }}</el-descriptions-item>
                <el-descriptions-item label="营业时间">{{ showText(detail.order.store.business_hours) }}</el-descriptions-item>
              </el-descriptions>
              <p v-else class="empty-line">{{ detail.merchant_name || '—' }}</p>
            </section>
            <section class="detail-block">
              <h4>会员</h4>
              <el-descriptions v-if="detail.order?.buyer" :column="1" border>
                <el-descriptions-item label="姓名">{{ detail.order.buyer.name }}</el-descriptions-item>
                <el-descriptions-item label="手机">{{ detail.order.buyer.phone }}</el-descriptions-item>
                <el-descriptions-item label="性别">{{ genderLabel(detail.order.buyer.gender) }}</el-descriptions-item>
                <el-descriptions-item label="邮箱">{{ showText(detail.order.buyer.email) }}</el-descriptions-item>
                <el-descriptions-item label="注册时间">{{ formatTime(detail.order.buyer.created_at) }}</el-descriptions-item>
                <el-descriptions-item label="备注">{{ showText(detail.order.buyer.remark) }}</el-descriptions-item>
              </el-descriptions>
              <p v-else class="empty-line">{{ memberLabel(detail) }}</p>
            </section>
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
.detail-body {
  max-height: 72vh;
  overflow: auto;
  padding-right: 4px;
}
.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.detail-head.inner {
  margin-top: 4px;
}
.detail-no {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
}
.detail-sub {
  margin: 6px 0 0;
  color: var(--admin-ink-muted);
}
.detail-amount {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}
.detail-amount strong {
  font-size: 22px;
}
.detail-block {
  margin-bottom: 18px;
}
.detail-block h4,
.detail-block h5 {
  margin: 0 0 8px;
}
.detail-block h5 {
  margin-top: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.pay-table {
  margin-top: 10px;
}
.empty-line {
  margin: 8px 0 0;
  color: var(--admin-ink-muted);
}
.raw-fold {
  margin-top: 10px;
}
.raw-json {
  margin: 0;
  max-height: 240px;
  overflow: auto;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
