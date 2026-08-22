<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { commissionScopeLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type StaffOption = { id: number; display_name: string; username: string }
type MemberOption = { id: number; name: string; phone: string }
type CommissionRule = { id: number; name: string; scope: string; is_active: boolean }
type SalesRep = {
  id: number
  merchant_id: number
  staff_user_id: number
  member_id: number
  display_name: string
  commission_rule_id?: number | null
  commission_rule_name?: string | null
  is_active: boolean
  staff_username?: string | null
  member_name?: string | null
  member_phone?: string | null
}

const SALE_SCOPES = ['membership_sale', 'pt_sale', 'retail_sale', 'activity_sale']

const merchants = ref<Merchant[]>([])
const staffOptions = ref<StaffOption[]>([])
const members = ref<MemberOption[]>([])
const commissionRules = ref<CommissionRule[]>([])
const rows = ref<SalesRep[]>([])
const loading = ref(false)
const submitting = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})

const query = reactive({ q: '', status: '' as '' | 'active' | 'inactive' })

const form = reactive({
  staff_user_id: undefined as number | undefined,
  member_id: undefined as number | undefined,
  display_name: '',
  commission_rule_id: undefined as number | undefined,
})

const rules: FormRules = {
  staff_user_id: [{ required: true, message: '请选择后台员工', trigger: 'change' }],
  member_id: [{ required: true, message: '请选择关联会员', trigger: 'change' }],
  display_name: [{ required: true, message: '请填写显示名', trigger: 'blur' }],
}

const saleRules = computed(() =>
  commissionRules.value.filter((r) => r.is_active && SALE_SCOPES.includes(r.scope)),
)

function staffLabel(s: StaffOption) {
  return `${s.display_name || s.username} (${s.username})`
}

function staffName(id: number | null | undefined, row?: SalesRep) {
  if (id == null) return '—'
  const s = staffOptions.value.find((x) => x.id === id)
  if (s) return staffLabel(s)
  if (row?.staff_username) return `${row.display_name} (${row.staff_username})`
  return `#${id}`
}

function merchantName(id: number) {
  return merchants.value.find((m) => m.id === id)?.name || `#${id}`
}

function memberLabel(m: MemberOption) {
  return `${m.name} · ${m.phone}`
}

function ruleLabel(r: CommissionRule) {
  return `${r.name}（${commissionScopeLabel(r.scope)}）`
}

async function loadDialogData(mid: number) {
  const [staffResp, memberResp, ruleResp] = await Promise.all([
    http.get<StaffOption[]>('/staff/options', { params: { merchant_id: mid } }),
    http.get<{ items: MemberOption[] }>('/members', {
      params: { merchant_id: mid, page: 1, page_size: 100 },
    }),
    http.get<{ items: CommissionRule[] }>('/commission-rules', {
      params: { merchant_id: mid, is_active: true, page: 1, page_size: 100 },
    }),
  ])
  staffOptions.value = staffResp.data || []
  members.value = memberResp.data.items || []
  commissionRules.value = ruleResp.data.items || []
}

async function refresh() {
  loading.value = true
  try {
    const merch = await http.get<Merchant[]>('/merchants')
    merchants.value = merchantsWithSystem(merch.data, 'gym')
    const { data } = await http.get<{ items: SalesRep[]; total: number }>('/sales-reps', {
      params: {
        merchant_id: merchantId.value,
        q: query.q.trim() || undefined,
        is_active: query.status === 'active' ? true : query.status === 'inactive' ? false : undefined,
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

async function openCreate() {
  const mid = requireMerchant('请先选择商户')
  if (!mid) return
  editingId.value = null
  form.staff_user_id = undefined
  form.member_id = undefined
  form.display_name = ''
  form.commission_rule_id = undefined
  formRef.value?.clearValidate()
  try {
    await loadDialogData(mid)
    dialogVisible.value = true
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载表单数据失败')
  }
}

async function openEdit(row: SalesRep) {
  editingId.value = row.id
  form.staff_user_id = row.staff_user_id
  form.member_id = row.member_id
  form.display_name = row.display_name
  form.commission_rule_id = row.commission_rule_id ?? undefined
  formRef.value?.clearValidate()
  try {
    await loadDialogData(row.merchant_id)
    if (row.member_id && row.member_name) {
      members.value = [
        { id: row.member_id, name: row.member_name, phone: row.member_phone || '' },
        ...members.value.filter((x) => x.id !== row.member_id),
      ]
    }
    dialogVisible.value = true
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载表单数据失败')
  }
}

async function submit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  const mid = editingId.value
    ? rows.value.find((r) => r.id === editingId.value)?.merchant_id
    : requireMerchant('请先选择商户')
  if (!mid) return
  submitting.value = true
  try {
    const payload = {
      merchant_id: mid,
      staff_user_id: form.staff_user_id,
      member_id: form.member_id,
      display_name: form.display_name.trim(),
      commission_rule_id: form.commission_rule_id ?? null,
    }
    if (editingId.value) {
      await http.patch(`/sales-reps/${editingId.value}`, payload)
    } else {
      await http.post('/sales-reps', payload)
    }
    ElMessage.success('已保存')
    dialogVisible.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function deactivate(row: SalesRep) {
  try {
    await http.post(`/sales-reps/${row.id}/deactivate`)
    ElMessage.success('已停用')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

onMounted(() => {
  void refresh()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>销售管理</h3>
        <p class="lead">
          每位销售必须关联会员主档，并可选绑定销售提成规则；未绑规则时按商户默认规则（同场景优先级）计提。
        </p>
      </div>
      <el-button type="primary" @click="openCreate">新建销售</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="启用" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="姓名 / 员工 / 会员" style="width: 180px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="refresh">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column v-if="!merchantId" label="商户" width="120">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
      <el-table-column prop="display_name" label="显示名" min-width="120" />
      <el-table-column label="后台员工" min-width="160">
        <template #default="{ row }">{{ staffName(row.staff_user_id, row) }}</template>
      </el-table-column>
      <el-table-column label="关联会员" min-width="180">
        <template #default="{ row }">
          <div>{{ row.member_name || '—' }}</div>
          <div class="sub">{{ row.member_phone || '' }}</div>
        </template>
      </el-table-column>
      <el-table-column label="销售提成规则" min-width="160">
        <template #default="{ row }">{{ row.commission_rule_name || '商户默认' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.is_active ? 'success' : 'info'">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.is_active" link type="warning" @click="deactivate(row)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        background
        @current-change="refresh"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑销售' : '新建销售'" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="后台员工" prop="staff_user_id">
          <el-select v-model="form.staff_user_id" filterable placeholder="开单时登录的账号" style="width: 100%">
            <el-option v-for="s in staffOptions" :key="s.id" :label="staffLabel(s)" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="关联会员" prop="member_id">
          <el-select v-model="form.member_id" filterable placeholder="提成记在此会员" style="width: 100%">
            <el-option v-for="m in members" :key="m.id" :label="memberLabel(m)" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="销售提成规则">
          <el-select
            v-model="form.commission_rule_id"
            filterable
            clearable
            placeholder="留空则按商户默认规则"
            style="width: 100%"
          >
            <el-option v-for="r in saleRules" :key="r.id" :label="ruleLabel(r)" :value="r.id" />
          </el-select>
          <p class="hint">规则场景须为会籍/课包/零售/活动销售，且受益方为销售。</p>
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="form.display_name" maxlength="64" placeholder="如 前台小王" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
      </template>
    </el-dialog>
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
.sub,
.hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.hint {
  margin: 6px 0 0;
}
</style>
