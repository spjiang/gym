<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { PT_PACKAGE_STATUS_LABELS } from '../../../core/labels'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Product = {
  id: number
  name: string
  price: string
  session_count: number
  valid_days: number
  is_active: boolean
}
type Pkg = {
  id: number
  merchant_id: number
  member_id: number
  product_id: number
  status: string
  remaining_sessions: number
  starts_at: string | null
  ends_at: string | null
  member?: { id: number; name: string; phone: string } | null
  product?: Product | null
}
type ConsumeLog = {
  id: number
  created_at: string
  sessions: number
  remaining_after: number | null
  actor_name: string | null
  summary: string
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const products = ref<Product[]>([])
const packages = ref<Pkg[]>([])
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({
  q: '',
  status: '' as string,
  product_id: undefined as number | undefined,
})

const sellDialog = ref(false)
const editDialog = ref(false)
const detailVisible = ref(false)
const consumeDialog = ref(false)
const submitting = ref(false)
const sellFormRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()
const sell = reactive({
  member_id: undefined as number | undefined,
  product_id: undefined as number | undefined,
})
const detail = ref<Pkg | null>(null)
const consumeTarget = ref<Pkg | null>(null)
const consumeRange = ref<[string, string] | null>(null)
const consumes = ref<ConsumeLog[]>([])
const consumesLoading = ref(false)
const editing = ref<Pkg | null>(null)
const editForm = reactive({
  remaining_sessions: 0,
  starts_at: '',
  ends_at: '',
  status: 'active',
})

const sellRules: FormRules = {
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
  product_id: [{ required: true, message: '请选择课包', trigger: 'change' }],
}

const editRules: FormRules = {
  remaining_sessions: [{ required: true, message: '请填写剩余课时', trigger: 'blur' }],
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

function memberName(id: number, row?: Pkg | null) {
  if (row?.member) return `${row.member.name} ${row.member.phone}`
  const m = members.value.find((x) => x.id === id)
  return m ? `${m.name} ${m.phone}` : `#${id}`
}

function productName(row: Pkg) {
  return row.product?.name || products.value.find((p) => p.id === row.product_id)?.name || `#${row.product_id}`
}

function statusLabel(s: string) {
  return PT_PACKAGE_STATUS_LABELS[s] || s
}

function datePart(iso: string | null | undefined) {
  return iso ? iso.slice(0, 10) : ''
}

function fmtDateTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function productSpec(row: Pkg) {
  const p = row.product || products.value.find((x) => x.id === row.product_id)
  if (!p) return ''
  return `${p.session_count} 课时 · ${p.valid_days} 天 · ¥${p.price}`
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
    const [p, pkgs] = await Promise.all([
      http.get('/pt-products', { params: { merchant_id: merchantId.value, page: 1, page_size: 100 } }),
      http.get<Page<Pkg>>('/pt-packages', {
        params: {
          merchant_id: merchantId.value,
          q: query.q.trim() || undefined,
          status: query.status || undefined,
          product_id: query.product_id,
          page: page.value,
          page_size: pageSize.value,
        },
      }),
    ])
    products.value = p.data.items
    packages.value = pkgs.data.items
    total.value = pkgs.data.total
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
  query.status = ''
  query.product_id = undefined
  page.value = 1
  void refresh()
}

async function loadConsumes(packageId: number) {
  consumesLoading.value = true
  try {
    const { data } = await http.get<ConsumeLog[]>(`/pt-packages/${packageId}/consumes`, {
      params: {
        from_date: consumeRange.value?.[0],
        to_date: consumeRange.value?.[1],
      },
    })
    consumes.value = data
  } catch (e: unknown) {
    consumes.value = []
    ElMessage.error(e instanceof Error ? e.message : '加载核销记录失败')
  } finally {
    consumesLoading.value = false
  }
}

async function openDetail(row: Pkg) {
  detail.value = row
  detailVisible.value = true
  try {
    const { data } = await http.get<Pkg>(`/pt-packages/${row.id}`)
    detail.value = data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载详情失败')
  }
}

async function openConsumes(row: Pkg) {
  consumeTarget.value = row
  consumeRange.value = null
  consumeDialog.value = true
  consumes.value = []
  await loadConsumes(row.id)
}

function searchConsumes() {
  if (!consumeTarget.value) return
  void loadConsumes(consumeTarget.value.id)
}

function resetConsumeSearch() {
  consumeRange.value = null
  searchConsumes()
}

function openSellDialog() {
  sell.member_id = undefined
  sell.product_id = products.value.find((x) => x.is_active)?.id
  sellFormRef.value?.clearValidate()
  sellDialog.value = true
}

function openEdit(row: Pkg) {
  if (row.status === 'void') {
    ElMessage.warning('已作废课包不可编辑')
    return
  }
  editing.value = row
  editForm.remaining_sessions = row.remaining_sessions
  editForm.starts_at = datePart(row.starts_at)
  editForm.ends_at = datePart(row.ends_at)
  editForm.status = row.status
  editFormRef.value?.clearValidate()
  editDialog.value = true
}

async function sellPackage() {
  const ok = await sellFormRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    const { data: order } = await http.post('/pt-packages/purchase', {
      merchant_id: mid,
      member_id: sell.member_id,
      product_id: sell.product_id,
    })
    await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
    ElMessage.success('售课并收款成功')
    sellDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '售卖失败')
  } finally {
    submitting.value = false
  }
}

