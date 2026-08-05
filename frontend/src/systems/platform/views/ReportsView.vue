<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import { useAuthStore } from '../../../core/stores/auth'
import { orderTypeLabel, paymentChannelLabel } from '../../../core/labels'

type Merchant = { id: number; name: string }
type BreakdownChannel = {
  channel: string
  charge_total: string
  refund_total: string
  net_total: string
}
type BreakdownType = {
  order_type: string
  charge_total: string
  refund_total: string
  net_total: string
}
type Summary = {
  charge_total: string
  refund_total: string
  net_total: string
  merchant_id: number | null
  by_channel: BreakdownChannel[]
  by_order_type: BreakdownType[]
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
type InventorySku = {
  sku_id: number
  name: string
  stock_qty: number
  low_stock_threshold: number
  is_low: boolean
}
type InventorySummary = {
  sale_qty: number
  skus: InventorySku[]
}

const auth = useAuthStore()
const merchants = ref<Merchant[]>([])
const summary = ref<Summary | null>(null)
const membership = ref<MembershipSummary | null>(null)
const course = ref<CourseSummary | null>(null)
const inventory = ref<InventorySummary | null>(null)
const loading = ref(false)

function todayStr() {
  return new Date().toISOString().slice(0, 10)
}

const form = reactive({
  date_from: todayStr(),
  date_to: todayStr(),
  merchant_id: undefined as number | undefined,
})

const isSiteAdmin = computed(() => auth.me?.role_codes.includes('site_admin'))

function reportParams() {
  return {
    date_from: form.date_from,
    date_to: form.date_to,
    merchant_id: isSiteAdmin.value ? form.merchant_id : undefined,
  }
}

async function loadMerchants() {
  const { data } = await http.get('/merchants')
  merchants.value = data
  if (!form.merchant_id && data[0] && isSiteAdmin.value) {
    form.merchant_id = data[0].id
  }
}

async function loadSummary() {
  loading.value = true
  try {
    const params = reportParams()
    const [c, m, o, i] = await Promise.all([
      http.get('/reports/commerce-summary', { params }),
      http.get('/reports/membership-summary', { params }),
      http.get('/reports/course-summary', { params }),
      http.get('/reports/inventory-summary', { params }),
    ])
    summary.value = c.data
    membership.value = m.data
    course.value = o.data
    inventory.value = i.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function exportCsv() {
  try {
    const resp = await http.get('/reports/commerce-payments.csv', {
      params: reportParams(),
      responseType: 'blob',
    })
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `commerce-payments-${form.date_from}-${form.date_to}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已开始下载')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导出失败')
  }
}

onMounted(async () => {
  await loadMerchants()
  await loadSummary()
})
</script>

<template>
  <div>
    <el-form inline>
      <el-form-item label="开始">
        <el-date-picker v-model="form.date_from" type="date" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item label="结束">
        <el-date-picker v-model="form.date_to" type="date" value-format="YYYY-MM-DD" />
      </el-form-item>
      <el-form-item v-if="isSiteAdmin" label="商户">
        <el-select v-model="form.merchant_id" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-button type="primary" :loading="loading" @click="loadSummary">查询</el-button>
      <el-button @click="exportCsv">导出收款明细</el-button>
    </el-form>

    <h3>收款汇总</h3>
    <el-row v-if="summary" :gutter="12" style="margin: 12px 0 20px">
      <el-col :span="8">
        <el-card shadow="never"><div class="muted">收款</div><div class="num">¥{{ summary.charge_total }}</div></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never"><div class="muted">退款</div><div class="num">¥{{ summary.refund_total }}</div></el-card>
      </el-col>
      <el-col :span="8">
        <el-card shadow="never"><div class="muted">净收</div><div class="num">¥{{ summary.net_total }}</div></el-card>
      </el-col>
    </el-row>

    <h3>按支付渠道</h3>
    <el-table :data="summary?.by_channel || []" stripe style="margin-bottom: 16px">
      <el-table-column label="渠道">
        <template #default="{ row }">{{ paymentChannelLabel(row.channel) }}</template>
      </el-table-column>
      <el-table-column prop="charge_total" label="收款" />
      <el-table-column prop="refund_total" label="退款" />
      <el-table-column prop="net_total" label="净收" />
    </el-table>

    <h3>按业务类型</h3>
    <el-table :data="summary?.by_order_type || []" stripe style="margin-bottom: 24px">
      <el-table-column label="类型">
        <template #default="{ row }">{{ orderTypeLabel(row.order_type) }}</template>
      </el-table-column>
      <el-table-column prop="charge_total" label="收款" />
      <el-table-column prop="refund_total" label="退款" />
      <el-table-column prop="net_total" label="净收" />
    </el-table>

    <h3>会籍</h3>
    <el-row v-if="membership" :gutter="12" style="margin-bottom: 20px">
      <el-col :span="4"><el-card shadow="never"><div class="muted">新开</div><div class="num">{{ membership.new_count }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="muted">续费</div><div class="num">{{ membership.renew_count }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="muted">在籍</div><div class="num">{{ membership.active_count }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="muted">停卡</div><div class="num">{{ membership.frozen_count }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="muted">区间到期</div><div class="num">{{ membership.expired_in_range }}</div></el-card></el-col>
    </el-row>

    <h3>课程</h3>
    <el-row v-if="course" :gutter="12" style="margin-bottom: 20px">
      <el-col :span="4"><el-card shadow="never"><div class="muted">团课场次</div><div class="num">{{ course.session_count }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="muted">预约</div><div class="num">{{ course.booking_count }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="muted">满课场次</div><div class="num">{{ course.full_session_count }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="muted">出勤</div><div class="num">{{ course.attended_count }}</div></el-card></el-col>
      <el-col :span="4"><el-card shadow="never"><div class="muted">私教核销</div><div class="num">{{ course.pt_consume_count }}</div></el-card></el-col>
    </el-row>

    <h3>库存</h3>
    <p v-if="inventory" class="muted" style="margin-bottom: 8px">区间销量：{{ inventory.sale_qty }}</p>
    <el-table :data="inventory?.skus || []" stripe>
      <el-table-column prop="sku_id" label="SKU" width="80" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="stock_qty" label="库存" width="90" />
      <el-table-column prop="low_stock_threshold" label="预警线" width="90" />
      <el-table-column label="低库存" width="90">
        <template #default="{ row }">{{ row.is_low ? '是' : '否' }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.muted {
  color: var(--admin-ink-muted);
  font-size: 0.8rem;
  letter-spacing: 0.04em;
  text-transform: uppercase;
  font-weight: 600;
}
.num {
  font-size: 1.55rem;
  font-weight: 700;
  margin-top: 6px;
  letter-spacing: -0.03em;
  color: var(--admin-ink);
}
</style>
