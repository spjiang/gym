<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { couponApplicableLabel, couponStatusLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Template = {
  id: number
  name: string
  discount_type: string
  threshold_amount: string
  fixed_amount: string | null
  percent_off: number | null
  applicable_to: string
  starts_at: string
  ends_at: string
  total_limit: number | null
  issued_count: number
  claimable: boolean
  per_member_limit: number
  is_active: boolean
}
type MemberCoupon = {
  id: number
  member_id: number
  template_id: number
  status: string
  starts_at: string
  ends_at: string
  used_order_id: number | null
}

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const templates = ref<Template[]>([])
const memberCoupons = ref<MemberCoupon[]>([])
const merchantId = ref<number | undefined>()
const filterMemberId = ref<number | undefined>()
const loading = ref(false)

const templateDialog = ref(false)
const issueDialog = ref(false)
const submitting = ref(false)
const templateFormRef = ref<FormInstance>()
const issueFormRef = ref<FormInstance>()

const form = reactive({
  name: '满100减20',
  discount_type: 'fixed',
  threshold_amount: '100',
  fixed_amount: '20',
  percent_off: 10,
  applicable_to: 'both',
  days: 30,
  total_limit: undefined as number | undefined,
  claimable: false,
  per_member_limit: 1,
})
const issueForm = reactive({
  template_id: undefined as number | undefined,
  member_id: undefined as number | undefined,
})

const templateRules: FormRules = {
  name: [{ required: true, message: '请填写模板名称', trigger: 'blur' }],
  threshold_amount: [{ required: true, message: '请填写使用门槛', trigger: 'blur' }],
}

const issueRules: FormRules = {
  template_id: [{ required: true, message: '请选择券模板', trigger: 'change' }],
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
}

function templateLabel(id: number) {
  return templates.value.find((t) => t.id === id)?.name ?? `#${id}`
}

function memberName(id: number, row?: { member?: { name: string; phone: string } | null }) {
  if (row?.member) return `${row.member.name} ${row.member.phone}`
  const m = members.value.find((x) => x.id === id)
  return m ? `${m.name} ${m.phone}` : `#${id}`
}

function discountLabel(t: Template) {
  return t.discount_type === 'fixed' ? `减 ¥${t.fixed_amount}` : `${t.percent_off}% 折扣`
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
    if (!merchantId.value && merchants.value[0]) merchantId.value = merchants.value[0].id
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = merchants.value[0]?.id
    }
    if (!merchantId.value) return
    const [t, c] = await Promise.all([
      http.get('/coupons/templates', { params: { merchant_id: merchantId.value } }),
      http.get('/coupons/member-coupons', {
        params: {
          merchant_id: merchantId.value,
          member_id: filterMemberId.value || undefined,
          page: 1,
          page_size: 100,
        },
      }),
    ])
    templates.value = t.data
    memberCoupons.value = c.data.items
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openTemplateDialog() {
  form.name = ''
  form.discount_type = 'fixed'
  form.threshold_amount = '100'
  form.fixed_amount = '20'
  form.percent_off = 10
  form.applicable_to = 'both'
  form.days = 30
  form.total_limit = undefined
  form.claimable = false
  form.per_member_limit = 1
  templateFormRef.value?.clearValidate()
  templateDialog.value = true
}

async function createTemplate() {
  const ok = await templateFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    const starts = new Date()
    const ends = new Date()
    ends.setDate(ends.getDate() + form.days)
    await http.post('/coupons/templates', {
      merchant_id: merchantId.value,
      name: form.name.trim(),
      discount_type: form.discount_type,
      threshold_amount: form.threshold_amount,
      fixed_amount: form.discount_type === 'fixed' ? form.fixed_amount : null,
      percent_off: form.discount_type === 'percent' ? form.percent_off : null,
      applicable_to: form.applicable_to,
      starts_at: starts.toISOString(),
      ends_at: ends.toISOString(),
      total_limit: form.total_limit ?? null,
      claimable: form.claimable,
      per_member_limit: form.per_member_limit,
    })
    ElMessage.success('模板已创建')
    templateDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openIssueDialog() {
  issueForm.template_id = templates.value.find((x) => x.is_active)?.id
  issueForm.member_id = undefined
  issueFormRef.value?.clearValidate()
  issueDialog.value = true
}

async function issueCoupon() {
  const ok = await issueFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/coupons/issue', {
      merchant_id: merchantId.value,
      template_id: issueForm.template_id,
      member_id: issueForm.member_id,
    })
    ElMessage.success('已发券')
    issueDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '发券失败')
  } finally {
    submitting.value = false
  }
}

