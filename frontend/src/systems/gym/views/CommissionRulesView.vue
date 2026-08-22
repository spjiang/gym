<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import {
  COMMISSION_BASIS_LABELS,
  COMMISSION_SCOPE_LABELS,
  commissionBasisLabel,
  commissionBeneficiaryLabel,
  commissionScopeLabel,
} from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Rule = {
  id: number
  merchant_id: number
  name: string
  scope: string
  beneficiary: string
  basis: string
  rate: string | null
  unit_amount: string | null
  min_base_amount: string | null
  max_amount: string | null
  first_order_only: boolean
  priority: number
  effective_from: string | null
  effective_to: string | null
  is_active: boolean
  remark: string | null
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

/** 场景 → 默认受益方 */
const DEFAULT_BENEFICIARY_BY_SCOPE: Record<string, string> = {
  membership_sale: 'seller',
  pt_sale: 'seller',
  retail_sale: 'seller',
  activity_sale: 'seller',
  group_session: 'coach',
  pt_session: 'coach',
  referral: 'referrer',
}

/** 各场景允许的受益方 */
const ALLOWED_BENEFICIARIES_BY_SCOPE: Record<string, string[]> = {
  membership_sale: ['seller', 'coach'],
  pt_sale: ['seller', 'coach'],
  retail_sale: ['seller', 'coach'],
  activity_sale: ['seller', 'coach'],
  group_session: ['coach', 'seller'],
  pt_session: ['coach', 'seller'],
  referral: ['referrer'],
}

/** 各场景允许的计提方式 */
const BASIS_BY_SCOPE: Record<string, string[]> = {
  membership_sale: ['percent', 'fixed'],
  pt_sale: ['percent', 'fixed'],
  retail_sale: ['percent', 'fixed'],
  activity_sale: ['percent', 'fixed'],
  group_session: ['per_head', 'fixed'],
  pt_session: ['percent', 'fixed', 'per_session'],
  referral: ['percent', 'fixed'],
}

const merchants = ref<Merchant[]>([])
const rows = ref<Rule[]>([])
const loading = ref(false)
const submitting = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dialog = ref(false)
const editing = ref<Rule | null>(null)
const formRef = ref<FormInstance>()

const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})

const query = reactive({ q: '', scope: '', is_active: undefined as boolean | undefined })

