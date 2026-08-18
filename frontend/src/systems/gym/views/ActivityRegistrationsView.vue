<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { registrationStatusLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Activity = { id: number; name: string; status: string; starts_at: string; requires_payment: boolean }
type Registration = {
  id: number
  activity_id: number
  member_id: number
  status: string
  amount: string
  order_id: number | null
  checked_in_at: string | null
  note: string | null
  created_at: string
  member?: Member | null
  activity_name: string | null
  activity_starts_at: string | null
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const activities = ref<Activity[]>([])
const rows = ref<Registration[]>([])
const loading = ref(false)
const submitting = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dialog = ref(false)
const formRef = ref<FormInstance>()

const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})

const query = reactive({
  q: '',
  activity_id: undefined as number | undefined,
  status: '' as string,
})

const form = reactive({
  activity_id: undefined as number | undefined,
  member_id: undefined as number | undefined,
  note: '',
})

const rules: FormRules = {
  activity_id: [{ required: true, message: '请选择活动', trigger: 'change' }],
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
}

function fmtTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function memberText(row: Registration) {
  if (row.member) return `${row.member.name} ${row.member.phone}`
  const m = members.value.find((x) => x.id === row.member_id)
  return m ? `${m.name} ${m.phone}` : `#${row.member_id}`
}

function statusTagType(status: string) {
  if (status === 'attended') return 'success'
  if (status === 'pending') return 'warning'
  if (status === 'cancelled' || status === 'no_show') return 'info'
  return 'primary'
}

async function refresh() {
  loading.value = true
  try {
    const [m, mem] = await Promise.all([
      http.get('/merchants'),
      http.get('/members', { params: { page: 1, page_size: 100 } }),
    ])
    merchants.value = merchantsWithSystem(m.data, 'gym')
    members.value = mem.data.items
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const [act, reg] = await Promise.all([
      http.get<Page<Activity>>('/activities', {
        params: { merchant_id: merchantId.value, page: 1, page_size: 100 },
      }),
      http.get<Page<Registration>>('/activity-registrations', {
        params: {
          merchant_id: merchantId.value,
          activity_id: query.activity_id,
          status: query.status || undefined,
          q: query.q.trim() || undefined,
          page: page.value,
          page_size: pageSize.value,
        },
      }),
    ])
    activities.value = act.data.items
    rows.value = reg.data.items
    total.value = reg.data.total
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
  query.q = ''
  query.activity_id = undefined
  query.status = ''
  page.value = 1
  void refresh()
}

function openCreate() {
  if (!requireMerchant('请先选择商户后再代客报名')) return
  form.activity_id = activities.value.find((a) => a.status === 'published')?.id
  form.member_id = undefined
  form.note = ''
  formRef.value?.clearValidate()
  dialog.value = true
}

async function submit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    const { data } = await http.post('/activity-registrations', {
      activity_id: form.activity_id,
      member_id: form.member_id,
      note: form.note.trim() || null,
    })
    if (data.order) {
      ElMessage.success(`报名已登记，已生成待收款订单 #${data.order.id}，收款后自动确认`)
    } else {
      ElMessage.success('报名成功')
    }
    dialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '报名失败')
  } finally {
    submitting.value = false
  }
}

async function act(row: Registration, action: 'checkin' | 'cancel' | 'no-show') {
  if (action !== 'checkin') {
    const tips: Record<string, string> = {
      cancel: '确认取消该会员的报名？',
      'no-show': '确认标记该会员未到场？',
    }
    try {
      await ElMessageBox.confirm(tips[action], '操作确认', { type: 'warning' })
    } catch {
      return
    }
  }
  try {
    await http.post(`/activity-registrations/${row.id}/${action}`)
    ElMessage.success('操作成功')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>活动报名</h3>
        <p class="lead">前台代客报名与现场签到。收费活动生成待收款订单，收款后报名自动确认才可签到。</p>
      </div>
      <el-button type="primary" @click="openCreate">代客报名</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="活动">
        <el-select v-model="query.activity_id" clearable filterable placeholder="全部活动" style="width: 200px">
          <el-option v-for="a in activities" :key="a.id" :label="a.name" :value="a.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 130px">
          <el-option label="待付款" value="pending" />
          <el-option label="已确认" value="confirmed" />
          <el-option label="已签到" value="attended" />
          <el-option label="未到场" value="no_show" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="会员姓名 / 手机号 / 活动名" style="width: 220px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="活动" min-width="160">
        <template #default="{ row }">{{ row.activity_name || `#${row.activity_id}` }}</template>
      </el-table-column>
      <el-table-column label="开始时间" min-width="160">
        <template #default="{ row }">{{ fmtTime(row.activity_starts_at) }}</template>
      </el-table-column>
      <el-table-column label="会员" min-width="180">
        <template #default="{ row }">{{ memberText(row) }}</template>
      </el-table-column>
      <el-table-column label="费用" width="100">
        <template #default="{ row }">¥{{ row.amount }}</template>
      </el-table-column>
      <el-table-column label="订单" width="90">
        <template #default="{ row }">{{ row.order_id ? `#${row.order_id}` : '—' }}</template>
      </el-table-column>
      <el-table-column label="签到时间" min-width="160">
        <template #default="{ row }">{{ fmtTime(row.checked_in_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag size="small" :type="statusTagType(row.status)">{{ registrationStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="note" label="备注" min-width="140">
        <template #default="{ row }">{{ row.note || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="210" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" :disabled="row.status !== 'confirmed'" @click="act(row, 'checkin')">签到</el-button>
          <el-button link type="warning" :disabled="row.status !== 'confirmed'" @click="act(row, 'no-show')">未到</el-button>
          <el-button
            link
            type="danger"
            :disabled="!['pending', 'confirmed'].includes(row.status)"
            @click="act(row, 'cancel')"
          >
            取消
          </el-button>
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

    <el-dialog v-model="dialog" title="代客报名" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="活动" prop="activity_id">
          <el-select v-model="form.activity_id" filterable style="width: 100%">
            <el-option
              v-for="a in activities.filter((x) => x.status === 'published')"
              :key="a.id"
              :label="a.name"
              :value="a.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="会员" prop="member_id">
          <el-select v-model="form.member_id" filterable style="width: 100%">
            <el-option v-for="x in members" :key="x.id" :label="`${x.name} ${x.phone}`" :value="x.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" maxlength="255" placeholder="选填" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">确认报名</el-button>
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
  margin-bottom: 20px;
}

.toolbar h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}

.lead {
  margin: 0;
  max-width: 640px;
  font-size: 13px;
  line-height: 1.55;
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
