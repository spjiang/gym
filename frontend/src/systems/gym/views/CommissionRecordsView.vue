<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'
import {
  COMMISSION_CATEGORY_LABELS,
  COMMISSION_SCOPE_LABELS,
  COMMISSION_STATUS_LABELS,
  beneficiaryTypeLabel,
  commissionCategoryLabel,
  commissionScopeLabel,
  commissionStatusLabel,
} from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Record_ = {
  id: number
  merchant_id: number
  rule_id: number | null
  rule_name: string | null
  scope: string
  category: string
  source_type: string
  source_id: number
  order_id: number | null
  member_id: number | null
  coach_id: number | null
  beneficiary_type: string
  beneficiary_id: number
  beneficiary_name: string
  base_amount: string
  quantity: number | null
  rate: string | null
  amount: string
  status: string
  note: string | null
  settled_at: string | null
  created_at: string
  settle_ready?: boolean
  settle_hold_until?: string | null
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }
type Summary = {
  date_from: string
  date_to: string
  total_amount: string
  pending_amount: string
  confirmed_amount: string
  paid_amount: string
  by_scope: { scope: string; record_count: number; total_amount: string }[]
  by_beneficiary: {
    beneficiary_type: string
    beneficiary_id: number
    beneficiary_name: string
    record_count: number
    pending_amount: string
    confirmed_amount: string
    paid_amount: string
    total_amount: string
  }[]
  sellers: {
    staff_id: number
    staff_name: string
    order_count: number
    sales_amount: string
    commission_amount: string
  }[]
}

const merchants = ref<Merchant[]>([])
const rows = ref<Record_[]>([])
const selected = ref<Record_[]>([])
const summary = ref<Summary | null>(null)
const loading = ref(false)
const summaryLoading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const activeTab = ref('records')

const { merchantId } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})

function today() {
  return new Date().toISOString().slice(0, 10)
}

function daysAgo(n: number) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

const query = reactive({
  q: '',
  scope: '',
  category: '',
  status: '',
  beneficiary_type: '',
  range: [daysAgo(29), today()] as [string, string] | undefined,
})

const summaryRange = ref<[string, string]>([daysAgo(29), today()])

const canBatchConfirm = computed(() => selected.value.some((r) => r.status === 'pending'))
const canBatchPay = computed(() =>
  selected.value.some((r) => r.status === 'confirmed' && r.settle_ready !== false),
)

function fmtTime(iso: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function statusTagType(status: string) {
  if (status === 'paid') return 'success'
  if (status === 'confirmed') return 'primary'
  if (status === 'pending') return 'warning'
  return 'info'
}

function sourceText(row: Record_) {
  if (row.order_id) return `订单 #${row.order_id}`
  if (row.source_type === 'group_session') return `团课场次 #${row.source_id}`
  if (row.source_type === 'pt_appointment') return `私教预约 #${row.source_id}`
  return `${row.source_type} #${row.source_id}`
}

function basisText(row: Record_) {
  if (row.rate) {
    const pct = (Number(row.rate) * 100).toFixed(2).replace(/\.?0+$/, '')
    return `¥${row.base_amount} × ${pct}%`
  }
  if (row.quantity && row.quantity > 1) return `${row.quantity} 单位固定额`
  return '固定额'
}

async function loadMerchants() {
  const { data } = await http.get('/merchants')
  merchants.value = merchantsWithSystem(data, 'gym')
  if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
    merchantId.value = undefined
  }
}

