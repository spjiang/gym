<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../api/http'

type Order = { id: number; title: string; amount: string; status: string; merchant_id: number; order_type: string }
type Merchant = { id: number; name: string; subsystem_codes: string[] }
type OrderTypeOpt = { value: string; label: string }

const orders = ref<Order[]>([])
const merchants = ref<Merchant[]>([])
const allowedTypes = ref<OrderTypeOpt[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()

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

function statusMeta(status: string) {
  return {
    paid: { type: 'success' as const, label: '已收款' },
    pending: { type: 'warning' as const, label: '待支付' },
    refunded: { type: 'danger' as const, label: '已退款' },
    cancelled: { type: 'info' as const, label: '已取消' },
  }[status] || { type: 'info' as const, label: status }
}

function orderTypeLabel(t: string) {
  return allowedTypes.value.find((o) => o.value === t)?.label
    || { retail: '零售', membership: '会籍办卡', pt: '私教', group: '团课', dining: '餐饮消费' }[t]
    || t
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
    const [o, m] = await Promise.all([http.get('/orders'), http.get('/merchants')])
    orders.value = o.data
    merchants.value = m.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
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
    await ElMessageBox.confirm(
      `确认对订单「${row.title}」（¥${row.amount}）发起退款？`,
      '订单退款',
      { type: 'warning', confirmButtonText: '退款', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await http.post(`/orders/${row.id}/refund`)
    ElMessage.success('已退款')
    await load()
  } catch (e: unknown) {
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

    <el-table :data="orders" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column label="商户" width="180">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
      <el-table-column label="类型" width="110">
        <template #default="{ row }">{{ orderTypeLabel(row.order_type) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="110">
        <template #default="{ row }"><b>¥{{ row.amount }}</b></template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" :disabled="row.status !== 'pending'" @click="payOffline(row)">
            线下收款
          </el-button>
          <el-button size="small" :disabled="row.status !== 'paid'" @click="refund(row)">退款</el-button>
        </template>
      </el-table-column>
    </el-table>

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
}
.toolbar h3 {
  margin: 0;
}
.hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--admin-ink-muted);
}
</style>
