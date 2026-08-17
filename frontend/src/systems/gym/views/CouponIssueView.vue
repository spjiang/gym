<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { couponStatusLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useAuthStore } from '../../../core/stores/auth'
import { CATERING_APPLICABLE, GYM_APPLICABLE, dateOnly, type CouponTemplate, type MemberCoupon } from '../couponUi'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const auth = useAuthStore()
const canManage = computed(
  () => (auth.me?.permissions || []).includes('coupon:manage') || (auth.me?.permissions || []).includes('*'),
)

const allMerchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const templates = ref<CouponTemplate[]>([])
const rows = ref<MemberCoupon[]>([])
const system = ref<'gym' | 'catering'>('gym')
const loading = ref(false)
const submitting = ref(false)
const issueVisible = ref(false)
const editVisible = ref(false)
const detailVisible = ref(false)
const issueFormRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()
const editing = ref<MemberCoupon | null>(null)
const detail = ref<MemberCoupon | null>(null)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const query = reactive({
  merchant_id: undefined as number | undefined,
  member_id: undefined as number | undefined,
  template_id: undefined as number | undefined,
  status: '',
  q: '',
})

const issueForm = reactive({
  mode: 'member' as 'member' | 'merchant',
  merchant_id: undefined as number | undefined,
  template_id: undefined as number | undefined,
  member_id: undefined as number | undefined,
})

const editForm = reactive({
  range: [] as string[],
})

const scopedMerchants = computed(() => merchantsWithSystem(allMerchants.value, system.value))
const scopedTemplates = computed(() =>
  templates.value.filter((t) =>
    system.value === 'catering' ? CATERING_APPLICABLE.has(t.applicable_to) : GYM_APPLICABLE.has(t.applicable_to),
  ),
)
const activeTemplates = computed(() => scopedTemplates.value.filter((t) => t.is_active))

const issueRules = computed<FormRules>(() => ({
  merchant_id: [{ required: true, message: '请选择商户', trigger: 'change' }],
  template_id: [{ required: true, message: '请选择券模板', trigger: 'change' }],
  member_id: issueForm.mode === 'member' ? [{ required: true, message: '请选择会员', trigger: 'change' }] : [],
}))

const editRules: FormRules = {
  range: [{ required: true, type: 'array', min: 2, message: '请选择有效期', trigger: 'change' }],
}

function merchantName(id: number) {
  return allMerchants.value.find((m) => m.id === id)?.name || `#${id}`
}
function templateLabel(id: number, row?: MemberCoupon) {
  return row?.template_name || templates.value.find((t) => t.id === id)?.name || `#${id}`
}
function memberName(id: number, row?: MemberCoupon) {
  if (row?.member) return `${row.member.name} ${row.member.phone}`
  const m = members.value.find((x) => x.id === id)
  return m ? `${m.name} ${m.phone}` : `#${id}`
}

function onSystemChange() {
  if (query.merchant_id && !scopedMerchants.value.some((m) => m.id === query.merchant_id)) {
    query.merchant_id = undefined
  }
  query.template_id = undefined
  page.value = 1
  void load()
}

async function loadOptions() {
  const [m, mem, t] = await Promise.all([
    http.get('/merchants'),
    http.get<Page<Member>>('/members', { params: { page: 1, page_size: 100 } }),
    http.get('/coupons/templates', { params: { merchant_id: query.merchant_id, page: 1, page_size: 100 } }),
  ])
  allMerchants.value = m.data
  members.value = mem.data.items
  templates.value = t.data.items
}