const form = reactive({
  name: '',
  scope: 'membership_sale',
  beneficiary: 'seller',
  basis: 'percent',
  rate: '',
  unit_amount: '',
  min_base_amount: '',
  max_amount: '',
  first_order_only: false,
  priority: 100,
  effective_from: '',
  effective_to: '',
  is_active: true,
  remark: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请填写规则名称', trigger: 'blur' }],
}

const dialogTitle = computed(() => (editing.value ? `编辑规则 #${editing.value.id}` : '新建分成规则'))
const allowedBeneficiaries = computed(
  () => ALLOWED_BENEFICIARIES_BY_SCOPE[form.scope] || ['seller'],
)
const allowedBasis = computed(() => BASIS_BY_SCOPE[form.scope] || ['percent', 'fixed'])
const isPercent = computed(() => form.basis === 'percent')

watch(
  () => form.scope,
  (scope) => {
    if (!allowedBasis.value.includes(form.basis)) form.basis = allowedBasis.value[0]
    const allowed = ALLOWED_BENEFICIARIES_BY_SCOPE[scope] || ['seller']
    if (!allowed.includes(form.beneficiary)) {
      form.beneficiary = DEFAULT_BENEFICIARY_BY_SCOPE[scope] || allowed[0]
    }
  },
)

function ruleValueText(row: Rule) {
  if (row.basis === 'percent') {
    const pct = row.rate ? (Number(row.rate) * 100).toFixed(2).replace(/\.?0+$/, '') : '0'
    return `${pct}%`
  }
  const suffix = row.basis === 'per_head' ? ' / 人' : row.basis === 'per_session' ? ' / 节' : ''
  return `¥${row.unit_amount ?? '0'}${suffix}`
}

function fmtTime(iso: string | null) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function refresh() {
  loading.value = true
  try {
    const m = await http.get('/merchants')
    merchants.value = merchantsWithSystem(m.data, 'gym')
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const { data } = await http.get<Page<Rule>>('/commission-rules', {
      params: {
        merchant_id: merchantId.value,
        scope: query.scope || undefined,
        is_active: query.is_active,
        q: query.q.trim() || undefined,
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
  query.q = ''
  query.scope = ''
  query.is_active = undefined
  page.value = 1
  void refresh()
}

function openCreate() {
  if (!requireMerchant('请先选择商户后再配置分成规则')) return
  editing.value = null
  Object.assign(form, {
    name: '',
    scope: 'membership_sale',
    beneficiary: 'seller',
    basis: 'percent',
    rate: '',
    unit_amount: '',
    min_base_amount: '',
    max_amount: '',
    first_order_only: false,
    priority: 100,
    effective_from: '',
    effective_to: '',
    is_active: true,
    remark: '',
  })
  formRef.value?.clearValidate()
  dialog.value = true
}

function openEdit(row: Rule) {
  editing.value = row
  Object.assign(form, {
    name: row.name,
    scope: row.scope,
    beneficiary: row.beneficiary,
    basis: row.basis,
    rate: row.rate ?? '',
    unit_amount: row.unit_amount ?? '',
    min_base_amount: row.min_base_amount ?? '',
    max_amount: row.max_amount ?? '',
    first_order_only: row.first_order_only,
    priority: row.priority,
    effective_from: row.effective_from ?? '',
    effective_to: row.effective_to ?? '',
    is_active: row.is_active,
    remark: row.remark ?? '',
  })
  formRef.value?.clearValidate()
  dialog.value = true
}

function payload(mid: number) {
  return {
    merchant_id: mid,
    name: form.name.trim(),
    scope: form.scope,
    beneficiary: form.beneficiary,
    basis: form.basis,
    rate: isPercent.value ? form.rate || null : null,
    unit_amount: isPercent.value ? null : form.unit_amount || null,
    min_base_amount: form.min_base_amount || null,
    max_amount: form.max_amount || null,
    first_order_only: form.scope === 'referral' ? form.first_order_only : false,
    priority: form.priority,
    effective_from: form.effective_from || null,
    effective_to: form.effective_to || null,
    is_active: form.is_active,
    remark: form.remark.trim() || null,
  }
}

async function submit() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  const mid = editing.value?.merchant_id ?? requireMerchant('请先选择商户后再配置分成规则')
  if (!mid) return
  submitting.value = true
  try {
    if (editing.value) {
      await http.patch(`/commission-rules/${editing.value.id}`, payload(mid))
    } else {
      await http.post('/commission-rules', payload(mid))
    }
    ElMessage.success('已保存')
    dialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function remove(row: Rule) {
  try {
    await ElMessageBox.confirm(
      `删除规则「${row.name}」？已产生提成记录的规则将自动改为停用以保留对账链路。`,
      '删除确认',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    const { data } = await http.delete(`/commission-rules/${row.id}`)
    ElMessage.success(data.deactivated ? '规则已停用（存在历史提成记录）' : '已删除')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

async function toggle(row: Rule) {
  try {
    await http.patch(`/commission-rules/${row.id}`, {
      merchant_id: row.merchant_id,
      name: row.name,
      scope: row.scope,
      beneficiary: row.beneficiary,
      basis: row.basis,
      rate: row.rate,
      unit_amount: row.unit_amount,
      min_base_amount: row.min_base_amount,
      max_amount: row.max_amount,
      first_order_only: row.first_order_only,
      priority: row.priority,
      effective_from: row.effective_from,
      effective_to: row.effective_to,
      is_active: !row.is_active,
      remark: row.remark,
    })
    ElMessage.success(row.is_active ? '已停用' : '已启用')
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
        <h3>分成规则</h3>
        <p class="lead">
          按业务场景配置提成规则：销售类（会籍/课包/零售/活动）受益方为销售，课时类（团课/私教）受益方为教练，推荐成交用于会员返点比例为 0 时的 fallback。同场景多条规则时按优先级取首条；销售/教练档案可绑定指定规则覆盖默认。
        </p>
      </div>
      <el-button type="primary" @click="openCreate">新建规则</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="场景">
        <el-select v-model="query.scope" clearable placeholder="全部" style="width: 160px">
          <el-option v-for="(label, code) in COMMISSION_SCOPE_LABELS" :key="code" :label="label" :value="code" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.is_active" clearable placeholder="全部" style="width: 120px">
          <el-option label="启用" :value="true" />
          <el-option label="停用" :value="false" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="规则名称" style="width: 180px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe style="width: 100%">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="规则" min-width="180" />
      <el-table-column label="场景" width="130">
        <template #default="{ row }">{{ commissionScopeLabel(row.scope) }}</template>
      </el-table-column>
      <el-table-column label="受益方" width="100">
        <template #default="{ row }">{{ commissionBeneficiaryLabel(row.beneficiary) }}</template>
      </el-table-column>
      <el-table-column label="计提方式" width="120">
        <template #default="{ row }">{{ commissionBasisLabel(row.basis) }}</template>
      </el-table-column>
      <el-table-column label="额度" width="120">
        <template #default="{ row }">{{ ruleValueText(row) }}</template>
      </el-table-column>
      <el-table-column label="门槛/上限" min-width="150">
        <template #default="{ row }">
          <span>{{ row.min_base_amount ? `满 ¥${row.min_base_amount}` : '不限门槛' }}</span>
          <span> · </span>
          <span>{{ row.max_amount ? `封顶 ¥${row.max_amount}` : '不封顶' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="生效期" min-width="220">
        <template #default="{ row }">{{ fmtTime(row.effective_from) }} ~ {{ fmtTime(row.effective_to) }}</template>
      </el-table-column>
      <el-table-column prop="priority" label="优先级" width="90" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag size="small" :type="row.is_active ? 'success' : 'info'">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="warning" @click="toggle(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
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

    <el-dialog v-model="dialog" :title="dialogTitle" width="620px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item label="规则名称" prop="name">
          <el-input v-model="form.name" maxlength="128" placeholder="如 会籍销售 10% 提成" />
        </el-form-item>
        <el-form-item label="计提场景">
          <el-select v-model="form.scope" style="width: 100%">
            <el-option v-for="(label, code) in COMMISSION_SCOPE_LABELS" :key="code" :label="label" :value="code" />
          </el-select>
        </el-form-item>
        <el-form-item label="受益方">
          <el-select v-model="form.beneficiary" style="width: 100%">
            <el-option
              v-for="code in allowedBeneficiaries"
              :key="code"
              :label="commissionBeneficiaryLabel(code)"
              :value="code"
            />
          </el-select>
          <span class="hint">决定提成记给谁；实际人员由订单 / 场次上下文解析</span>
        </el-form-item>
        <el-form-item label="计提方式">
          <el-radio-group v-model="form.basis">
            <el-radio v-for="b in allowedBasis" :key="b" :value="b">{{ COMMISSION_BASIS_LABELS[b] }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="isPercent" label="提成比例">
          <el-input v-model="form.rate" style="width: 160px" placeholder="0.1 表示 10%" />
          <span class="hint">以小数填写，最大 1</span>
        </el-form-item>
        <el-form-item v-else label="单位金额">
          <el-input v-model="form.unit_amount" style="width: 160px" placeholder="如 50.00" />
          <span class="hint">
            {{ form.basis === 'per_head' ? '每出席一人' : form.basis === 'per_session' ? '每节课' : '每笔订单' }}
          </span>
        </el-form-item>
        <el-form-item label="起算门槛">
          <el-input v-model="form.min_base_amount" style="width: 160px" placeholder="留空不限" />
          <span class="hint">订单金额低于门槛不计提</span>
        </el-form-item>
        <el-form-item label="单笔封顶">
          <el-input v-model="form.max_amount" style="width: 160px" placeholder="留空不封顶" />
        </el-form-item>
        <el-form-item v-if="form.scope === 'referral'" label="仅首单">
          <el-switch v-model="form.first_order_only" />
          <span class="hint">开启后同一被推荐人仅首单计提</span>
        </el-form-item>
        <el-form-item label="优先级">
          <el-input-number v-model="form.priority" :min="1" :max="9999" />
          <span class="hint">数值越小越先命中</span>
        </el-form-item>
        <el-form-item label="生效时间">
          <el-date-picker
            v-model="form.effective_from"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="留空立即生效"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="失效时间">
          <el-date-picker
            v-model="form.effective_to"
            type="datetime"
            value-format="YYYY-MM-DDTHH:mm:ss"
            placeholder="留空长期有效"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submit">保存</el-button>
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
  max-width: 720px;
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

.hint {
  margin-left: 10px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
