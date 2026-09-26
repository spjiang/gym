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
  return value && value.trim() ? value : '—'
}

const wechatSummary = computed(() => {
  const raw = detail.value?.wechat_payload
  if (!raw) return []
  const amount = raw.amount as { total?: number; payer_total?: number } | undefined
  const payer = raw.payer as { openid?: string } | undefined
  const fen = amount?.payer_total ?? amount?.total
  return [
    ['交易状态', String(raw.trade_state_desc || raw.trade_state || '—')],
    ['支付完成时间', String(raw.success_time || '—')],
    ['付款银行', String(raw.bank_type || '—')],
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

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>订单收款</h3>
      <div>
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

    <el-drawer v-model="detailVisible" title="订单详情" size="760px" destroy-on-close>
      <div v-loading="detailLoading">
        <template v-if="detail">
          <header class="detail-head">
            <div>
              <p class="detail-no">{{ detail.order_no || '—' }}</p>
              <p class="detail-sub">{{ detail.title }} · {{ orderTypeLabel(detail.order_type) }}</p>
            </div>
            <div class="detail-amount">
              <el-tag :type="statusMeta(detail.status).type">{{ statusMeta(detail.status).label }}</el-tag>
              <strong>¥{{ detail.amount }}</strong>
            </div>
          </header>

          <section class="detail-block">
            <h4>订单信息</h4>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="下单时间">{{ formatTime(detail.created_at) }}</el-descriptions-item>
              <el-descriptions-item label="支付时间">{{ formatTime(detail.paid_at) }}</el-descriptions-item>
              <el-descriptions-item label="订单金额">¥{{ detail.original_amount || detail.amount }}</el-descriptions-item>
              <el-descriptions-item label="优惠">¥{{ detail.promotion_discount_amount || '0.00' }}</el-descriptions-item>
              <el-descriptions-item label="实付">¥{{ detail.amount }}</el-descriptions-item>
              <el-descriptions-item label="已退">¥{{ detail.refunded_amount || '0.00' }}</el-descriptions-item>
              <el-descriptions-item v-if="detail.pickup_code" label="取餐号">{{ detail.pickup_code }}</el-descriptions-item>
              <el-descriptions-item v-if="detail.customer_note" label="顾客备注" :span="2">
                {{ detail.customer_note }}
              </el-descriptions-item>
            </el-descriptions>
          </section>

          <section class="detail-block">
            <h4>支付信息</h4>
            <el-descriptions :column="1" border>
              <el-descriptions-item label="商户订单号">{{ detail.out_trade_no || '—' }}</el-descriptions-item>
              <el-descriptions-item label="微信支付订单号">{{ detail.wechat_transaction_id || '—' }}</el-descriptions-item>
            </el-descriptions>
            <el-table v-if="detail.payments?.length" :data="detail.payments" size="small" class="pay-table">
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
            <p v-else class="empty-line">暂无收退款流水</p>
            <template v-if="wechatSummary.length">
              <h5>微信返回</h5>
              <el-descriptions :column="1" border>
                <el-descriptions-item v-for="item in wechatSummary" :key="item[0]" :label="item[0]">
                  {{ item[1] }}
                </el-descriptions-item>
              </el-descriptions>
              <el-collapse class="raw-fold">
                <el-collapse-item title="查看微信原始数据" name="raw">
                  <pre class="raw-json">{{ JSON.stringify(detail.wechat_payload, null, 2) }}</pre>
                </el-collapse-item>
              </el-collapse>
            </template>
          </section>

          <div class="detail-grid">
            <section class="detail-block">
              <h4>店铺</h4>
              <el-descriptions v-if="detail.store" :column="1" border>
                <el-descriptions-item label="名称">{{ detail.store.name }}</el-descriptions-item>
                <el-descriptions-item label="状态">{{ merchantStatusLabel(detail.store.status) }}</el-descriptions-item>
                <el-descriptions-item label="主体">{{ showText(detail.store.legal_name) }}</el-descriptions-item>
                <el-descriptions-item label="地址">{{ showText(detail.store.business_address) }}</el-descriptions-item>
                <el-descriptions-item label="电话">{{ showText(detail.store.contact_phone) }}</el-descriptions-item>
                <el-descriptions-item label="营业时间">{{ showText(detail.store.business_hours) }}</el-descriptions-item>
              </el-descriptions>
              <p v-else class="empty-line">{{ merchantName(detail) }}</p>
            </section>
            <section class="detail-block">
              <h4>用户</h4>
              <el-descriptions v-if="detail.buyer" :column="1" border>
                <el-descriptions-item label="姓名">{{ detail.buyer.name }}</el-descriptions-item>
                <el-descriptions-item label="手机">{{ detail.buyer.phone }}</el-descriptions-item>
                <el-descriptions-item label="性别">{{ genderLabel(detail.buyer.gender) }}</el-descriptions-item>
                <el-descriptions-item label="邮箱">{{ showText(detail.buyer.email) }}</el-descriptions-item>
                <el-descriptions-item label="注册时间">{{ formatTime(detail.buyer.created_at) }}</el-descriptions-item>
                <el-descriptions-item label="备注">{{ showText(detail.buyer.remark) }}</el-descriptions-item>
              </el-descriptions>
              <p v-else class="empty-line">{{ memberLabel(detail) }}</p>
            </section>
          </div>
        </template>
      </div>
    </el-drawer>

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
.detail-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
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