async function load() {
  loading.value = true
  try {
    await loadOptions()
    const { data } = await http.get<Page<MemberCoupon>>('/coupons/member-coupons', {
      params: {
        merchant_id: query.merchant_id,
        member_id: query.member_id || undefined,
        template_id: query.template_id || undefined,
        status: query.status || undefined,
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
  void load()
}

function resetQuery() {
  query.merchant_id = undefined
  query.member_id = undefined
  query.template_id = undefined
  query.status = ''
  query.q = ''
  page.value = 1
  void load()
}

function openIssue() {
  issueForm.mode = 'member'
  issueForm.merchant_id = query.merchant_id ?? scopedMerchants.value[0]?.id
  issueForm.template_id = activeTemplates.value[0]?.id
  issueForm.member_id = undefined
  issueFormRef.value?.clearValidate()
  issueVisible.value = true
}

async function issueCoupon() {
  const ok = await issueFormRef.value?.validate().catch(() => false)
  if (!ok || !issueForm.merchant_id) return
  submitting.value = true
  try {
    if (issueForm.mode === 'merchant') {
      const { data } = await http.post<{ issued: number; skipped: number }>('/coupons/issue-batch', {
        merchant_id: issueForm.merchant_id,
        template_id: issueForm.template_id,
      })
      ElMessage.success(`已向商户会员发券 ${data.issued} 张，跳过 ${data.skipped} 张`)
    } else {
      await http.post('/coupons/issue', {
        merchant_id: issueForm.merchant_id,
        template_id: issueForm.template_id,
        member_id: issueForm.member_id,
      })
      ElMessage.success('已发券给指定会员')
    }
    issueVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '发券失败')
  } finally {
    submitting.value = false
  }
}

function openDetail(row: MemberCoupon) {
  detail.value = row
  detailVisible.value = true
}

function openEdit(row: MemberCoupon) {
  editing.value = row
  editForm.range = [row.starts_at, row.ends_at]
  editFormRef.value?.clearValidate()
  editVisible.value = true
}

async function saveEdit() {
  if (!editing.value) return
  const ok = await editFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.patch(`/coupons/member-coupons/${editing.value.id}`, {
      starts_at: editForm.range[0],
      ends_at: editForm.range[1],
    })
    ElMessage.success('会员券已更新')
    editVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function deactivate(row: MemberCoupon) {
  try {
    await http.post(`/coupons/member-coupons/${row.id}/deactivate`)
    ElMessage.success('已停用该会员券')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '停用失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>发放优惠券</h3>
      <el-button v-if="canManage" type="primary" @click="openIssue">发放优惠券</el-button>
    </div>

    <el-form inline class="filters" @submit.prevent="search">
      <el-form-item label="业务系统">
        <el-radio-group v-model="system" @change="onSystemChange">
          <el-radio-button value="gym">观野FIT</el-radio-button>
          <el-radio-button value="catering">观野BAR</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="商户">
        <el-select v-model="query.merchant_id" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in scopedMerchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="模板">
        <el-select v-model="query.template_id" clearable filterable placeholder="全部模板" style="width: 180px">
          <el-option v-for="t in scopedTemplates" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="会员">
        <el-select v-model="query.member_id" clearable filterable placeholder="全部会员" style="width: 200px">
          <el-option v-for="m in members" :key="m.id" :label="`${m.name} ${m.phone}`" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="未使用" value="unused" />
          <el-option label="已使用" value="used" />
          <el-option label="已过期" value="expired" />
          <el-option label="已停用" value="void" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="会员姓名 / 手机号" style="width: 180px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="券ID" width="80" />
      <el-table-column label="会员" min-width="180">
        <template #default="{ row }">{{ memberName(row.member_id, row) }}</template>
      </el-table-column>
      <el-table-column label="商户" width="140">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
      <el-table-column label="模板" min-width="140">
        <template #default="{ row }">{{ templateLabel(row.template_id, row) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="
              row.status === 'used'
                ? 'info'
                : row.status === 'expired' || row.status === 'void'
                  ? 'danger'
                  : 'success'
            "
          >
            {{ couponStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="有效至" width="120">
        <template #default="{ row }">{{ dateOnly(row.ends_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button
            v-if="canManage && row.status === 'unused'"
            link
            type="primary"
            @click="openEdit(row)"
          >
            编辑
          </el-button>
          <el-button
            v-if="canManage && row.status === 'unused'"
            link
            type="danger"
            @click="deactivate(row)"
          >
            停用
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
        @current-change="load"
        @size-change="
          () => {
            page = 1
            load()
          }
        "
      />
    </div>

    <el-drawer v-model="detailVisible" :title="detail ? `会员券 #${detail.id}` : '会员券详情'" size="420px">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="券ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="会员">{{ memberName(detail.member_id, detail) }}</el-descriptions-item>
        <el-descriptions-item label="商户">{{ merchantName(detail.merchant_id) }}</el-descriptions-item>
        <el-descriptions-item label="模板">{{ templateLabel(detail.template_id, detail) }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ couponStatusLabel(detail.status) }}</el-descriptions-item>
        <el-descriptions-item label="有效期">
          {{ dateOnly(detail.starts_at) }} ~ {{ dateOnly(detail.ends_at) }}
        </el-descriptions-item>
        <el-descriptions-item label="核销订单">{{ detail.used_order_id || '—' }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="detail && canManage && detail.status === 'unused'" class="drawer-actions">
        <el-button type="primary" @click="openEdit(detail)">编辑</el-button>
        <el-button type="danger" plain @click="deactivate(detail)">停用</el-button>
      </div>
    </el-drawer>

    <el-dialog v-model="issueVisible" title="发放优惠券" width="480px" destroy-on-close>
      <el-form ref="issueFormRef" :model="issueForm" :rules="issueRules" label-width="90px">
        <el-form-item label="发放方式">
          <el-radio-group v-model="issueForm.mode">
            <el-radio-button value="member">指定会员</el-radio-button>
            <el-radio-button value="merchant">商户全部会员</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="商户" prop="merchant_id">
          <el-select v-model="issueForm.merchant_id" style="width: 100%">
            <el-option v-for="m in scopedMerchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="券模板" prop="template_id">
          <el-select v-model="issueForm.template_id" filterable style="width: 100%">
            <el-option
              v-for="t in activeTemplates"
              :key="t.id"
              :label="`#${t.id} ${t.name}`"
              :value="t.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item v-if="issueForm.mode === 'member'" label="会员" prop="member_id">
          <el-select v-model="issueForm.member_id" filterable style="width: 100%">
            <el-option v-for="m in members" :key="m.id" :label="`${m.name} ${m.phone}`" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="issueVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="issueCoupon">发放</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑会员券" width="480px" destroy-on-close>
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="90px">
        <el-form-item label="有效期" prop="range">
          <el-date-picker
            v-model="editForm.range"
            type="datetimerange"
            value-format="YYYY-MM-DDTHH:mm:ss.SSSZ"
            start-placeholder="开始"
            end-placeholder="结束"
            style="width: 100%"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button>
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
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0;
}
.filters {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.drawer-actions {
  margin-top: 16px;
}
</style>
