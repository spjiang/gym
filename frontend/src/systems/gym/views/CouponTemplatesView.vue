<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { couponApplicableLabel } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useAuthStore } from '../../../core/stores/auth'
import { dateOnly, discountLabel, type CouponTemplate } from '../couponUi'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }

const auth = useAuthStore()
const canManage = computed(
  () => (auth.me?.permissions || []).includes('coupon:manage') || (auth.me?.permissions || []).includes('*'),
)

const allMerchants = ref<Merchant[]>([])
const templates = ref<CouponTemplate[]>([])
const system = ref<'gym' | 'catering'>('gym')
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const submitting = ref(false)
const dialogVisible = ref(false)
const detailVisible = ref(false)
const editingId = ref<number | null>(null)
const detail = ref<CouponTemplate | null>(null)
const formRef = ref<FormInstance>()

const query = reactive({
  merchant_id: undefined as number | undefined,
  q: '',
  discount_type: '' as '' | 'fixed' | 'percent',
  applicable_to: '',
  is_active: '' as '' | 'true' | 'false',
})

const form = reactive({
  merchant_id: undefined as number | undefined,
  name: '',
  discount_type: 'fixed',
  threshold_amount: '100',
  fixed_amount: '20',
  percent_off: 10,
  applicable_to: 'both',
  range: [] as string[],
  total_limit: undefined as number | undefined,
  claimable: false,
  per_member_limit: 1,
  is_active: true,
})

const scopedMerchants = computed(() => merchantsWithSystem(allMerchants.value, system.value))

const rules: FormRules = {
  merchant_id: [{ required: true, message: '请选择发放商户', trigger: 'change' }],
  name: [{ required: true, message: '请填写模板名称', trigger: 'blur' }],
  threshold_amount: [{ required: true, message: '请填写使用门槛', trigger: 'blur' }],
  range: [{ required: true, type: 'array', min: 2, message: '请选择有效期', trigger: 'change' }],
}

function merchantName(id: number) {
  return allMerchants.value.find((m) => m.id === id)?.name || `#${id}`
}

function defaultRange() {
  const starts = new Date()
  const ends = new Date()
  ends.setDate(ends.getDate() + 30)
  return [starts.toISOString(), ends.toISOString()]
}

function onSystemChange() {
  if (query.merchant_id && !scopedMerchants.value.some((m) => m.id === query.merchant_id)) {
    query.merchant_id = undefined
  }
  query.applicable_to = ''
  page.value = 1
  void load()
}

