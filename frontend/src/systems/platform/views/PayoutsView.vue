<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'
import {
  PAYOUT_SOURCE_LABELS,
  PAYOUT_STATUS_LABELS,
  payoutMethodLabel,
  payoutSourceLabel,
  payoutStatusLabel,
} from '../../../core/labels'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Payout = {
  id: number
  merchant_id: number | null
  source: string
  beneficiary_type: string
  beneficiary_id: number
  beneficiary_name: string
  amount: string
  status: string
  method: string | null
  external_ref: string | null
  note: string | null
  reject_reason: string | null
  paid_at: string | null
  created_at: string
  item_count: number
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

type Merchant = { id: number; name: string }

const rows = ref<Payout[]>([])
const merchants = ref<Merchant[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const { merchantId } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const query = reactive({
  source: '',
  status: 'requested' as string,
  range: undefined as [string, string] | undefined,
})

const payDialog = ref(false)
const payTarget = ref<Payout | null>(null)
const payForm = reactive({ method: 'offline_transfer', external_ref: '', note: '' })
const submitting = ref(false)

function fmtTime(iso: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function statusType(status: string) {
  if (status === 'paid') return 'success'
  if (status === 'approved') return 'primary'
  if (status === 'requested') return 'warning'
  return 'info'
}

async function refresh() {
  loading.value = true
  try {
    if (!merchants.value.length) {
      const { data } = await http.get<Merchant[]>('/merchants')
      merchants.value = data
    }
    const { data } = await http.get<Page<Payout>>('/payouts', {
      params: {
        merchant_id: merchantId.value,
        source: query.source || undefined,
        status: query.status || undefined,
        date_from: query.range?.[0],
        date_to: query.range?.[1],
        page: page.value,
        page_size: pageSize.value,
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
  void refresh()
}

function resetSearch() {
  query.source = ''
  query.status = ''
  query.range = undefined
  page.value = 1
  void refresh()
}

async function approve(row: Payout) {
  try {
    await ElMessageBox.confirm(`通过 ${row.beneficiary_name} 的 ¥${row.amount} 提现申请？`, '审核通过', {
      type: 'info',
    })
  } catch {
    return
  }
  try {
    await http.post(`/payouts/${row.id}/approve`)
    ElMessage.success('已通过，待线下打款')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

async function reject(row: Payout) {
  try {
    const { value } = await ElMessageBox.prompt('请填写驳回原因', '驳回提现', {
      inputPlaceholder: '原因将展示给申请人',
      confirmButtonText: '驳回',
    })
    await http.post(`/payouts/${row.id}/reject`, { reason: value || null })
    ElMessage.success('已驳回，资金已解冻')
    await refresh()
  } catch (e: unknown) {
    if (e !== 'cancel') ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

function openPay(row: Payout) {
  payTarget.value = row
  payForm.method = 'offline_transfer'
  payForm.external_ref = ''
  payForm.note = ''
  payDialog.value = true
}

async function submitPay() {
  if (!payTarget.value) return
  submitting.value = true
  try {
    await http.post(`/payouts/${payTarget.value.id}/pay`, {
      method: payForm.method,
      external_ref: payForm.external_ref.trim() || null,
      note: payForm.note.trim() || null,
    })
    ElMessage.success('已登记线下打款')
    payDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '登记失败')
  } finally {
    submitting.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>提现审核</h3>
        <p class="lead">
          会员返点与教练佣金提现均在此审核。打款在线下完成，登记后系统把状态同步为已完成。
        </p>
      </div>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 200px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="来源">
        <el-select v-model="query.source" clearable placeholder="全部" style="width: 140px">
          <el-option v-for="(label, code) in PAYOUT_SOURCE_LABELS" :key="code" :label="label" :value="code" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 150px">
          <el-option v-for="(label, code) in PAYOUT_STATUS_LABELS" :key="code" :label="label" :value="code" />
        </el-select>
      </el-form-item>
      <el-form-item label="申请日期">
        <el-date-picker
          v-model="query.range"
          type="daterange"
          value-format="YYYY-MM-DD"
          start-placeholder="开始"
          end-placeholder="结束"
          style="width: 240px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="单号" width="80" />
      <el-table-column label="来源" width="110">
        <template #default="{ row }">{{ payoutSourceLabel(row.source) }}</template>
      </el-table-column>
      <el-table-column prop="beneficiary_name" label="收款人" min-width="160" />
      <el-table-column label="金额" width="120">
        <template #default="{ row }">
          <strong>¥{{ row.amount }}</strong>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="130">
        <template #default="{ row }">
          <el-tag size="small" :type="statusType(row.status)">{{ payoutStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="申请时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="打款" min-width="160">
        <template #default="{ row }">
          <span v-if="row.status === 'paid'">
            {{ payoutMethodLabel(row.method) }} {{ row.external_ref || '' }}
          </span>
          <span v-else-if="row.reject_reason">{{ row.reject_reason }}</span>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button v-if="row.status === 'requested'" link type="primary" @click="approve(row)">通过</el-button>
          <el-button v-if="row.status === 'requested'" link type="danger" @click="reject(row)">驳回</el-button>
          <el-button v-if="row.status === 'requested' || row.status === 'approved'" link type="success" @click="openPay(row)">
            登记打款
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
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

    <el-dialog v-model="payDialog" title="登记线下打款" width="460px" destroy-on-close>
      <p class="lead">{{ payTarget?.beneficiary_name }} · ¥{{ payTarget?.amount }}</p>
      <el-form label-width="100px">
        <el-form-item label="打款方式">
          <el-select v-model="payForm.method" style="width: 100%">
            <el-option label="转账" value="offline_transfer" />
            <el-option label="现金" value="offline_cash" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="凭证号">
          <el-input v-model="payForm.external_ref" maxlength="64" placeholder="转账流水号，选填" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="payForm.note" type="textarea" :rows="2" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="payDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitPay">确认已打款</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}
.lead {
  margin: 0 0 16px;
  max-width: 720px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.filters {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
