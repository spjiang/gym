<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { ORDER_TYPE_LABELS, orderTypeLabel as mapOrderType } from '../../../core/labels'

type MemberBrief = { id: number; name: string; phone: string }
type Order = {
  id: number
  title: string
  amount: string
  status: string
  merchant_id: number
  order_type: string
  member_id?: number | null
  pickup_code?: string | null
  customer_note?: string | null
  created_at?: string
  member?: MemberBrief | null
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
const detail = ref<Order | null>(null)
const submitting = ref(false)
const formRef = ref<FormInstance>()

const query = reactive({
  q: '',
  status: '' as string,
  merchant_id: undefined as number | undefined,
  order_type: '' as string,
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

function merchantName(id: number) {
  return merchants.value.find((m) => m.id === id)?.name || `#${id}`
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
  page.value = 1
  void load()
}

function openDetail(row: Order) {
  detail.value = row
  detailVisible.value = true
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
    ElMessage.success('已退款')
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
      <el-button type="primary" @click="openDialog">创建订单</el-button>
    </div>

    <div class="filters">
      <el-input
        v-model="query.q"
        clearable
        placeholder="单号 / 标题 / 会员"
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
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="orders" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column label="会员" min-width="150">
        <template #default="{ row }">{{ memberLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="商户" width="160">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
      <el-table-column label="类型" width="100">
        <template #default="{ row }">{{ orderTypeLabel(row.order_type) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="100">
        <template #default="{ row }"><b>¥{{ row.amount }}</b></template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button size="small" :disabled="row.status !== 'pending'" @click="payOffline(row)">
            线下收款
          </el-button>
          <el-button size="small" :disabled="row.status !== 'paid'" @click="refund(row)">退款</el-button>
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

    <el-drawer v-model="detailVisible" title="订单详情" size="440px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="订单号">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="标题">{{ detail.title }}</el-descriptions-item>
          <el-descriptions-item label="金额">¥{{ detail.amount }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusMeta(detail.status).label }}</el-descriptions-item>
          <el-descriptions-item label="类型">{{ orderTypeLabel(detail.order_type) }}</el-descriptions-item>
          <el-descriptions-item label="商户">{{ merchantName(detail.merchant_id) }}</el-descriptions-item>
          <el-descriptions-item label="会员">{{ memberLabel(detail) }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.pickup_code" label="取餐号">
            {{ detail.pickup_code }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.customer_note" label="备注">
            {{ detail.customer_note }}
          </el-descriptions-item>
        </el-descriptions>
      </template>
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
</style>