async function refresh() {
  loading.value = true
  try {
    await loadMerchants()
    const { data } = await http.get<Page<Record_>>('/commission-records', {
      params: {
        merchant_id: merchantId.value,
        scope: query.scope || undefined,
        category: query.category || undefined,
        status: query.status || undefined,
        beneficiary_type: query.beneficiary_type || undefined,
        date_from: query.range?.[0],
        date_to: query.range?.[1],
        q: query.q.trim() || undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    rows.value = data.items
    total.value = data.total
    selected.value = []
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  summaryLoading.value = true
  try {
    const { data } = await http.get<Summary>('/commission-summary', {
      params: {
        merchant_id: merchantId.value,
        date_from: summaryRange.value?.[0],
        date_to: summaryRange.value?.[1],
      },
    })
    summary.value = data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载看板失败')
  } finally {
    summaryLoading.value = false
  }
}

function search() {
  page.value = 1
  void refresh()
}

function resetSearch() {
  query.q = ''
  query.scope = ''
  query.category = ''
  query.status = ''
  query.beneficiary_type = ''
  query.range = [daysAgo(29), today()]
  page.value = 1
  void refresh()
}

function onTabChange(name: string) {
  if (name === 'summary' && !summary.value) void loadSummary()
}

async function changeStatus(row: Record_, status: string, label: string) {
  try {
    await ElMessageBox.confirm(
      `将 ${row.beneficiary_name} 的 ¥${row.amount} 提成${label}？`,
      `${label}确认`,
      { type: status === 'void' ? 'warning' : 'info' },
    )
  } catch {
    return
  }
  try {
    await http.post(`/commission-records/${row.id}/status`, { status })
    ElMessage.success(`已${label}`)
    await refresh()
    if (summary.value) await loadSummary()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

async function batchStatus(status: string, label: string) {
  const ids = selected.value
    .filter((r) =>
      status === 'confirmed'
        ? r.status === 'pending'
        : r.status === 'confirmed' && r.settle_ready !== false,
    )
    .map((r) => r.id)
  if (!ids.length) {
    ElMessage.warning(`勾选的记录中没有可${label}的条目`)
    return
  }
  try {
    await ElMessageBox.confirm(`批量${label} ${ids.length} 条提成记录？`, `批量${label}`, {
      type: 'info',
    })
  } catch {
    return
  }
  try {
    const { data } = await http.post('/commission-records/batch-status', { ids, status })
    ElMessage.success(`成功 ${data.updated} 条，跳过 ${data.skipped} 条`)
    await refresh()
    if (summary.value) await loadSummary()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '批量操作失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>提成结算</h3>
        <p class="lead">
          销售开单、团课签到、私教核销与推荐成交产生的提成在此确认与结算。流转顺序为待确认 → 已确认 → 已结算。冷却期内不可结算；未打款退款自动作废，已打款退款记欠额并在下次结算抵扣。冷却天数在「分成配置」中设置。
        </p>
      </div>
    </div>

    <el-tabs v-model="activeTab" @tab-change="onTabChange">
      <el-tab-pane label="提成明细" name="records">
        <el-form inline class="filters">
          <el-form-item label="商户">
            <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 170px">
              <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="类别">
            <el-select v-model="query.category" clearable placeholder="全部" style="width: 130px">
              <el-option v-for="(label, code) in COMMISSION_CATEGORY_LABELS" :key="code" :label="label" :value="code" />
            </el-select>
          </el-form-item>
          <el-form-item label="场景">
            <el-select v-model="query.scope" clearable placeholder="全部" style="width: 150px">
              <el-option v-for="(label, code) in COMMISSION_SCOPE_LABELS" :key="code" :label="label" :value="code" />
            </el-select>
          </el-form-item>
          <el-form-item label="状态">
            <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px">
              <el-option v-for="(label, code) in COMMISSION_STATUS_LABELS" :key="code" :label="label" :value="code" />
            </el-select>
          </el-form-item>
          <el-form-item label="受益人">
            <el-select v-model="query.beneficiary_type" clearable placeholder="全部" style="width: 110px">
              <el-option label="员工" value="staff" />
              <el-option label="教练" value="coach" />
              <el-option label="会员" value="member" />
            </el-select>
          </el-form-item>
          <el-form-item label="计提日期">
            <el-date-picker
              v-model="query.range"
              type="daterange"
              value-format="YYYY-MM-DD"
              start-placeholder="开始"
              end-placeholder="结束"
              style="width: 240px"
            />
          </el-form-item>
          <el-form-item label="关键词">
            <el-input
              v-model="query.q"
              clearable
              placeholder="受益人 / 备注 / 订单号"
              style="width: 190px"
              @keyup.enter="search"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="search">查询</el-button>
            <el-button @click="resetSearch">重置</el-button>
          </el-form-item>
        </el-form>

        <div class="batch-bar">
          <span class="hint">已勾选 {{ selected.length }} 条</span>
          <el-button size="small" type="primary" :disabled="!canBatchConfirm" @click="batchStatus('confirmed', '确认')">
            批量确认
          </el-button>
          <el-button size="small" type="success" :disabled="!canBatchPay" @click="batchStatus('paid', '结算')">
            批量结算
          </el-button>
        </div>

        <el-table
          :data="rows"
          v-loading="loading"
          stripe
          style="width: 100%"
          @selection-change="(v: Record_[]) => (selected = v)"
        >
          <el-table-column type="selection" width="46" :selectable="(row: Record_) => row.status === 'pending' || (row.status === 'confirmed' && row.settle_ready !== false)" />
          <el-table-column prop="id" label="ID" width="70" />
          <el-table-column label="受益人" min-width="150">
            <template #default="{ row }">
              <div>{{ row.beneficiary_name }}</div>
              <div class="sub">{{ beneficiaryTypeLabel(row.beneficiary_type) }} #{{ row.beneficiary_id }}</div>
            </template>
          </el-table-column>
          <el-table-column label="类别" width="90">
            <template #default="{ row }">{{ commissionCategoryLabel(row.category) }}</template>
          </el-table-column>
          <el-table-column label="场景" width="120">
            <template #default="{ row }">{{ commissionScopeLabel(row.scope) }}</template>
          </el-table-column>
          <el-table-column label="来源" min-width="160">
            <template #default="{ row }">
              <div>{{ sourceText(row) }}</div>
              <div class="sub">
                {{ row.rule_name || '规则已删除' }}
                <template v-if="row.coach_id"> · 教练 #{{ row.coach_id }}</template>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="计提口径" min-width="150">
            <template #default="{ row }">{{ basisText(row) }}</template>
          </el-table-column>
          <el-table-column label="提成金额" width="120">
            <template #default="{ row }">
              <strong>¥{{ row.amount }}</strong>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small" :type="statusTagType(row.status)">{{ commissionStatusLabel(row.status) }}</el-tag>
              <div v-if="row.status === 'confirmed' && row.settle_ready === false" class="sub">
                冷却至 {{ fmtTime(row.settle_hold_until || null) }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="计提时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="结算时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.settled_at) }}</template>
          </el-table-column>
          <el-table-column label="备注" min-width="160">
            <template #default="{ row }">{{ row.note || '—' }}</template>
          </el-table-column>
          <el-table-column label="操作" width="190" fixed="right">
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'pending'"
                link
                type="primary"
                @click="changeStatus(row, 'confirmed', '确认')"
              >
                确认
              </el-button>
              <el-button
                v-if="row.status === 'confirmed' && row.settle_ready !== false"
                link
                type="success"
                @click="changeStatus(row, 'paid', '结算')"
              >
                结算
              </el-button>
              <el-button
                v-if="row.status === 'pending' || row.status === 'confirmed'"
                link
                type="danger"
                @click="changeStatus(row, 'void', '作废')"
              >
                作废
              </el-button>
              <span v-if="row.status === 'paid' || row.status === 'void'" class="sub">已终结</span>
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
            @current-change="refresh"
            @size-change="
              () => {
                page = 1
                refresh()
              }
            "
          />
        </div>
      </el-tab-pane>

      <el-tab-pane label="业绩看板" name="summary">
        <el-form inline class="filters">
          <el-form-item label="统计区间">
            <el-date-picker
              v-model="summaryRange"
              type="daterange"
              value-format="YYYY-MM-DD"
              start-placeholder="开始"
              end-placeholder="结束"
              style="width: 240px"
            />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" :loading="summaryLoading" @click="loadSummary">刷新看板</el-button>
          </el-form-item>
        </el-form>

        <div v-loading="summaryLoading">
          <div class="kpis">
            <el-card shadow="never" class="kpi">
              <div class="kpi-label">提成合计</div>
              <div class="kpi-value">¥{{ summary?.total_amount ?? '0.00' }}</div>
            </el-card>
            <el-card shadow="never" class="kpi">
              <div class="kpi-label">待确认</div>
              <div class="kpi-value warn">¥{{ summary?.pending_amount ?? '0.00' }}</div>
            </el-card>
            <el-card shadow="never" class="kpi">
              <div class="kpi-label">已确认待结算</div>
              <div class="kpi-value">¥{{ summary?.confirmed_amount ?? '0.00' }}</div>
            </el-card>
            <el-card shadow="never" class="kpi">
              <div class="kpi-label">已结算</div>
              <div class="kpi-value ok">¥{{ summary?.paid_amount ?? '0.00' }}</div>
            </el-card>
          </div>

          <div class="panels">
            <el-card shadow="never" class="panel">
              <template #header>按场景分布</template>
              <el-table :data="summary?.by_scope || []" size="small" style="width: 100%">
                <el-table-column label="场景">
                  <template #default="{ row }">{{ commissionScopeLabel(row.scope) }}</template>
                </el-table-column>
                <el-table-column prop="record_count" label="记录数" width="90" />
                <el-table-column label="金额" width="120">
                  <template #default="{ row }">¥{{ row.total_amount }}</template>
                </el-table-column>
              </el-table>
            </el-card>

            <el-card shadow="never" class="panel">
              <template #header>销售业绩排行</template>
              <el-table :data="summary?.sellers || []" size="small" style="width: 100%">
                <el-table-column prop="staff_name" label="员工" />
                <el-table-column prop="order_count" label="成交单" width="90" />
                <el-table-column label="销售额" width="120">
                  <template #default="{ row }">¥{{ row.sales_amount }}</template>
                </el-table-column>
                <el-table-column label="提成" width="110">
                  <template #default="{ row }">¥{{ row.commission_amount }}</template>
                </el-table-column>
              </el-table>
            </el-card>
          </div>

          <el-card shadow="never" class="panel">
            <template #header>受益人明细</template>
            <el-table :data="summary?.by_beneficiary || []" size="small" style="width: 100%">
              <el-table-column prop="beneficiary_name" label="受益人" min-width="150" />
              <el-table-column label="身份" width="90">
                <template #default="{ row }">{{ beneficiaryTypeLabel(row.beneficiary_type) }}</template>
              </el-table-column>
              <el-table-column prop="record_count" label="记录数" width="90" />
              <el-table-column label="待确认" width="110">
                <template #default="{ row }">¥{{ row.pending_amount }}</template>
              </el-table-column>
              <el-table-column label="已确认" width="110">
                <template #default="{ row }">¥{{ row.confirmed_amount }}</template>
              </el-table-column>
              <el-table-column label="已结算" width="110">
                <template #default="{ row }">¥{{ row.paid_amount }}</template>
              </el-table-column>
              <el-table-column label="合计" width="120">
                <template #default="{ row }">
                  <strong>¥{{ row.total_amount }}</strong>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.toolbar h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}

.lead {
  margin: 0;
  max-width: 760px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--el-text-color-secondary);
}

.filters {
  margin-bottom: 4px;
}

.batch-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.sub {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 12px;
  margin-bottom: 14px;
}

.kpi-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.kpi-value {
  margin-top: 6px;
  font-size: 22px;
  font-weight: 600;
}

.kpi-value.warn {
  color: var(--el-color-warning);
}

.kpi-value.ok {
  color: var(--el-color-success);
}

.panels {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 12px;
}

.panel {
  margin-bottom: 12px;
}
</style>
