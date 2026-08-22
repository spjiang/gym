<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'
import {
  commissionScopeLabel,
  commissionCategoryLabel,
  commissionStatusLabel,
  payoutStatusLabel,
  percentLabel,
} from '../../../core/labels'

type CoachSlice = {
  coach_id: number
  display_name: string
  title: string | null
  pt_commission_rate: string | null
}
type SalesSlice = {
  sales_rep_id: number
  display_name: string
  promotion_code: string | null
}
type Profile = {
  display_name: string
  roles: string[]
  coach: CoachSlice | null
  sales_rep: SalesSlice | null
}
type Summary = {
  display_name: string
  roles: string[]
  pending_amount: string
  confirmed_amount: string
  paid_amount: string
  total_amount: string
  settleable_amount: string
  settleable_count: number
  withdrawing_amount: string
  debt_amount?: string
  settle_hold_days?: number
  by_scope: { scope: string; count: number; amount: string }[]
}
type Record_ = {
  id: number
  scope: string
  category: string
  source_type: string
  source_id: number
  order_id: number | null
  amount: string
  base_amount: string
  rate: string | null
  status: string
  note: string | null
  created_at: string
}
type Payout = {
  id: number
  amount: string
  status: string
  method: string | null
  reject_reason: string | null
  created_at: string
  paid_at: string | null
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const profile = ref<Profile | null>(null)
const summary = ref<Summary | null>(null)
const records = ref<Record_[]>([])
const payouts = ref<Payout[]>([])
const loading = ref(false)
const noProfile = ref(false)
const recordTotal = ref(0)
const recordPage = ref(1)
const payoutTotal = ref(0)
const payoutPage = ref(1)
const query = reactive({ status: '' })
const submitting = ref(false)

const roleHint = computed(() => {
  const roles = profile.value?.roles || []
  if (roles.includes('sales') && roles.includes('coach')) {
    return '销售开单提成与教练课时提成均展示在此。'
  }
  if (roles.includes('sales')) {
    return '展示当前登录销售绑定会员的开单提成（会籍、零售、课包等）。'
  }
  return '展示当前登录教练绑定会员的课时提成。'
})

function fmtTime(iso: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function refresh() {
  loading.value = true
  noProfile.value = false
  try {
    const [p, s, r, w] = await Promise.all([
      http.get<Profile>('/my/commission-profile'),
      http.get<Summary>('/my/commission-summary'),
      http.get<Page<Record_>>('/my/commission-records', {
        params: { status: query.status || undefined, page: recordPage.value, page_size: 20 },
      }),
      http.get<Page<Payout>>('/my/payouts', { params: { page: payoutPage.value, page_size: 20 } }),
    ])
    profile.value = p.data
    summary.value = s.data
    records.value = r.data.items
    recordTotal.value = r.data.total
    payouts.value = w.data.items
    payoutTotal.value = w.data.total
  } catch (e: unknown) {
    const msg = e instanceof Error ? e.message : '加载失败'
    if (msg.includes('未绑定') || msg.includes('not_found')) {
      noProfile.value = true
      profile.value = null
      summary.value = null
      records.value = []
      payouts.value = []
      return
    }
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function requestPayout() {
  const amount = summary.value?.settleable_amount
  const count = summary.value?.settleable_count || 0
  if (!count) {
    ElMessage.warning('暂无可提现的已确认佣金')
    return
  }
  try {
    const debt = Number(summary.value?.debt_amount || 0)
    const debtHint = debt > 0 ? `将优先抵扣欠额 ¥${summary.value?.debt_amount}，现金以审核页为准。` : '打款由运营线下完成。'
    await ElMessageBox.confirm(
      `申请提现已确认佣金 ${count} 笔，合计 ¥${amount}。${debtHint}`,
      '申请提现',
      { type: 'info' },
    )
  } catch {
    return
  }
  submitting.value = true
  try {
    await http.post('/my/payouts', {})
    ElMessage.success('已提交提现申请')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '申请失败')
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
        <h3>我的佣金</h3>
        <p class="lead">
          {{ roleHint }}每笔有类别，并可追溯到具体订单 / 场次 / 预约。提现线下打款，进度在此同步。
          <template v-if="Number(summary?.settle_hold_days || 0) > 0">
            计提满 {{ summary?.settle_hold_days }} 天后方可提现。
          </template>
        </p>
      </div>
      <el-button v-if="!noProfile" type="primary" :loading="submitting" @click="requestPayout">申请提现</el-button>
    </div>

    <el-alert
      v-if="noProfile"
      type="info"
      :closable="false"
      show-icon
      title="当前账号未绑定销售或教练档案"
      description="此页仅供已绑定档案的销售/教练查看本人提成。管理员请使用「提成结算」查看全员数据。"
      class="no-profile"
    />

    <template v-if="!noProfile">
    <el-descriptions v-if="profile" :column="3" border class="profile">
      <el-descriptions-item label="姓名">{{ profile.display_name }}</el-descriptions-item>
      <el-descriptions-item v-if="profile.sales_rep" label="销售档案">
        {{ profile.sales_rep.display_name }}
        <template v-if="profile.sales_rep.promotion_code">
          · 推广码 {{ profile.sales_rep.promotion_code }}
        </template>
      </el-descriptions-item>
      <el-descriptions-item v-if="profile.coach" label="教练档案">
        {{ profile.coach.display_name }}
        <template v-if="profile.coach.title"> · {{ profile.coach.title }}</template>
      </el-descriptions-item>
      <el-descriptions-item v-if="profile.coach" label="私教提成比例">
        {{ profile.coach.pt_commission_rate ? percentLabel(profile.coach.pt_commission_rate) : '按商户规则' }}
      </el-descriptions-item>
    </el-descriptions>

    <div v-loading="loading" class="kpis">
      <el-card shadow="never">
        <div class="kpi-label">待确认</div>
        <div class="kpi-value">¥{{ summary?.pending_amount ?? '0.00' }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="kpi-label">可提现（已确认）</div>
        <div class="kpi-value">¥{{ summary?.settleable_amount ?? '0.00' }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="kpi-label">提现中</div>
        <div class="kpi-value">¥{{ summary?.withdrawing_amount ?? '0.00' }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="kpi-label">待追回欠额</div>
        <div class="kpi-value">¥{{ summary?.debt_amount ?? '0.00' }}</div>
      </el-card>
      <el-card shadow="never">
        <div class="kpi-label">已打款</div>
        <div class="kpi-value">¥{{ summary?.paid_amount ?? '0.00' }}</div>
      </el-card>
    </div>

    <el-tabs>
      <el-tab-pane label="佣金明细">
        <el-form inline>
          <el-form-item label="状态">
            <el-select v-model="query.status" clearable placeholder="全部" style="width: 140px" @change="refresh">
              <el-option label="待确认" value="pending" />
              <el-option label="已确认" value="confirmed" />
              <el-option label="已结算" value="paid" />
            </el-select>
          </el-form-item>
        </el-form>
        <el-table :data="records" size="small" stripe>
          <el-table-column label="类别" width="100">
            <template #default="{ row }">{{ commissionCategoryLabel(row.category) }}</template>
          </el-table-column>
          <el-table-column label="场景" width="120">
            <template #default="{ row }">{{ commissionScopeLabel(row.scope) }}</template>
          </el-table-column>
          <el-table-column label="来源" min-width="140">
            <template #default="{ row }">
              {{ row.source_type }} #{{ row.source_id }}
              <template v-if="row.order_id"> · 订单 #{{ row.order_id }}</template>
            </template>
          </el-table-column>
          <el-table-column label="口径" min-width="150">
            <template #default="{ row }">
              ¥{{ row.base_amount }} × {{ row.rate ? percentLabel(row.rate) : '规则' }}
            </template>
          </el-table-column>
          <el-table-column label="金额" width="110">
            <template #default="{ row }">¥{{ row.amount }}</template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">{{ commissionStatusLabel(row.status) }}</template>
          </el-table-column>
          <el-table-column label="时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column prop="note" label="备注" min-width="140" />
        </el-table>
        <div class="pager">
          <el-pagination
            v-model:current-page="recordPage"
            :total="recordTotal"
            layout="total, prev, pager, next"
            background
            @current-change="refresh"
          />
        </div>
      </el-tab-pane>
      <el-tab-pane label="提现记录">
        <el-table :data="payouts" size="small" stripe empty-text="暂无提现">
          <el-table-column prop="id" label="单号" width="80" />
          <el-table-column label="金额" width="120">
            <template #default="{ row }">¥{{ row.amount }}</template>
          </el-table-column>
          <el-table-column label="状态" width="140">
            <template #default="{ row }">{{ payoutStatusLabel(row.status) }}</template>
          </el-table-column>
          <el-table-column label="申请时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="打款时间" width="150">
            <template #default="{ row }">{{ fmtTime(row.paid_at) }}</template>
          </el-table-column>
          <el-table-column label="说明" min-width="160">
            <template #default="{ row }">{{ row.reject_reason || row.method || '—' }}</template>
          </el-table-column>
        </el-table>
        <div class="pager">
          <el-pagination
            v-model:current-page="payoutPage"
            :total="payoutTotal"
            layout="total, prev, pager, next"
            background
            @current-change="refresh"
          />
        </div>
      </el-tab-pane>
    </el-tabs>
    </template>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
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
.profile {
  margin-bottom: 14px;
}
.no-profile {
  margin-bottom: 16px;
}
.kpis {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}
.kpi-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.kpi-value {
  margin-top: 6px;
  font-size: 20px;
  font-weight: 600;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