async function saveEdit() {
  const ok = await editFormRef.value?.validate().catch(() => false)
  if (!ok || !editing.value) return
  submitting.value = true
  try {
    const { data } = await http.patch<Pkg>(`/pt-packages/${editing.value.id}`, {
      remaining_sessions: editForm.remaining_sessions,
      starts_at: editForm.starts_at ? `${editForm.starts_at}T00:00:00` : null,
      ends_at: editForm.ends_at ? `${editForm.ends_at}T23:59:59` : null,
      status: editForm.status,
    })
    ElMessage.success('课包已更新')
    editDialog.value = false
    if (detail.value?.id === data.id) detail.value = data
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function consume(row: Pkg) {
  const next = Math.max(row.remaining_sessions - 1, 0)
  try {
    await ElMessageBox.confirm(
      `确认为「${memberName(row.member_id, row)}」核销「${productName(row)}」1 课时？核销后剩余 ${next} 课时。`,
      '核销确认',
      {
        type: 'warning',
        confirmButtonText: '确认核销',
        cancelButtonText: '取消',
        appendTo: document.body,
      },
    )
  } catch {
    return
  }
  try {
    const { data } = await http.post<Pkg>(`/pt-packages/${row.id}/consume`)
    ElMessage.success('已核销 1 课时')
    if (detail.value?.id === data.id) detail.value = data
    if (consumeTarget.value?.id === data.id) {
      consumeTarget.value = data
      await loadConsumes(data.id)
    }
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '核销失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>会员课包</h3>
        <p class="lead">售卖课包并核销课时。课包商品请到「私教课管理 → 私教课包」。</p>
      </div>
      <el-button type="primary" @click="openSellDialog">售卖课包</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input
          v-model="query.q"
          clearable
          placeholder="会员姓名 / 手机 / 课包名"
          style="width: 220px"
          @keyup.enter="search"
        />
      </el-form-item>
      <el-form-item label="课包">
        <el-select v-model="query.product_id" clearable placeholder="全部" style="width: 160px">
          <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="使用中" value="active" />
          <el-option label="已用尽" value="exhausted" />
          <el-option label="已过期" value="expired" />
          <el-option label="已作废" value="void" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="packages" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="会员" min-width="180">
        <template #default="{ row }">{{ memberName(row.member_id, row) }}</template>
      </el-table-column>
      <el-table-column label="课包" min-width="180">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">{{ productName(row) }}</el-button>
          <div class="card-spec">{{ productSpec(row) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="remaining_sessions" label="剩余课时" width="100" />
      <el-table-column label="生效" width="120">
        <template #default="{ row }">{{ datePart(row.starts_at) || '—' }}</template>
      </el-table-column>
      <el-table-column label="到期" width="120">
        <template #default="{ row }">{{ datePart(row.ends_at) || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button link type="primary" @click="openConsumes(row)">核销记录</el-button>
          <el-button v-if="row.status !== 'void'" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.status === 'active'" link type="danger" @click="consume(row)">核销</el-button>
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

    <el-drawer v-model="detailVisible" title="课包详情" size="520px">
      <template v-if="detail">
        <h4 class="detail-section">课包</h4>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="会员">{{ memberName(detail.member_id, detail) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(detail.status) }}</el-descriptions-item>
          <el-descriptions-item label="剩余课时">{{ detail.remaining_sessions }}</el-descriptions-item>
          <el-descriptions-item label="生效">{{ datePart(detail.starts_at) || '—' }}</el-descriptions-item>
          <el-descriptions-item label="到期">{{ datePart(detail.ends_at) || '—' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="detail-section">商品</h4>
        <el-descriptions :column="1" border>
          <template v-if="detail.product">
            <el-descriptions-item label="名称">{{ detail.product.name }}</el-descriptions-item>
            <el-descriptions-item label="课时额度">{{ detail.product.session_count }} 节</el-descriptions-item>
            <el-descriptions-item label="有效天数">{{ detail.product.valid_days }} 天</el-descriptions-item>
            <el-descriptions-item label="标价">¥{{ detail.product.price }}</el-descriptions-item>
            <el-descriptions-item label="售卖状态">
              {{ detail.product.is_active ? '在售' : '已停用' }}
            </el-descriptions-item>
          </template>
          <el-descriptions-item v-else label="课包">{{ productName(detail) }}</el-descriptions-item>
        </el-descriptions>
        <div class="detail-actions">
          <el-button v-if="detail.status === 'active'" type="danger" plain @click="consume(detail)">核销</el-button>
          <el-button type="primary" plain @click="openConsumes(detail)">核销记录</el-button>
          <el-button v-if="detail.status !== 'void'" type="primary" @click="openEdit(detail)">编辑</el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="editDialog" title="编辑课包" width="480px" destroy-on-close>
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="90px">
        <el-form-item label="会员">
          <el-input :model-value="editing ? memberName(editing.member_id, editing) : ''" disabled />
        </el-form-item>
        <el-form-item label="课包">
          <el-input :model-value="editing ? productName(editing) : ''" disabled />
        </el-form-item>
        <el-form-item label="剩余课时" prop="remaining_sessions">
          <el-input-number v-model="editForm.remaining_sessions" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="生效日">
          <el-date-picker v-model="editForm.starts_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="到期日">
          <el-date-picker v-model="editForm.ends_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="使用中" value="active" />
            <el-option label="已用尽" value="exhausted" />
            <el-option label="已过期" value="expired" />
          </el-select>
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon title="校正剩余课时或有效期后立即生效，核销仍按 1 课时扣减。" />
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="sellDialog" title="售卖课包并收款" width="480px" destroy-on-close>
      <el-form ref="sellFormRef" :model="sell" :rules="sellRules" label-width="90px">
        <el-form-item label="会员" prop="member_id">
          <el-select v-model="sell.member_id" filterable style="width: 100%">
            <el-option v-for="x in members" :key="x.id" :label="`${x.name} ${x.phone}`" :value="x.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="课包" prop="product_id">
          <el-select v-model="sell.product_id" style="width: 100%">
            <el-option
              v-for="p in products.filter((x) => x.is_active)"
              :key="p.id"
              :label="`${p.name} ¥${p.price}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="提交后将自动生成订单并登记线下收款（现金）"
        />
      </el-form>
      <template #footer>
        <el-button @click="sellDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="sellPackage">售卖并收款</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="consumeDialog"
      :title="consumeTarget ? `核销记录 · ${productName(consumeTarget)}` : '核销记录'"
      width="720px"
      append-to-body
      destroy-on-close
    >
      <p v-if="consumeTarget" class="card-hint">
        {{ memberName(consumeTarget.member_id, consumeTarget) }} · 剩余 {{ consumeTarget.remaining_sessions }} 课时
      </p>
      <el-form inline class="filters">
        <el-form-item label="核销时间">
          <el-date-picker
            v-model="consumeRange"
            type="daterange"
            value-format="YYYY-MM-DD"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            unlink-panels
            style="width: 260px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="searchConsumes">查询</el-button>
          <el-button @click="resetConsumeSearch">重置</el-button>
        </el-form-item>
      </el-form>
      <el-table :data="consumes" v-loading="consumesLoading" stripe empty-text="暂无核销记录">
        <el-table-column label="核销时间" min-width="170">
          <template #default="{ row }">{{ fmtDateTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="核销课时" width="100">
          <template #default="{ row }">{{ row.sessions }} 节</template>
        </el-table-column>
        <el-table-column label="核销后剩余" width="110">
          <template #default="{ row }">{{ row.remaining_after ?? '—' }}</template>
        </el-table-column>
        <el-table-column label="操作人" min-width="120">
          <template #default="{ row }">{{ row.actor_name || '—' }}</template>
        </el-table-column>
        <el-table-column label="说明" min-width="180" show-overflow-tooltip>
          <template #default="{ row }">{{ row.summary }}</template>
        </el-table-column>
      </el-table>
      <template #footer>
        <el-button
          v-if="consumeTarget?.status === 'active'"
          type="danger"
          @click="consumeTarget && consume(consumeTarget)"
        >
          核销
        </el-button>
        <el-button @click="consumeDialog = false">关闭</el-button>
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

.card-spec {
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.detail-section {
  margin: 0 0 10px;
  font-size: 0.9rem;
}

.detail-section + .el-descriptions + .detail-section {
  margin-top: 20px;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

.card-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
</style>
