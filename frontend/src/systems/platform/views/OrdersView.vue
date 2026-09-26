<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import RowActions from '../../../core/components/RowActions.vue'
import { ORDER_TYPE_LABELS, orderTypeLabel as mapOrderType } from '../../../core/labels'

const router = useRouter()

type MemberBrief = { id: number; name: string; phone: string }
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
type Order = {
  id: number
  order_no?: string
  title: string
  amount: string
  original_amount?: string | null
  promotion_discount_amount?: string
  refunded_amount?: string
  status: string
  merchant_id: number
  merchant_name?: string | null
  order_type: string
  member_id?: number | null
  pickup_code?: string | null
  customer_note?: string | null
  dining_status?: string | null
  created_at?: string
  member?: MemberBrief | null
  out_trade_no?: string | null
  wechat_transaction_id?: string | null
  paid_at?: string | null
  store?: OrderStore | null
  buyer?: OrderBuyer | null
  payments?: OrderPayment[]
  wechat_payload?: Record<string, unknown> | null
}
type Merchant = { id: number; name: string; subsystem_codes: string[] }
type OrderTypeOpt = { value: string; label: string }
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const orders = ref<Order[]>([])
const merchants = ref<Merchant[]>([])
const allowedTypes = ref<OrderTypeOpt[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dialogVisible = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref<Order | null>(null)
const submitting = ref(false)
const exporting = ref(false)
const formRef = ref<FormInstance>()

const query = reactive({
  q: '',
  status: '' as string,
  merchant_id: undefined as number | undefined,
  order_type: '' as string,
  createdRange: null as [string, string] | null,
  paidRange: null as [string, string] | null,
})

const form = reactive({
  merchant_id: undefined as number | undefined,
  title: '',
  amount: '99.00',
  order_type: 'retail',
})

const rules: FormRules = {
  merchant_id: [{ required: true, message: '请选择商户', trigger: 'change' }],
  order_type: [{ required: true, message: '请选择订单类型', trigger: 'change' }],
  title: [{ required: true, message: '请填写订单标题', trigger: 'blur' }],
  amount: [
    { required: true, message: '请填写金额', trigger: 'blur' },
    {
      validator: (_r, v: string, cb) => {
        const n = Number(v)
        if (!Number.isFinite(n) || n <= 0) cb(new Error('金额必须大于 0'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

const titlePlaceholder = computed(() => {
  const t = form.order_type
  if (t === 'dining') return '如：吧台现结 · 啤酒两杯'
  if (t === 'membership') return '如：标准月卡办卡'
  if (t === 'pt') return '如：私教课时费'
  if (t === 'group') return '如：团课补差'
  return '如：零售商品收款'
})

function merchantName(row: Pick<Order, 'merchant_id' | 'merchant_name'>) {
  if (row.merchant_name) return row.merchant_name
  return merchants.value.find((m) => m.id === row.merchant_id)?.name || `商户 #${row.merchant_id}`
}

function memberLabel(row: Order) {
  if (row.member) return `${row.member.name} ${row.member.phone}`
  if (row.member_id) return `#${row.member_id}`
  return '—'
}

function statusMeta(status: string) {
  return {
    paid: { type: 'success' as const, label: '已收款' },
    pending: { type: 'warning' as const, label: '待支付' },
    refunded: { type: 'danger' as const, label: '已退款' },
    cancelled: { type: 'info' as const, label: '已取消' },
  }[status] || { type: 'info' as const, label: status }
}

function orderTypeLabel(t: string) {
  return allowedTypes.value.find((o) => o.value === t)?.label || mapOrderType(t)
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

function merchantStatusLabel(status?: string | null) {
  return { active: '营业中', preparing: '筹备中', disabled: '已停用' }[status || ''] || status || '—'
}

function showText(value?: string | null) {
  return value && value.trim() ? value : ''
}

function bankLabel(code: string) {
  if (!code) return '—'
  if (code === 'OTHERS') return '零钱或其他'
  return code
}

const wechatSummary = computed(() => {
  const raw = detail.value?.wechat_payload
  if (!raw) return []
  const amount = raw.amount as { total?: number; payer_total?: number } | undefined
  const payer = raw.payer as { openid?: string } | undefined
  const fen = amount?.payer_total ?? amount?.total
  return [
    ['交易状态', String(raw.trade_state_desc || raw.trade_state || '—')],
    ['支付完成时间', formatTime(raw.success_time ? String(raw.success_time) : null)],
    ['付款银行', bankLabel(String(raw.bank_type || ''))],
    ['用户支付', fen == null ? '—' : `¥${(Number(fen) / 100).toFixed(2)}`],
    ['付款人 OpenID', String(payer?.openid || '—')],
  ]
})

async function loadOrderTypes(merchantId: number) {
  const { data } = await http.get(`/merchants/${merchantId}/order-types`)
  allowedTypes.value = data
  if (!allowedTypes.value.some((t) => t.value === form.order_type)) {
    form.order_type = allowedTypes.value[0]?.value || 'retail'
  }
}

async function load() {
  loading.value = true
  try {
    const [o, m] = await Promise.all([
      http.get<Page<Order>>('/orders', {
        params: {
          page: page.value,
          page_size: pageSize.value,
          q: query.q.trim() || undefined,
          status: query.status || undefined,
          merchant_id: query.merchant_id,
          order_type: query.order_type || undefined,
          created_from: query.createdRange?.[0],
          created_to: query.createdRange?.[1],
          paid_from: query.paidRange?.[0],
          paid_to: query.paidRange?.[1],
        },
      }),
      http.get('/merchants'),
    ])
    orders.value = o.data.items
    total.value = o.data.total
    merchants.value = m.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function resetSearch() {
  query.q = ''
  query.status = ''
  query.merchant_id = undefined
  query.order_type = ''
  query.createdRange = null
  query.paidRange = null
  page.value = 1
  void load()
}

async function openDetail(row: Order) {
  detail.value = row
  detailVisible.value = true
  detailLoading.value = true
  try {
    const { data } = await http.get<Order>(`/orders/${row.id}`)
    detail.value = data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载订单详情失败')
  } finally {
    detailLoading.value = false
  }
}

async function openDialog() {
  form.title = ''
  form.amount = '99.00'
  form.merchant_id = merchants.value[0]?.id
  formRef.value?.clearValidate()
  if (form.merchant_id) {
    try {
      await loadOrderTypes(form.merchant_id)
    } catch (e: unknown) {
      ElMessage.error(e instanceof Error ? e.message : '加载订单类型失败')
      return
    }
  } else {
    allowedTypes.value = []
  }
  dialogVisible.value = true
}

watch(
  () => form.merchant_id,
  async (id) => {
    if (!id || !dialogVisible.value) return
    try {
      await loadOrderTypes(id)
    } catch (e: unknown) {
      ElMessage.error(e instanceof Error ? e.message : '加载订单类型失败')
    }
  },
)

async function create() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!allowedTypes.value.length) {
    ElMessage.warning('该商户未关联业态，无法创建业务订单')
    return
  }
  submitting.value = true
  try {
    await http.post('/orders', {
      title: form.title.trim(),
      amount: form.amount,
      order_type: form.order_type,
      merchant_id: form.merchant_id,
    })
    ElMessage.success('订单已创建')
    dialogVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

async function payOffline(row: Order) {
  try {
    await http.post(`/orders/${row.id}/pay/offline`, { channel: 'offline_cash' })
    ElMessage.success('线下收款成功')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '收款失败')
  }
}

async function refund(row: Order) {
  try {
    const { data: preview } = await http.get<{
      suggested_amount: string
      refundable_balance: string
      basis: string
      unused?: boolean
    }>(`/orders/${row.id}/refund/preview`)
    const amount = preview.suggested_amount || preview.refundable_balance
    await ElMessageBox.confirm(
      `建议退 ¥${amount}（${preview.basis}${preview.unused ? '·未使用' : ''}）。确认退款？`,
      '订单退款',
      { type: 'warning', confirmButtonText: '退款', cancelButtonText: '取消' },
    )
    await http.post(`/orders/${row.id}/refund`, {
      amount,
      channel: 'wechat_original',
      reason: '管理端退款',
    })
    ElMessage.success('退款已提交，可在「退款记录」查看')
    await load()
  } catch (e: unknown) {
    if (e === 'cancel') return
    ElMessage.error(e instanceof Error ? e.message : '退款失败')
  }
}

function downloadBlob(data: Blob, filename: string) {
  const url = URL.createObjectURL(data)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function fileStamp() {
  const date = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}${pad(date.getMonth() + 1)}${pad(date.getDate())}`
}

async function exportExcel() {
  exporting.value = true
  try {
    const { data } = await http.get<Blob>('/orders/export.xlsx', {
      params: {
        q: query.q.trim() || undefined,
        status: query.status || undefined,
        merchant_id: query.merchant_id,
        order_type: query.order_type || undefined,
        created_from: query.createdRange?.[0],
        created_to: query.createdRange?.[1],
        paid_from: query.paidRange?.[0],
        paid_to: query.paidRange?.[1],
      },
      responseType: 'blob',
      timeout: 60000,
    })
    downloadBlob(data, `订单收款-${fileStamp()}.xlsx`)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>订单收款</h3>
      <div>
        <el-button :loading="exporting" @click="exportExcel">导出 Excel</el-button>
        <el-button @click="router.push('/orders/refunds')">退款记录</el-button>
        <el-button type="primary" @click="openDialog">创建订单</el-button>
      </div>
    </div>

    <div class="filters">
      <el-input
        v-model="query.q"
        clearable
        placeholder="订单号 / 微信账单号 / 标题 / 会员"
        style="width: 200px"
        @keyup.enter="search"
      />
      <el-select v-model="query.status" clearable placeholder="状态" style="width: 140px">
        <el-option label="待支付" value="pending" />
        <el-option label="已收款" value="paid" />
        <el-option label="已退款" value="refunded" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-select v-model="query.merchant_id" clearable placeholder="商户" style="width: 180px">
        <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-select v-model="query.order_type" clearable placeholder="订单类型" style="width: 150px">
        <el-option v-for="(label, value) in ORDER_TYPE_LABELS" :key="value" :label="label" :value="value" />
      </el-select>
      <el-date-picker
        v-model="query.createdRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="创建开始"
        end-placeholder="创建结束"
        range-separator="至"
        style="width: 260px"
      />
      <el-date-picker
        v-model="query.paidRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="支付开始"
        end-placeholder="支付结束"
        range-separator="至"
        style="width: 260px"
      />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="orders" v-loading="loading" stripe>
      <el-table-column prop="order_no" label="订单号" min-width="210" />
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column label="会员" min-width="150">
        <template #default="{ row }">{{ memberLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="商户" width="160">
        <template #default="{ row }">{{ merchantName(row) }}</template>
      </el-table-column>
      <el-table-column label="类型" width="100">
        <template #default="{ row }">{{ orderTypeLabel(row.order_type) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="100">
        <template #default="{ row }"><b>¥{{ row.amount }}</b></template>
      </el-table-column>
      <el-table-column label="微信账单号" min-width="180">
        <template #default="{ row }">{{ row.wechat_transaction_id || '—' }}</template>
      </el-table-column>
      <el-table-column label="创建时间" min-width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="支付时间" min-width="170">
        <template #default="{ row }">{{ formatTime(row.paid_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <RowActions
            :more="[{ command: 'refund', label: '退款', disabled: row.status !== 'paid', danger: true }]"
            @more="refund(row)"
          >
            <el-button size="small" type="primary" @click="openDetail(row)">详情</el-button>
            <el-button size="small" type="primary" :disabled="row.status !== 'pending'" @click="payOffline(row)">
              线下收款
            </el-button>
          </RowActions>
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

    <el-dialog v-model="detailVisible" title="收款详情" width="840px" align-center destroy-on-close>
      <div v-loading="detailLoading" class="bill">
        <template v-if="detail">
          <header class="bill-hero">
            <div>
              <p class="bill-kicker">{{ orderTypeLabel(detail.order_type) }} · {{ merchantName(detail) }}</p>
              <h3>{{ detail.title }}</h3>
              <p class="bill-no">{{ detail.order_no || '—' }}</p>
            </div>
            <div class="bill-sum">
              <span class="bill-status" :data-tone="statusMeta(detail.status).type">
                {{ statusMeta(detail.status).label }}
              </span>
              <strong>¥{{ detail.amount }}</strong>
              <span>实付</span>
            </div>
          </header>

          <div class="bill-metrics">
            <div>
              <span>订单金额</span>
              <b>¥{{ detail.original_amount || detail.amount }}</b>
            </div>
            <div>
              <span>优惠</span>
              <b>¥{{ detail.promotion_discount_amount || '0.00' }}</b>
            </div>
            <div>
              <span>已退</span>
              <b>¥{{ detail.refunded_amount || '0.00' }}</b>
            </div>
            <div>
              <span>下单</span>
              <b>{{ formatTime(detail.created_at) }}</b>
            </div>
            <div>
              <span>支付</span>
              <b>{{ formatTime(detail.paid_at) }}</b>
            </div>
          </div>

          <p v-if="detail.pickup_code || detail.customer_note" class="bill-note">
            <template v-if="detail.pickup_code">取餐号 {{ detail.pickup_code }}</template>
            <template v-if="detail.customer_note">{{ detail.pickup_code ? ' · ' : '' }}{{ detail.customer_note }}</template>
          </p>

          <section class="bill-card">
            <h4>收退款流水</h4>
            <ul v-if="detail.payments?.length" class="ledger">
              <li v-for="row in detail.payments" :key="row.id">
                <i :data-kind="row.kind" />
                <div>
                  <b>{{ payKindLabel(row.kind) }} · {{ payChannelLabel(row.channel) }}</b>
                  <small>{{ formatTime(row.created_at) }}<template v-if="row.note"> · {{ row.note }}</template></small>
                </div>
                <em>¥{{ row.amount }}</em>
              </li>
            </ul>
            <p v-else class="empty-line">暂无收退款流水</p>
            <div v-if="detail.out_trade_no || detail.wechat_transaction_id" class="id-row">
              <span v-if="detail.out_trade_no">商户订单号 <code>{{ detail.out_trade_no }}</code></span>
              <span v-if="detail.wechat_transaction_id">微信支付订单号 <code>{{ detail.wechat_transaction_id }}</code></span>
            </div>
          </section>

          <section v-if="wechatSummary.length" class="bill-card">
            <h4>微信返回</h4>
            <dl class="kv">
              <div v-for="item in wechatSummary" :key="item[0]">
                <dt>{{ item[0] }}</dt>
                <dd>{{ item[1] }}</dd>
              </div>
            </dl>
            <el-collapse class="raw-fold">
              <el-collapse-item title="查看微信原始数据" name="raw">
                <pre class="raw-json">{{ JSON.stringify(detail.wechat_payload, null, 2) }}</pre>
              </el-collapse-item>
            </el-collapse>
          </section>

          <div class="people">
            <article class="bill-card">
              <h4>店铺</h4>
              <template v-if="detail.store">
                <strong>{{ detail.store.name }}</strong>
                <p class="people-sub">{{ merchantStatusLabel(detail.store.status) }}</p>
                <ul>
                  <li v-if="showText(detail.store.legal_name)"><span>主体</span>{{ detail.store.legal_name }}</li>
                  <li v-if="showText(detail.store.business_address)"><span>地址</span>{{ detail.store.business_address }}</li>
                  <li v-if="showText(detail.store.contact_phone)"><span>电话</span>{{ detail.store.contact_phone }}</li>
                  <li v-if="showText(detail.store.business_hours)"><span>营业</span>{{ detail.store.business_hours }}</li>
                </ul>
              </template>
              <p v-else class="empty-line">{{ merchantName(detail) }}</p>
            </article>
            <article class="bill-card">
              <h4>会员</h4>
              <template v-if="detail.buyer">
                <strong>{{ detail.buyer.name }}</strong>
                <p class="people-sub">{{ detail.buyer.phone }} · {{ genderLabel(detail.buyer.gender) }}</p>
                <ul>
                  <li v-if="showText(detail.buyer.email)"><span>邮箱</span>{{ detail.buyer.email }}</li>
                  <li><span>注册</span>{{ formatTime(detail.buyer.created_at) }}</li>
                  <li v-if="showText(detail.buyer.remark)"><span>备注</span>{{ detail.buyer.remark }}</li>
                </ul>
              </template>
              <p v-else class="empty-line">{{ memberLabel(detail) }}</p>
            </article>
          </div>
        </template>
      </div>
    </el-dialog>

    <el-dialog v-model="dialogVisible" title="创建订单（线下收款）" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="商户" prop="merchant_id">
          <el-select v-model="form.merchant_id" style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="订单类型" prop="order_type">
          <el-select v-model="form.order_type" style="width: 100%" :disabled="!allowedTypes.length">
            <el-option v-for="t in allowedTypes" :key="t.value" :label="t.label" :value="t.value" />
          </el-select>
          <p v-if="!allowedTypes.length" class="hint">该商户未关联业态子系统，请先在「商户组织」配置。</p>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" :placeholder="titlePlaceholder" maxlength="255" />
        </el-form-item>
        <el-form-item label="金额" prop="amount">
          <el-input v-model="form.amount" placeholder="0.00" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="create">创建</el-button>
      </template>
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
.hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--admin-ink-muted);
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
  grid-template-columns: 0.8fr 0.7fr 0.7fr 1.3fr 1.3fr;
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
.ledger {
  list-style: none;
  margin: 0;
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
.id-row code,
.kv dd {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.kv {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px 16px;
  margin: 0;
}
.kv div {
  min-width: 0;
}
.kv dt {
  margin-bottom: 2px;
  color: var(--admin-ink-muted);
  font-size: 12px;
}
.kv dd {
  margin: 0;
  font-size: 13px;
  word-break: break-all;
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
