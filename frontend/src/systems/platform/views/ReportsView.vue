<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import { orderTypeLabel, paymentChannelLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsStore, type OpsSubsystem } from '../../../core/stores/ops'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
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

type ReportTab = 'commerce' | 'membership' | 'course' | 'inventory'

const GYM_ORDER_TYPES = new Set(['membership', 'retail', 'pt', 'pt_package', 'group', 'course_pack'])
const CATERING_ORDER_TYPES = new Set(['dining'])

const ops = useOpsStore()
const merchants = ref<Merchant[]>([])
const summary = ref<Summary | null>(null)
const membership = ref<MembershipSummary | null>(null)
const course = ref<CourseSummary | null>(null)
const inventory = ref<InventorySummary | null>(null)
const loading = ref(false)
const activeTab = ref<ReportTab>('commerce')

function pad(n: number) {
  return String(n).padStart(2, '0')
}

function formatDate(d: Date) {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`
}

function todayStr() {
  return formatDate(new Date())
}

function daysAgo(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return formatDate(d)
}

const form = reactive({
  date_from: todayStr(),
  date_to: todayStr(),
})

const scopedMerchants = computed(() => merchantsWithSystem(merchants.value, ops.subsystem))
const isGym = computed(() => ops.subsystem === 'gym')
const subsystemLabel = computed(() => (isGym.value ? '观野FIT' : '观野BAR'))

const scopedTypes = computed(() => {
  const rows = summary.value?.by_order_type || []
  const allow = isGym.value ? GYM_ORDER_TYPES : CATERING_ORDER_TYPES
  return rows.filter((r) => allow.has(r.order_type) || r.order_type === 'coupon')
})

const scopedTotals = computed(() => {
  const rows = scopedTypes.value
  if (!rows.length) {
    return { charge: '0.00', refund: '0.00', net: '0.00' }
  }
  const charge = rows.reduce((s, r) => s + Number(r.charge_total), 0)
  const refund = rows.reduce((s, r) => s + Number(r.refund_total), 0)
  return {
    charge: charge.toFixed(2),
    refund: refund.toFixed(2),
    net: (charge - refund).toFixed(2),
  }
})

const lowStockSkus = computed(() => (inventory.value?.skus || []).filter((s) => s.is_low))
const sortedSkus = computed(() =>
  [...(inventory.value?.skus || [])].sort((a, b) => Number(b.is_low) - Number(a.is_low)),
)
const skuPage = ref(1)
const skuPageSize = ref(20)
const pagedSkus = computed(() => {
  const start = (skuPage.value - 1) * skuPageSize.value
  return sortedSkus.value.slice(start, start + skuPageSize.value)
})

function money(v: string | number | undefined) {
  return `¥${Number(v || 0).toFixed(2)}`
}

function setPreset(days: number) {
  form.date_to = todayStr()
  form.date_from = days <= 1 ? todayStr() : daysAgo(days - 1)
  loadSummary()
}

function setSubsystem(code: OpsSubsystem) {
  ops.setSubsystem(code)
  if (ops.merchantId && !merchantsWithSystem(merchants.value, code).some((m) => m.id === ops.merchantId)) {
    ops.setMerchantId(null)
  }
  if (code === 'catering' && activeTab.value !== 'commerce') {
    activeTab.value = 'commerce'
  }
}

function reportParams() {
  return {
    date_from: form.date_from,
    date_to: form.date_to,
    merchant_id: ops.merchantId ?? undefined,
  }
}

async function loadMerchants() {
  try {
    const { data } = await http.get<Merchant[]>('/merchants')
    merchants.value = data
    if (ops.merchantId && !scopedMerchants.value.some((m) => m.id === ops.merchantId)) {
      ops.setMerchantId(null)
    }
  } catch {
    merchants.value = []
  }
}

async function loadSummary() {
  loading.value = true
  try {
    const params = reportParams()
    const tasks: Promise<void>[] = [
      http.get<Summary>('/reports/commerce-summary', { params }).then((r) => {
        summary.value = r.data
      }),
    ]
    if (isGym.value) {
      tasks.push(
        http.get<MembershipSummary>('/reports/membership-summary', { params }).then((r) => {
          membership.value = r.data
        }),
        http.get<CourseSummary>('/reports/course-summary', { params }).then((r) => {
          course.value = r.data
        }),
        http.get<InventorySummary>('/reports/inventory-summary', { params }).then((r) => {
          inventory.value = r.data
        }),
      )
    } else {
      membership.value = null
      course.value = null
      inventory.value = null
    }
    await Promise.all(tasks)
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
    a.download = `收款明细-${form.date_from}-${form.date_to}.csv`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('已开始下载')
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导出失败')
  }
}

watch(
  () => [ops.subsystem, ops.merchantId],
  () => {
    loadSummary()
  },
)

onMounted(async () => {
  await loadMerchants()
  await loadSummary()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>经营报表</h3>
        <p class="hint">先选业务子系统，再按标签查看一类数据。商户可留空，表示该子系统下全部商户。</p>
      </div>
      <el-button @click="exportCsv">导出收款明细</el-button>
    </div>

    <div class="filters">
      <el-radio-group :model-value="ops.subsystem" @change="setSubsystem">
        <el-radio-button value="gym">观野FIT</el-radio-button>
        <el-radio-button value="catering">观野BAR</el-radio-button>
      </el-radio-group>
      <el-select
        :model-value="ops.merchantId ?? undefined"
        clearable
        placeholder="全部商户"
        style="width: 200px"
        @change="(v: number | undefined) => ops.setMerchantId(v ?? null)"
      >
        <el-option v-for="m in scopedMerchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-date-picker
        v-model="form.date_from"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="开始日期"
        style="width: 150px"
      />
      <span class="range-sep">至</span>
      <el-date-picker
        v-model="form.date_to"
        type="date"
        value-format="YYYY-MM-DD"
        placeholder="结束日期"
        style="width: 150px"
      />
      <el-button-group>
        <el-button @click="setPreset(1)">今日</el-button>
        <el-button @click="setPreset(7)">近7天</el-button>
        <el-button @click="setPreset(30)">近30天</el-button>
      </el-button-group>
      <el-button type="primary" :loading="loading" @click="loadSummary">查询</el-button>
    </div>

    <el-tabs v-model="activeTab" class="report-tabs">
      <el-tab-pane :label="`${subsystemLabel}收款`" name="commerce">
        <div v-loading="loading">
          <div class="kpi-grid">
            <div class="kpi-card">
              <div class="kpi-label">收款</div>
              <div class="kpi-value">{{ money(scopedTotals.charge) }}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">退款</div>
              <div class="kpi-value">{{ money(scopedTotals.refund) }}</div>
            </div>
            <div class="kpi-card kpi-card--accent">
              <div class="kpi-label">净收</div>
              <div class="kpi-value">{{ money(scopedTotals.net) }}</div>
            </div>
          </div>

          <h4 class="section-title">按业务类型</h4>
          <el-table :data="scopedTypes" stripe empty-text="该区间暂无收款">
            <el-table-column label="类型" min-width="140">
              <template #default="{ row }">{{ orderTypeLabel(row.order_type) }}</template>
            </el-table-column>
            <el-table-column label="收款" width="140">
              <template #default="{ row }">{{ money(row.charge_total) }}</template>
            </el-table-column>
            <el-table-column label="退款" width="140">
              <template #default="{ row }">{{ money(row.refund_total) }}</template>
            </el-table-column>
            <el-table-column label="净收" width="140">
              <template #default="{ row }">{{ money(row.net_total) }}</template>
            </el-table-column>
          </el-table>

          <h4 class="section-title">按支付渠道</h4>
          <el-table :data="summary?.by_channel || []" stripe empty-text="该区间暂无支付流水">
            <el-table-column label="渠道" min-width="140">
              <template #default="{ row }">{{ paymentChannelLabel(row.channel) }}</template>
            </el-table-column>
            <el-table-column label="收款" width="140">
              <template #default="{ row }">{{ money(row.charge_total) }}</template>
            </el-table-column>
            <el-table-column label="退款" width="140">
              <template #default="{ row }">{{ money(row.refund_total) }}</template>
            </el-table-column>
            <el-table-column label="净收" width="140">
              <template #default="{ row }">{{ money(row.net_total) }}</template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="isGym" label="会籍" name="membership">
        <div v-loading="loading" class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-label">新开</div>
            <div class="kpi-value">{{ membership?.new_count ?? 0 }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">续费</div>
            <div class="kpi-value">{{ membership?.renew_count ?? 0 }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">在籍</div>
            <div class="kpi-value">{{ membership?.active_count ?? 0 }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">停卡</div>
            <div class="kpi-value">{{ membership?.frozen_count ?? 0 }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">区间到期</div>
            <div class="kpi-value">{{ membership?.expired_in_range ?? 0 }}</div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="isGym" label="课程" name="course">
        <div v-loading="loading" class="kpi-grid">
          <div class="kpi-card">
            <div class="kpi-label">团课场次</div>
            <div class="kpi-value">{{ course?.session_count ?? 0 }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">预约</div>
            <div class="kpi-value">{{ course?.booking_count ?? 0 }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">满课场次</div>
            <div class="kpi-value">{{ course?.full_session_count ?? 0 }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">出勤</div>
            <div class="kpi-value">{{ course?.attended_count ?? 0 }}</div>
          </div>
          <div class="kpi-card">
            <div class="kpi-label">私教核销</div>
            <div class="kpi-value">{{ course?.pt_consume_count ?? 0 }}</div>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane v-if="isGym" label="零售库存" name="inventory">
        <div v-loading="loading">
          <div class="kpi-grid">
            <div class="kpi-card">
              <div class="kpi-label">区间销量</div>
              <div class="kpi-value">{{ inventory?.sale_qty ?? 0 }}</div>
            </div>
            <div class="kpi-card">
              <div class="kpi-label">在售 SKU</div>
              <div class="kpi-value">{{ inventory?.skus.length ?? 0 }}</div>
            </div>
            <div class="kpi-card kpi-card--warn">
              <div class="kpi-label">低库存</div>
              <div class="kpi-value">{{ lowStockSkus.length }}</div>
            </div>
          </div>
          <h4 class="section-title">SKU 库存</h4>
          <el-table :data="pagedSkus" stripe empty-text="暂无在售商品">
            <el-table-column prop="name" label="名称" min-width="160" />
            <el-table-column prop="stock_qty" label="库存" width="100" />
            <el-table-column prop="low_stock_threshold" label="预警线" width="100" />
            <el-table-column label="状态" width="110">
              <template #default="{ row }">
                <el-tag size="small" :type="row.is_low ? 'danger' : 'success'">
                  {{ row.is_low ? '低库存' : '正常' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
          <div class="pager">
            <el-pagination
              v-model:current-page="skuPage"
              v-model:page-size="skuPageSize"
              :total="sortedSkus.length"
              :page-sizes="[10, 20, 50, 100]"
              layout="total, sizes, prev, pager, next"
              background
            />
          </div>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0 0 6px;
}
.hint {
  margin: 0;
  font-size: 13px;
  color: var(--admin-ink-muted);
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  margin-bottom: 8px;
}
.range-sep {
  color: var(--admin-ink-muted);
  font-size: 13px;
}
.report-tabs {
  margin-top: 4px;
}
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 12px;
  margin: 4px 0 20px;
}
.kpi-card {
  border: 1px solid rgba(28, 25, 23, 0.08);
  background: #fffcf8;
  border-radius: 14px;
  padding: 16px;
}
.kpi-card--accent {
  border-color: rgba(61, 107, 92, 0.28);
  background: #f4f8f6;
}
.kpi-card--warn {
  border-color: rgba(180, 83, 9, 0.22);
  background: #fff8f1;
}
.kpi-label {
  font-size: 12px;
  color: var(--admin-ink-muted);
  font-weight: 600;
}
.kpi-value {
  margin-top: 8px;
  font-size: 1.45rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--admin-ink);
}
.section-title {
  margin: 8px 0 12px;
  font-size: 0.95rem;
  font-weight: 650;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
