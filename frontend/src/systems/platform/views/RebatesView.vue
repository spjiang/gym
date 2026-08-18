<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import { REBATE_LEDGER_KIND_LABELS, rebateLedgerKindLabel } from '../../../core/labels'

type Ledger = {
  id: number
  member_id: number
  member_name: string | null
  kind: string
  amount: string
  balance_after: string
  order_id: number | null
  from_member_name: string | null
  base_amount: string | null
  rate: string | null
  note: string | null
  created_at: string
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }
type Account = {
  balance: string
  frozen_amount: string
  debt_amount: string
  total_earned: string
  total_withdrawn: string
}
type Member = { id: number; name: string; phone: string }

const rows = ref<Ledger[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({
  q_member_id: undefined as number | undefined,
  kind: '',
  range: undefined as [string, string] | undefined,
})
const members = ref<Member[]>([])

const adjustDialog = ref(false)
const adjustMemberId = ref<number | undefined>()
const adjustAmount = ref('')
const adjustNote = ref('')
const submitting = ref(false)

function fmtTime(iso: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadMembers() {
  try {
    const { data } = await http.get<Page<Member>>('/members', { params: { page: 1, page_size: 200 } })
    members.value = data.items
  } catch {
    members.value = []
  }
}

async function refresh() {
  loading.value = true
  try {
    const { data } = await http.get<Page<Ledger>>('/rebate-ledgers', {
      params: {
        member_id: query.q_member_id,
        kind: query.kind || undefined,
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
  query.q_member_id = undefined
  query.kind = ''
  query.range = undefined
  page.value = 1
  void refresh()
}

function openAdjust(memberId?: number) {
  adjustMemberId.value = memberId ?? query.q_member_id
  adjustAmount.value = ''
  adjustNote.value = ''
  adjustDialog.value = true
}

async function submitAdjust() {
  if (!adjustMemberId.value) {
    ElMessage.warning('请选择会员')
    return
  }
  if (!adjustAmount.value || Number(adjustAmount.value) === 0) {
    ElMessage.warning('请填写非零金额，正数为补发，负数为扣减')
    return
  }
  if (!adjustNote.value.trim()) {
    ElMessage.warning('请填写调整原因')
    return
  }
  submitting.value = true
  try {
    const { data } = await http.post<Account>(`/members/${adjustMemberId.value}/rebate-adjust`, {
      amount: adjustAmount.value,
      note: adjustNote.value.trim(),
    })
    ElMessage.success(`已调整，当前余额 ¥${data.balance}`)
    adjustDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '调整失败')
  } finally {
    submitting.value = false
  }
}

onMounted(async () => {
  await loadMembers()
  await refresh()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>会员返点</h3>
        <p class="lead">
          下级消费入账、退款冲回与提现冻结均记在此。返点余额只用于线下提现，不能抵扣消费。
        </p>
      </div>
      <el-button type="primary" @click="openAdjust()">人工调账</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="会员">
        <el-select v-model="query.q_member_id" filterable clearable placeholder="全部" style="width: 200px">
          <el-option v-for="m in members" :key="m.id" :label="`${m.name} ${m.phone}`" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="query.kind" clearable placeholder="全部" style="width: 150px">
          <el-option v-for="(label, code) in REBATE_LEDGER_KIND_LABELS" :key="code" :label="label" :value="code" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期">
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
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="会员" min-width="140">
        <template #default="{ row }">{{ row.member_name || `#${row.member_id}` }}</template>
      </el-table-column>
      <el-table-column label="类型" width="130">
        <template #default="{ row }">{{ rebateLedgerKindLabel(row.kind) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="120">
        <template #default="{ row }">
          <span :class="Number(row.amount) < 0 ? 'neg' : 'pos'">{{ Number(row.amount) > 0 ? '+' : '' }}¥{{ row.amount }}</span>
        </template>
      </el-table-column>
      <el-table-column label="余额" width="110">
        <template #default="{ row }">¥{{ row.balance_after }}</template>
      </el-table-column>
      <el-table-column label="来源下级" min-width="120">
        <template #default="{ row }">{{ row.from_member_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="订单" width="90">
        <template #default="{ row }">{{ row.order_id ? `#${row.order_id}` : '—' }}</template>
      </el-table-column>
      <el-table-column label="口径" min-width="140">
        <template #default="{ row }">
          <span v-if="row.base_amount">¥{{ row.base_amount }} × {{ row.rate || '—' }}</span>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="150">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="note" label="备注" min-width="160" show-overflow-tooltip />
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

    <el-dialog v-model="adjustDialog" title="人工调整返点余额" width="460px" destroy-on-close>
      <el-form label-width="90px">
        <el-form-item label="会员">
          <el-select v-model="adjustMemberId" filterable style="width: 100%">
            <el-option v-for="m in members" :key="m.id" :label="`${m.name} ${m.phone}`" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额">
          <el-input v-model="adjustAmount" placeholder="正数补发，负数扣减" />
        </el-form-item>
        <el-form-item label="原因">
          <el-input v-model="adjustNote" type="textarea" :rows="2" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="adjustDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitAdjust">确认调整</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}
.lead {
  margin: 0;
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
.pos {
  color: var(--el-color-success);
}
.neg {
  color: var(--el-color-danger);
}
</style>