async function deactivate(id: number) {
  await http.post(`/coupons/templates/${id}/deactivate`)
  ElMessage.success('已停用')
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>优惠券</h3>
      <div class="toolbar-actions">
        <el-button type="primary" plain @click="openTemplateDialog">新建券模板</el-button>
        <el-button type="primary" @click="openIssueDialog">发券给会员</el-button>
      </div>
    </div>

    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <h3 class="section-title">券模板</h3>
    <el-table :data="templates" v-loading="loading" stripe style="margin-bottom: 28px">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="类型" width="90">
        <template #default="{ row }">
          {{ row.discount_type === 'fixed' ? '满减' : '折扣' }}
        </template>
      </el-table-column>
      <el-table-column label="面额" width="120">
        <template #default="{ row }">{{ discountLabel(row) }}</template>
      </el-table-column>
      <el-table-column prop="threshold_amount" label="门槛" width="100" />
      <el-table-column label="适用" width="120">
        <template #default="{ row }">{{ couponApplicableLabel(row.applicable_to) }}</template>
      </el-table-column>
      <el-table-column label="已发/库存" width="110">
        <template #default="{ row }">
          {{ row.issued_count }} / {{ row.total_limit ?? '∞' }}
        </template>
      </el-table-column>
      <el-table-column label="可领/限" width="100">
        <template #default="{ row }">
          {{ row.claimable ? `是/${row.per_member_limit}` : '否' }}
        </template>
      </el-table-column>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button v-if="row.is_active" link type="danger" @click="deactivate(row.id)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <h3 class="section-title">会员持券</h3>
    <el-form inline style="margin-bottom: 12px">
      <el-form-item label="会员ID">
        <el-input-number v-model="filterMemberId" :min="1" placeholder="会员ID" />
      </el-form-item>
      <el-button @click="refresh">筛选</el-button>
      <el-button v-if="filterMemberId" @click="filterMemberId = undefined; refresh()">清除</el-button>
    </el-form>
    <el-table :data="memberCoupons" v-loading="loading" stripe>
      <el-table-column prop="id" label="券ID" width="80" />
      <el-table-column label="会员" width="200">
        <template #default="{ row }">{{ memberName(row.member_id, row) }}</template>
      </el-table-column>
      <el-table-column label="模板" width="160">
        <template #default="{ row }">{{ templateLabel(row.template_id) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="row.status === 'used' ? 'info' : row.status === 'expired' ? 'danger' : 'success'"
          >
            {{ couponStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="有效至" width="120">
        <template #default="{ row }">{{ row.ends_at?.slice(0, 10) }}</template>
      </el-table-column>
      <el-table-column prop="used_order_id" label="核销订单" width="100">
        <template #default="{ row }">{{ row.used_order_id ?? '—' }}</template>
      </el-table-column>
    </el-table>

    <!-- 新建券模板弹窗 -->
    <el-dialog v-model="templateDialog" title="新建券模板" width="560px" destroy-on-close>
      <el-form ref="templateFormRef" :model="form" :rules="templateRules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：满100减20" maxlength="64" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.discount_type">
            <el-radio-button value="fixed">满减</el-radio-button>
            <el-radio-button value="percent">折扣</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="form.discount_type === 'fixed'" label="减免金额">
          <el-input v-model="form.fixed_amount" />
        </el-form-item>
        <el-form-item v-else label="折扣率%">
          <el-input-number v-model="form.percent_off" :min="1" :max="99" style="width: 100%" />
        </el-form-item>
        <el-form-item label="使用门槛" prop="threshold_amount">
          <el-input v-model="form.threshold_amount" placeholder="订单满多少可用" />
        </el-form-item>
        <el-form-item label="适用场景">
          <el-select v-model="form.applicable_to" style="width: 100%">
            <el-option label="办卡+零售" value="both" />
            <el-option label="仅零售" value="retail" />
            <el-option label="仅办卡" value="membership" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效天数">
          <el-input-number v-model="form.days" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="总库存">
          <el-input-number v-model="form.total_limit" :min="1" style="width: 100%" />
          <div class="form-hint">不填表示不限制发放总数</div>
        </el-form-item>
        <el-form-item label="可自助领取">
          <el-switch v-model="form.claimable" />
        </el-form-item>
        <el-form-item label="每人限领">
          <el-input-number v-model="form.per_member_limit" :min="1" :max="100" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="templateDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createTemplate">创建</el-button>
      </template>
    </el-dialog>

    <!-- 发券弹窗 -->
    <el-dialog v-model="issueDialog" title="发券给会员" width="480px" destroy-on-close>
      <el-form ref="issueFormRef" :model="issueForm" :rules="issueRules" label-width="90px">
        <el-form-item label="券模板" prop="template_id">
          <el-select v-model="issueForm.template_id" filterable style="width: 100%">
            <el-option
              v-for="t in templates.filter((x) => x.is_active)"
              :key="t.id"
              :label="`#${t.id} ${t.name}`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="会员" prop="member_id">
          <el-select v-model="issueForm.member_id" filterable style="width: 100%">
            <el-option v-for="m in members" :key="m.id" :label="`${m.name} ${m.phone}`" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="issueDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="issueCoupon">发券</el-button>
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
  margin: 0;
  font-size: 1.1rem;
}

.toolbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.section-title {
  margin: 0 0 12px;
  font-size: 0.95rem;
}

.form-hint {
  width: 100%;
  margin-top: 6px;
  font-size: 0.78rem;
  color: var(--admin-ink-muted);
}
</style>