async function load() {
  loading.value = true
  try {
    const [m, t] = await Promise.all([
      http.get('/merchants'),
      http.get('/coupons/templates', {
        params: {
          merchant_id: query.merchant_id,
          q: query.q.trim() || undefined,
          discount_type: query.discount_type || undefined,
          applicable_to: query.applicable_to || undefined,
          is_active: query.is_active === '' ? undefined : query.is_active === 'true',
          system: system.value,
          page: page.value,
          page_size: pageSize.value,
        },
      }),
    ])
    allMerchants.value = m.data
    templates.value = t.data.items
    total.value = t.data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function resetQuery() {
  query.merchant_id = undefined
  query.q = ''
  query.discount_type = ''
  query.applicable_to = ''
  query.is_active = ''
  page.value = 1
  void load()
}

function fillForm(row?: CouponTemplate) {
  form.merchant_id = row?.merchant_id ?? query.merchant_id ?? scopedMerchants.value[0]?.id
  form.name = row?.name || ''
  form.discount_type = row?.discount_type || 'fixed'
  form.threshold_amount = row?.threshold_amount || '100'
  form.fixed_amount = row?.fixed_amount || '20'
  form.percent_off = row?.percent_off || 10
  form.applicable_to = row?.applicable_to || (system.value === 'catering' ? 'dining' : 'both')
  form.range = row ? [row.starts_at, row.ends_at] : defaultRange()
  form.total_limit = row?.total_limit ?? undefined
  form.claimable = row?.claimable ?? false
  form.per_member_limit = row?.per_member_limit || 1
  form.is_active = row?.is_active ?? true
}

function openCreate() {
  editingId.value = null
  fillForm()
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

function openEdit(row: CouponTemplate) {
  editingId.value = row.id
  fillForm(row)
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

function openDetail(row: CouponTemplate) {
  detail.value = row
  detailVisible.value = true
}

function payload() {
  return {
    merchant_id: form.merchant_id,
    name: form.name.trim(),
    discount_type: form.discount_type,
    threshold_amount: form.threshold_amount,
    fixed_amount: form.discount_type === 'fixed' ? form.fixed_amount : null,
    percent_off: form.discount_type === 'percent' ? form.percent_off : null,
    applicable_to: form.applicable_to,
    starts_at: form.range[0],
    ends_at: form.range[1],
    total_limit: form.total_limit ?? null,
    claimable: form.claimable,
    per_member_limit: form.per_member_limit,
    is_active: form.is_active,
  }
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok || !form.merchant_id) return
  submitting.value = true
  try {
    if (editingId.value) {
      const { merchant_id: _mid, ...patch } = payload()
      void _mid
      await http.patch(`/coupons/templates/${editingId.value}`, patch)
      ElMessage.success('模板已更新')
    } else {
      await http.post('/coupons/templates', payload())
      ElMessage.success('模板已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function setActive(row: CouponTemplate, active: boolean) {
  try {
    if (active) await http.patch(`/coupons/templates/${row.id}`, { is_active: true })
    else await http.post(`/coupons/templates/${row.id}/deactivate`)
    ElMessage.success(active ? '已启用' : '已停用')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>券模板管理</h3>
      <el-button v-if="canManage" type="primary" @click="openCreate">新建券模板</el-button>
    </div>

    <el-form inline class="filters" @submit.prevent="load">
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
      <el-form-item label="名称">
        <el-input v-model="query.q" clearable placeholder="模板名称" style="width: 160px" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="query.discount_type" clearable placeholder="全部" style="width: 120px">
          <el-option label="满减" value="fixed" />
          <el-option label="折扣" value="percent" />
        </el-select>
      </el-form-item>
      <el-form-item label="适用">
        <el-select v-model="query.applicable_to" clearable placeholder="全部" style="width: 180px">
          <template v-if="system === 'gym'">
            <el-option label="观野FIT·办卡+零售" value="both" />
            <el-option label="观野FIT·仅零售" value="retail" />
            <el-option label="观野FIT·仅办卡" value="membership" />
          </template>
          <el-option v-else label="观野BAR消费" value="dining" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.is_active" clearable placeholder="全部" style="width: 110px">
          <el-option label="启用" value="true" />
          <el-option label="停用" value="false" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="() => { page = 1; load() }">查询</el-button>
        <el-button @click="resetQuery">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="templates" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column label="商户" width="140">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
      <el-table-column label="类型" width="80">
        <template #default="{ row }">{{ row.discount_type === 'fixed' ? '满减' : '折扣' }}</template>
      </el-table-column>
      <el-table-column label="面额" width="110">
        <template #default="{ row }">{{ discountLabel(row) }}</template>
      </el-table-column>
      <el-table-column prop="threshold_amount" label="门槛" width="90" />
      <el-table-column label="适用" width="150">
        <template #default="{ row }">{{ couponApplicableLabel(row.applicable_to) }}</template>
      </el-table-column>
      <el-table-column label="已发/库存" width="100">
        <template #default="{ row }">{{ row.issued_count }} / {{ row.total_limit ?? '∞' }}</template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="canManage" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="canManage && row.is_active" link type="danger" @click="setActive(row, false)">
            停用
          </el-button>
          <el-button v-if="canManage && !row.is_active" link type="success" @click="setActive(row, true)">
            启用
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

    <el-drawer v-model="detailVisible" :title="detail ? `券模板 · ${detail.name}` : '券模板详情'" size="420px">
      <el-descriptions v-if="detail" :column="1" border>
        <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
        <el-descriptions-item label="名称">{{ detail.name }}</el-descriptions-item>
        <el-descriptions-item label="商户">{{ merchantName(detail.merchant_id) }}</el-descriptions-item>
        <el-descriptions-item label="类型">{{ detail.discount_type === 'fixed' ? '满减' : '折扣' }}</el-descriptions-item>
        <el-descriptions-item label="面额">{{ discountLabel(detail) }}</el-descriptions-item>
        <el-descriptions-item label="门槛">{{ detail.threshold_amount }}</el-descriptions-item>
        <el-descriptions-item label="适用">{{ couponApplicableLabel(detail.applicable_to) }}</el-descriptions-item>
        <el-descriptions-item label="有效期">{{ dateOnly(detail.starts_at) }} ~ {{ dateOnly(detail.ends_at) }}</el-descriptions-item>
        <el-descriptions-item label="已发 / 库存">{{ detail.issued_count }} / {{ detail.total_limit ?? '不限' }}</el-descriptions-item>
        <el-descriptions-item label="可自助领取">{{ detail.claimable ? '是' : '否' }}</el-descriptions-item>
        <el-descriptions-item label="每人限领">{{ detail.per_member_limit }}</el-descriptions-item>
        <el-descriptions-item label="状态">{{ detail.is_active ? '启用' : '停用' }}</el-descriptions-item>
      </el-descriptions>
      <div v-if="detail && canManage" class="drawer-actions">
        <el-button type="primary" @click="openEdit(detail)">编辑</el-button>
      </div>
    </el-drawer>

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑券模板' : '新建券模板'"
      width="560px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item v-if="!editingId" label="发放商户" prop="merchant_id">
          <el-select v-model="form.merchant_id" style="width: 100%">
            <el-option v-for="m in scopedMerchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
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
            <template v-if="system === 'gym'">
              <el-option label="观野FIT·办卡+零售" value="both" />
              <el-option label="观野FIT·仅零售" value="retail" />
              <el-option label="观野FIT·仅办卡" value="membership" />
            </template>
            <el-option v-else label="观野BAR消费" value="dining" />
          </el-select>
        </el-form-item>
        <el-form-item label="有效期" prop="range">
          <el-date-picker
            v-model="form.range"
            type="datetimerange"
            value-format="YYYY-MM-DDTHH:mm:ss.SSSZ"
            start-placeholder="开始"
            end-placeholder="结束"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="总库存">
          <el-input-number v-model="form.total_limit" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="可自助领取">
          <el-switch v-model="form.claimable" />
        </el-form-item>
        <el-form-item label="每人限领">
          <el-input-number v-model="form.per_member_limit" :min="1" :max="100" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="editingId" label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">保存</el-button>
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
