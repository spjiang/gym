<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import { ArrowDown } from '@element-plus/icons-vue'
import http from '../../../core/api/http'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useAuthStore } from '../../../core/stores/auth'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'
import {
  memberCouponMeta,
  memberCouponName,
  moneyLabel,
  quoteCoupon,
  type MemberCoupon,
} from '../couponUi'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Product = {
  id: number
  name: string
  price: string
  is_active: boolean
  product_type: string
  duration_days: number | null
  session_count: number | null
  stored_value: string | null
  is_trial?: boolean
  promo_price?: string | null
  promo_starts_at?: string | null
  promo_ends_at?: string | null
  effective_price?: string | null
  access_point_ids?: number[]
}
type Membership = {
  id: number
  member_id: number
  product_id: number
  product_type: string
  status: string
  starts_at: string | null
  ends_at: string | null
  remaining_sessions: number | null
  balance: string | null
  remark: string | null
  member?: { id: number; name: string; phone: string } | null
}
type Consumption = {
  id: number
  kind: string
  sessions: number | null
  amount: string | null
  remaining_sessions_after: number | null
  balance_after: string | null
  source: string
  note: string | null
  actor_name: string | null
  created_at: string
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const products = ref<Product[]>([])
const memberships = ref<Membership[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const auth = useAuthStore()
const isSiteAdmin = computed(() => auth.isSiteAdmin())
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const query = reactive({ q: '', status: '' as string, product_type: '' as string })
const detailVisible = ref(false)
const detail = ref<Membership | null>(null)

const purchaseDialog = ref(false)
const renewDialog = ref(false)
const editDialog = ref(false)
const submitting = ref(false)
const purchaseFormRef = ref<FormInstance>()
const renewFormRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()
const editing = ref<Membership | null>(null)

const purchase = reactive({
  member_id: undefined as number | undefined,
  product_id: undefined as number | undefined,
  member_coupon_id: undefined as number | undefined,
})
const renew = reactive({
  membership_id: undefined as number | undefined,
  product_id: undefined as number | undefined,
  member_coupon_id: undefined as number | undefined,
})
const unusedCoupons = ref<MemberCoupon[]>([])
const allProducts = ref<Product[]>([])
const editForm = reactive({
  member_id: undefined as number | undefined,
  product_id: undefined as number | undefined,
  starts_at: '',
  ends_at: '',
  remaining_sessions: null as number | null,
  balance: '' as string,
  status: 'active',
  remark: '',
})

const editingProductType = computed(() => {
  const selected = allProducts.value.find((p) => p.id === editForm.product_id)
  return selected?.product_type || editing.value?.product_type
})

const editRules: FormRules = {
  status: [{ required: true, message: '请选择状态', trigger: 'change' }],
}

const purchaseRules: FormRules = {
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
  product_id: [{ required: true, message: '请选择卡种', trigger: 'change' }],
}

const renewRules: FormRules = {
  membership_id: [{ required: true, message: '请选择要续卡的会籍', trigger: 'change' }],
}

const activeMemberships = computed(() => memberships.value.filter((x) => x.status === 'active'))

const selectedPurchaseProduct = computed(() => products.value.find((p) => p.id === purchase.product_id))
const selectedPurchaseCoupon = computed(() =>
  unusedCoupons.value.find((c) => c.id === purchase.member_coupon_id),
)
const purchaseQuote = computed(() =>
  quoteCoupon(selectedPurchaseProduct.value?.price, selectedPurchaseCoupon.value, 'membership'),
)

const selectedRenewMembership = computed(() =>
  memberships.value.find((x) => x.id === renew.membership_id),
)
const selectedRenewProduct = computed(() => {
  const productId = renew.product_id || selectedRenewMembership.value?.product_id
  return (
    products.value.find((p) => p.id === productId) ||
    allProducts.value.find((p) => p.id === productId)
  )
})
const selectedRenewCoupon = computed(() => unusedCoupons.value.find((c) => c.id === renew.member_coupon_id))
const renewQuote = computed(() =>
  quoteCoupon(selectedRenewProduct.value?.price, selectedRenewCoupon.value, 'membership'),
)

const currentProduct = computed(() => {
  const id = selectedRenewMembership.value?.product_id
  return products.value.find((p) => p.id === id) || allProducts.value.find((p) => p.id === id)
})

const renewPreview = computed(() => {
  const membership = selectedRenewMembership.value
  const product = selectedRenewProduct.value
  if (!membership || !product) return ''
  if (product.product_type === 'term' && product.duration_days) {
    const ends = membership.ends_at ? new Date(membership.ends_at) : new Date()
    const base = ends.getTime() > Date.now() ? ends : new Date()
    const next = new Date(base)
    next.setDate(next.getDate() + product.duration_days)
    return `续期后到期 ${next.toISOString().slice(0, 10)}（+${product.duration_days} 天）`
  }
  if (product.product_type === 'count' && product.session_count) {
    const next = (membership.remaining_sessions || 0) + product.session_count
    return `续期后剩余 ${next} 次（+${product.session_count} 次）`
  }
  if (product.product_type === 'value' && product.stored_value) {
    const next = (Number(membership.balance || 0) + Number(product.stored_value)).toFixed(2)
    return `续期后余额 ¥${next}（+¥${product.stored_value}）`
  }
  return '续期后按所选卡种规则叠加'
})

function memberName(id: number, row?: Membership) {
  if (row?.member) return `${row.member.name}(${row.member.phone})`
  const m = members.value.find((x) => x.id === id)
  return m ? `${m.name}(${m.phone})` : `#${id}`
}

function productName(id: number) {
  return findProduct(id)?.name || `#${id}`
}

function findProduct(id?: number | null) {
  if (!id) return undefined
  return allProducts.value.find((p) => p.id === id) || products.value.find((p) => p.id === id)
}

function productSpec(id?: number | null) {
  const p = findProduct(id)
  if (!p) return ''
  const bits = [productTypeLabel(p.product_type)]
  if (p.is_trial) bits.push('体验卡')
  if (p.product_type === 'term' && p.duration_days) bits.push(`${p.duration_days} 天`)
  if (p.product_type === 'count' && p.session_count) bits.push(`${p.session_count} 次`)
  if (p.product_type === 'value' && p.stored_value) bits.push(`储值 ${moneyLabel(p.stored_value)}`)
  bits.push(`售价 ${moneyLabel(p.effective_price || p.price)}`)
  return bits.join(' · ')
}

const detailProduct = computed(() => findProduct(detail.value?.product_id))

function datePart(iso: string | null) {
  return iso ? iso.slice(0, 10) : ''
}

function statusLabel(s: string) {
  return { active: '在籍', frozen: '已停卡', expired: '已到期' }[s] || s
}

function productTypeLabel(t?: string | null) {
  return { term: '期限卡', count: '次卡', value: '储值卡' }[t || ''] || t || '—'
}

function openDetail(row: Membership) {
  detail.value = row
  detailVisible.value = true
}

async function loadUnusedCouponsForMember(memberId?: number) {
  unusedCoupons.value = []
  if (!merchantId.value || !memberId) return
  const { data } = await http.get('/coupons/member-coupons', {
    params: {
      merchant_id: merchantId.value,
      member_id: memberId,
      status: 'unused',
      page: 1,
      page_size: 100,
    },
  })
  unusedCoupons.value = data.items
}

async function loadPurchaseCoupons() {
  purchase.member_coupon_id = undefined
  await loadUnusedCouponsForMember(purchase.member_id)
}

async function loadRenewCoupons() {
  renew.member_coupon_id = undefined
  await loadUnusedCouponsForMember(selectedRenewMembership.value?.member_id)
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
    const [p, ms] = await Promise.all([
      http.get('/membership-products', { params: { merchant_id: merchantId.value, page: 1, page_size: 100 } }),
      http.get<Page<Membership>>('/memberships', {
        params: {
          merchant_id: merchantId.value,
          page: page.value,
          page_size: pageSize.value,
          q: query.q.trim() || undefined,
          status: query.status || undefined,
          product_type: query.product_type || undefined,
        },
      }),
    ])
    allProducts.value = p.data.items
    products.value = p.data.items.filter((x: Product) => x.is_active)
    memberships.value = ms.data.items
    total.value = ms.data.total
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
  query.product_type = ''
  page.value = 1
  void refresh()
}

function openPurchaseDialog() {
  purchase.member_id = undefined
  purchase.product_id = products.value[0]?.id
  purchase.member_coupon_id = undefined
  unusedCoupons.value = []
  purchaseFormRef.value?.clearValidate()
  purchaseDialog.value = true
}

async function doPurchase() {
  const ok = await purchaseFormRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  if (!purchaseQuote.value.usable) {
    ElMessage.warning(purchaseQuote.value.reason || '当前优惠券不可用')
    return
  }
  submitting.value = true
  try {
    const { data: order } = await http.post('/memberships/purchase', {
      member_id: purchase.member_id,
      product_id: purchase.product_id,
      merchant_id: mid,
      member_coupon_id: purchase.member_coupon_id ?? null,
    })
    await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
    ElMessage.success(`办卡并收款成功，实付 ¥${order.amount}`)
    purchaseDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '办卡失败')
  } finally {
    submitting.value = false
  }
}

function openRenewDialog(row?: Membership) {
  renew.membership_id = row?.id
  renew.product_id = undefined
  renew.member_coupon_id = undefined
  unusedCoupons.value = []
  renewFormRef.value?.clearValidate()
  renewDialog.value = true
  void loadRenewCoupons()
}

async function doRenew() {
  const ok = await renewFormRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  if (!renewQuote.value.usable) {
    ElMessage.warning(renewQuote.value.reason || '当前优惠券不可用')
    return
  }
  submitting.value = true
  try {
    const { data: order } = await http.post('/memberships/renew', {
      membership_id: renew.membership_id,
      product_id: renew.product_id ?? null,
      merchant_id: mid,
      member_coupon_id: renew.member_coupon_id ?? null,
    })
    await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
    ElMessage.success(`续卡并收款成功，实付 ¥${order.amount}`)
    renewDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '续卡失败')
  } finally {
    submitting.value = false
  }
}

function openEdit(row: Membership) {
  if (row.status === 'void') {
    ElMessage.warning('已作废会籍不可编辑')
    return
  }
  editing.value = row
  editForm.member_id = row.member_id
  editForm.product_id = row.product_id
  editForm.starts_at = datePart(row.starts_at)
  editForm.ends_at = datePart(row.ends_at)
  editForm.remaining_sessions = row.remaining_sessions
  editForm.balance = row.balance ?? ''
  editForm.status = row.status
  editForm.remark = row.remark || ''
  editFormRef.value?.clearValidate()
  editDialog.value = true
}

async function saveEdit() {
  const ok = await editFormRef.value?.validate().catch(() => false)
  if (!ok || !editing.value) return
  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      starts_at: editForm.starts_at ? `${editForm.starts_at}T00:00:00` : null,
      ends_at: editForm.ends_at ? `${editForm.ends_at}T23:59:59` : null,
      status: editForm.status,
      remark: editForm.remark.trim() || null,
    }
    if (isSiteAdmin.value) {
      payload.member_id = editForm.member_id
      payload.product_id = editForm.product_id
    }
    if (editingProductType.value === 'count') {
      payload.remaining_sessions = editForm.remaining_sessions
    }
    if (editingProductType.value === 'value') {
      payload.balance = editForm.balance || null
    }
    await http.patch(`/memberships/${editing.value.id}`, payload)
    ElMessage.success('会籍已更新')
    editDialog.value = false
    detailVisible.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '更新失败')
  } finally {
    submitting.value = false
  }
}

const consumeDialog = ref(false)
const consumeTarget = ref<Membership | null>(null)
const consumeForm = reactive({ sessions: 1, amount: '', note: '' })

const consumeLogVisible = ref(false)
const consumeLogTarget = ref<Membership | null>(null)
const consumeLogs = ref<Consumption[]>([])
const consumeLogLoading = ref(false)
const consumeLogTotal = ref(0)
const consumeLogPage = ref(1)
const consumeLogPageSize = ref(10)

/** 次卡按次销次，储值卡按金额扣减；期限卡不参与核销 */
function canConsume(row: Membership) {
  return row.status === 'active' && (row.product_type === 'count' || row.product_type === 'value')
}

type RowAction = 'edit' | 'log' | 'renew' | 'freeze' | 'void'

function onRowAction(command: string | number | object, row: Membership) {
  const action = String(command) as RowAction
  if (action === 'edit') openEdit(row)
  else if (action === 'log') void openConsumeLog(row)
  else if (action === 'renew') openRenewDialog(row)
  else if (action === 'freeze') void freeze(row)
  else if (action === 'void') void voidMembership(row)
}

function openConsume(row: Membership) {
  consumeTarget.value = row
  consumeForm.sessions = 1
  consumeForm.amount = ''
  consumeForm.note = ''
  consumeDialog.value = true
}

async function doConsume() {
  const row = consumeTarget.value
  if (!row) return
  const payload: Record<string, unknown> = { note: consumeForm.note.trim() || null }
  if (row.product_type === 'count') {
    if (!consumeForm.sessions || consumeForm.sessions < 1) {
      ElMessage.warning('请填写销次次数')
      return
    }
    payload.sessions = consumeForm.sessions
  } else {
    const amount = Number(consumeForm.amount)
    if (!consumeForm.amount || Number.isNaN(amount) || amount <= 0) {
      ElMessage.warning('请填写大于 0 的扣减金额')
      return
    }
    payload.amount = consumeForm.amount
  }
  submitting.value = true
  try {
    const { data } = await http.post(`/memberships/${row.id}/consume`, payload)
    const after =
      row.product_type === 'count'
        ? `剩余 ${data.consumption.remaining_sessions_after} 次`
        : `余额 ¥${data.consumption.balance_after}`
    ElMessage.success(`核销成功，${after}`)
    consumeDialog.value = false
    if (detail.value?.id === row.id) detail.value = data.membership
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '核销失败')
  } finally {
    submitting.value = false
  }
}

async function openConsumeLog(row: Membership) {
  consumeLogTarget.value = row
  consumeLogPage.value = 1
  consumeLogVisible.value = true
  await loadConsumeLogs()
}

async function loadConsumeLogs() {
  const row = consumeLogTarget.value
  if (!row) return
  consumeLogLoading.value = true
  try {
    const { data } = await http.get<Page<Consumption>>(`/memberships/${row.id}/consumptions`, {
      params: { page: consumeLogPage.value, page_size: consumeLogPageSize.value },
    })
    consumeLogs.value = data.items
    consumeLogTotal.value = data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载核销记录失败')
  } finally {
    consumeLogLoading.value = false
  }
}

function consumptionKindLabel(kind: string) {
  if (kind === 'session') return '销次'
  if (kind === 'value') return '扣值'
  return kind
}

function consumptionSourceLabel(source: string) {
  if (source === 'front_desk') return '前台核销'
  if (source === 'access') return '门禁通行'
  if (source === 'course') return '课程消课'
  return source
}

function consumptionChangeText(row: Consumption) {
  if (row.kind === 'session') return `-${row.sessions ?? 0} 次`
  return `-¥${row.amount ?? '0.00'}`
}

function consumptionAfterText(row: Consumption) {
  if (row.kind === 'session') return `剩余 ${row.remaining_sessions_after ?? '—'} 次`
  return `余额 ¥${row.balance_after ?? '0.00'}`
}

async function voidMembership(row: Membership) {
  try {
    await ElMessageBox.confirm(
      `作废会员「${memberName(row.member_id, row)}」的会籍 #${row.id}？作废后不可恢复，门禁授权同时失效。`,
      '作废确认',
      { type: 'warning', confirmButtonText: '确认作废', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await http.post(`/memberships/${row.id}/void`)
    ElMessage.success('会籍已作废')
    detailVisible.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '作废失败')
  }
}

async function freeze(row: Membership) {
  try {
    await ElMessageBox.confirm(
      `确认对会员「${memberName(row.member_id)}」的会籍 #${row.id} 执行停卡？停卡期间门禁授权将失效。`,
      '停卡确认',
      { type: 'warning', confirmButtonText: '停卡', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await http.post(`/memberships/${row.id}/freeze`)
    ElMessage.success('已停卡')
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '停卡失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>会籍档案</h3>
        <p class="lead">办卡、续卡与停卡。卡种请到「会籍管理 → 会籍卡种」。</p>
      </div>
      <el-button type="primary" @click="openPurchaseDialog">办卡并收款</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 200px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="会员手机/姓名" style="width: 180px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="在籍" value="active" />
          <el-option label="已停卡" value="frozen" />
          <el-option label="已到期" value="expired" />
          <el-option label="已作废" value="void" />
        </el-select>
      </el-form-item>
      <el-form-item label="卡种">
        <el-select v-model="query.product_type" clearable placeholder="全部" style="width: 120px">
          <el-option label="期限卡" value="term" />
          <el-option label="次卡" value="count" />
          <el-option label="储值卡" value="value" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <h3 class="section-title">会籍列表</h3>
    <el-table :data="memberships" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="会员" width="200">
        <template #default="{ row }">{{ memberName(row.member_id, row) }}</template>
      </el-table-column>
      <el-table-column label="卡种" min-width="220">
        <template #default="{ row }">
          <div>{{ productName(row.product_id) }}</div>
          <div class="card-spec">{{ productSpec(row.product_id) }}</div>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="row.status === 'active' ? 'success' : row.status === 'frozen' ? 'warning' : 'info'"
          >
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="ends_at" label="到期" width="180">
        <template #default="{ row }">{{ row.ends_at?.slice(0, 10) || '—' }}</template>
      </el-table-column>
      <el-table-column prop="remaining_sessions" label="剩余次" width="90">
        <template #default="{ row }">{{ row.remaining_sessions ?? '—' }}</template>
      </el-table-column>
      <el-table-column prop="balance" label="余额" width="100">
        <template #default="{ row }">{{ row.balance != null ? `¥${row.balance}` : '—' }}</template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip>
        <template #default="{ row }">{{ row.remark || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" min-width="168" fixed="right" align="right">
        <template #default="{ row }">
          <div class="row-actions">
            <el-button link type="primary" @click="openDetail(row)">详情</el-button>
            <el-button v-if="canConsume(row)" link type="success" @click="openConsume(row)">
              {{ row.product_type === 'count' ? '销次' : '扣值' }}
            </el-button>
            <el-dropdown trigger="click" teleported @command="onRowAction($event, row)">
              <el-button link type="primary">
                更多<el-icon class="more-icon"><ArrowDown /></el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item v-if="row.status !== 'void'" command="edit">编辑</el-dropdown-item>
                  <el-dropdown-item command="log">核销记录</el-dropdown-item>
                  <el-dropdown-item v-if="row.status === 'active'" command="renew">续卡</el-dropdown-item>
                  <el-dropdown-item v-if="row.status === 'active'" command="freeze">停卡</el-dropdown-item>
                  <el-dropdown-item v-if="row.status !== 'void'" command="void" divided>作废</el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </div>
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

    <el-drawer v-model="detailVisible" title="会籍详情" size="460px">
      <template v-if="detail">
        <h4 class="detail-section">会籍</h4>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="会员">{{ memberName(detail.member_id, detail) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(detail.status) }}</el-descriptions-item>
          <el-descriptions-item label="开卡">{{ datePart(detail.starts_at) || '—' }}</el-descriptions-item>
          <el-descriptions-item label="到期">{{ datePart(detail.ends_at) || '—' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.product_type === 'count'" label="剩余次">
            {{ detail.remaining_sessions ?? '—' }}
          </el-descriptions-item>
          <el-descriptions-item v-if="detail.product_type === 'value'" label="余额">
            {{ detail.balance != null ? moneyLabel(detail.balance) : '—' }}
          </el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '—' }}</el-descriptions-item>
        </el-descriptions>

        <h4 class="detail-section">卡种</h4>
        <el-descriptions :column="1" border>
          <template v-if="detailProduct">
            <el-descriptions-item label="名称">{{ detailProduct.name }}</el-descriptions-item>
            <el-descriptions-item label="类型">{{ productTypeLabel(detailProduct.product_type) }}</el-descriptions-item>
            <el-descriptions-item label="体验卡">{{ detailProduct.is_trial ? '是' : '否' }}</el-descriptions-item>
            <el-descriptions-item label="标价">{{ moneyLabel(detailProduct.price) }}</el-descriptions-item>
            <el-descriptions-item label="当前成交价">
              {{ moneyLabel(detailProduct.effective_price || detailProduct.price) }}
            </el-descriptions-item>
            <el-descriptions-item v-if="detailProduct.product_type === 'term'" label="有效天数">
              {{ detailProduct.duration_days ?? '—' }} 天
            </el-descriptions-item>
            <el-descriptions-item v-if="detailProduct.product_type === 'count'" label="次数额度">
              {{ detailProduct.session_count ?? '—' }} 次
            </el-descriptions-item>
            <el-descriptions-item v-if="detailProduct.product_type === 'value'" label="储值额度">
              {{ detailProduct.stored_value != null ? moneyLabel(detailProduct.stored_value) : '—' }}
            </el-descriptions-item>
            <el-descriptions-item label="活动价">
              {{ detailProduct.promo_price ? moneyLabel(detailProduct.promo_price) : '无' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="detailProduct.promo_price" label="活动起止">
              {{ `${datePart(detailProduct.promo_starts_at || '')} ~ ${datePart(detailProduct.promo_ends_at || '')}` }}
            </el-descriptions-item>
            <el-descriptions-item label="售卖状态">
              {{ detailProduct.is_active ? '在售' : '已停用' }}
            </el-descriptions-item>
          </template>
          <el-descriptions-item v-else label="卡种">{{ productName(detail.product_id) }}</el-descriptions-item>
        </el-descriptions>
        <div class="detail-actions">
          <el-button v-if="detail.status !== 'void'" type="primary" @click="openEdit(detail)">编辑</el-button>
          <el-button v-if="canConsume(detail)" type="success" @click="openConsume(detail)">
            {{ detail.product_type === 'count' ? '销次' : '扣值' }}
          </el-button>
          <el-button @click="openConsumeLog(detail)">核销记录</el-button>
          <el-button v-if="detail.status !== 'void'" type="danger" @click="voidMembership(detail)">作废</el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
        </div>
      </template>
    </el-drawer>

    <!-- 销次 / 扣值弹窗 -->
    <el-dialog
      v-model="consumeDialog"
      :title="consumeTarget?.product_type === 'count' ? '次卡销次' : '储值卡扣值'"
      width="460px"
      destroy-on-close
    >
      <el-descriptions v-if="consumeTarget" :column="1" border class="consume-info">
        <el-descriptions-item label="会员">
          {{ memberName(consumeTarget.member_id, consumeTarget) }}
        </el-descriptions-item>
        <el-descriptions-item label="卡种">{{ productName(consumeTarget.product_id) }}</el-descriptions-item>
        <el-descriptions-item v-if="consumeTarget.product_type === 'count'" label="当前剩余">
          {{ consumeTarget.remaining_sessions ?? 0 }} 次
        </el-descriptions-item>
        <el-descriptions-item v-else label="当前余额">
          {{ consumeTarget.balance != null ? moneyLabel(consumeTarget.balance) : '¥0.00' }}
        </el-descriptions-item>
      </el-descriptions>
      <el-form label-width="90px">
        <el-form-item v-if="consumeTarget?.product_type === 'count'" label="销次次数">
          <el-input-number v-model="consumeForm.sessions" :min="1" :max="100" />
        </el-form-item>
        <el-form-item v-else label="扣减金额">
          <el-input v-model="consumeForm.amount" placeholder="如 50.00" style="width: 160px" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="consumeForm.note" type="textarea" :rows="2" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="consumeDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="doConsume">确认核销</el-button>
      </template>
    </el-dialog>

    <!-- 核销记录 -->
    <el-drawer v-model="consumeLogVisible" title="核销记录" size="560px">
      <p class="lead" v-if="consumeLogTarget">
        会籍 #{{ consumeLogTarget.id }} · {{ memberName(consumeLogTarget.member_id, consumeLogTarget) }}
      </p>
      <el-table :data="consumeLogs" v-loading="consumeLogLoading" size="small" empty-text="暂无核销记录">
        <el-table-column label="时间" width="150">
          <template #default="{ row }">{{ row.created_at?.slice(0, 16).replace('T', ' ') }}</template>
        </el-table-column>
        <el-table-column label="类型" width="80">
          <template #default="{ row }">{{ consumptionKindLabel(row.kind) }}</template>
        </el-table-column>
        <el-table-column label="变动" width="90">
          <template #default="{ row }">{{ consumptionChangeText(row) }}</template>
        </el-table-column>
        <el-table-column label="核销后" width="120">
          <template #default="{ row }">{{ consumptionAfterText(row) }}</template>
        </el-table-column>
        <el-table-column label="来源" width="100">
          <template #default="{ row }">{{ consumptionSourceLabel(row.source) }}</template>
        </el-table-column>
        <el-table-column label="操作人" min-width="100">
          <template #default="{ row }">{{ row.actor_name || '系统' }}</template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination
          v-model:current-page="consumeLogPage"
          :page-size="consumeLogPageSize"
          :total="consumeLogTotal"
          layout="total, prev, pager, next"
          background
          @current-change="loadConsumeLogs"
        />
      </div>
    </el-drawer>

    <!-- 编辑会籍弹窗 -->
    <el-dialog v-model="editDialog" title="编辑会籍" width="500px" destroy-on-close>
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="90px">
        <el-form-item label="会员">
          <el-select
            v-if="isSiteAdmin"
            v-model="editForm.member_id"
            filterable
            style="width: 100%"
          >
            <el-option v-for="x in members" :key="x.id" :label="`${x.name}(${x.phone})`" :value="x.id" />
          </el-select>
          <el-input v-else :model-value="editing ? memberName(editing.member_id, editing) : ''" disabled />
        </el-form-item>
        <el-form-item label="卡种">
          <el-select
            v-if="isSiteAdmin"
            v-model="editForm.product_id"
            filterable
            style="width: 100%"
          >
            <el-option v-for="p in allProducts" :key="p.id" :label="p.name" :value="p.id" />
          </el-select>
          <el-input v-else :model-value="editing ? productName(editing.product_id) : ''" disabled />
        </el-form-item>
        <el-form-item label="开卡日">
          <el-date-picker v-model="editForm.starts_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="到期日">
          <el-date-picker v-model="editForm.ends_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="editingProductType === 'count'" label="剩余次">
          <el-input-number v-model="editForm.remaining_sessions" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item v-if="editingProductType === 'value'" label="余额">
          <el-input v-model="editForm.balance" placeholder="如 500.00" />
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="editForm.status" style="width: 100%">
            <el-option label="在籍" value="active" />
            <el-option label="已停卡" value="frozen" />
            <el-option label="已到期" value="expired" />
          </el-select>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.remark"
            type="textarea"
            :rows="3"
            maxlength="200"
            show-word-limit
            placeholder="如特殊约定、停卡原因等"
          />
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          :title="
            isSiteAdmin
              ? '超管可改正会员/卡种。修改后，门禁授权会按新会员与卡种同步。'
              : '修改到期日或状态后，门禁授权会同步更新'
          "
        />
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 办卡弹窗 -->
    <el-dialog v-model="purchaseDialog" title="办卡并收款" width="560px" destroy-on-close>
      <el-form ref="purchaseFormRef" :model="purchase" :rules="purchaseRules" label-width="90px">
        <el-form-item label="会员" prop="member_id">
          <el-select v-model="purchase.member_id" filterable style="width: 100%" @change="loadPurchaseCoupons">
            <el-option v-for="m in members" :key="m.id" :label="`${m.name}(${m.phone})`" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="卡种" prop="product_id">
          <el-select v-model="purchase.product_id" style="width: 100%">
            <el-option v-for="p in products" :key="p.id" :label="`${p.name} ¥${p.price}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优惠券">
          <el-select
            v-model="purchase.member_coupon_id"
            clearable
            filterable
            placeholder="会员可用优惠券"
            style="width: 100%"
            :disabled="!purchase.member_id"
            popper-class="coupon-select-popper"
            :fit-input-width="true"
            teleported
          >
            <el-option
              v-for="c in unusedCoupons"
              :key="c.id"
              :label="memberCouponName(c)"
              :value="c.id"
            >
              <div class="coupon-option">
                <div class="coupon-option__name">{{ memberCouponName(c) }}</div>
                <div class="coupon-option__meta">{{ memberCouponMeta(c) }}</div>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <div v-if="selectedPurchaseProduct" class="pay-summary">
          <div class="pay-row">
            <span>当前金额</span>
            <span>{{ moneyLabel(purchaseQuote.original) }}</span>
          </div>
          <div v-if="purchaseQuote.discount > 0" class="pay-row">
            <span>优惠抵扣</span>
            <span class="pay-off">-{{ moneyLabel(purchaseQuote.discount) }}</span>
          </div>
          <div class="pay-row pay-row--total">
            <span>支付金额</span>
            <span>{{ moneyLabel(purchaseQuote.payable) }}</span>
          </div>
          <p v-if="!purchaseQuote.usable" class="pay-warn">{{ purchaseQuote.reason }}</p>
        </div>
        <el-alert type="info" :closable="false" show-icon title="提交后将自动生成订单并登记线下收款（现金）" />
      </el-form>
      <template #footer>
        <el-button @click="purchaseDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!purchaseQuote.usable"
          @click="doPurchase"
        >
          办卡并收款 {{ selectedPurchaseProduct ? moneyLabel(purchaseQuote.payable) : '' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 续卡弹窗 -->
    <el-dialog v-model="renewDialog" title="续卡并收款" width="560px" destroy-on-close>
      <el-form ref="renewFormRef" :model="renew" :rules="renewRules" label-width="90px">
        <el-form-item label="会籍" prop="membership_id">
          <el-select
            v-model="renew.membership_id"
            filterable
            style="width: 100%"
            @change="loadRenewCoupons"
          >
            <el-option
              v-for="x in activeMemberships"
              :key="x.id"
              :label="`#${x.id} ${memberName(x.member_id)}（${productName(x.product_id)}）`"
              :value="x.id"
            />
          </el-select>
        </el-form-item>
        <div v-if="selectedRenewMembership" class="current-card">
          <div class="current-card__title">当前会籍（参考）</div>
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="会员" :span="2">
              {{ memberName(selectedRenewMembership.member_id, selectedRenewMembership) }}
            </el-descriptions-item>
            <el-descriptions-item label="卡种" :span="2">
              {{ productName(selectedRenewMembership.product_id) }}
              <div class="current-card__type">{{ productSpec(selectedRenewMembership.product_id) }}</div>
            </el-descriptions-item>
            <el-descriptions-item label="状态">{{ statusLabel(selectedRenewMembership.status) }}</el-descriptions-item>
            <el-descriptions-item label="开卡">{{ datePart(selectedRenewMembership.starts_at) || '—' }}</el-descriptions-item>
            <el-descriptions-item label="到期">{{ datePart(selectedRenewMembership.ends_at) || '—' }}</el-descriptions-item>
            <el-descriptions-item v-if="selectedRenewMembership.product_type === 'count'" label="剩余次">
              {{ selectedRenewMembership.remaining_sessions ?? '—' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="selectedRenewMembership.product_type === 'value'" label="余额">
              {{ selectedRenewMembership.balance != null ? moneyLabel(selectedRenewMembership.balance) : '—' }}
            </el-descriptions-item>
            <el-descriptions-item v-if="selectedRenewMembership.remark" label="备注" :span="2">
              {{ selectedRenewMembership.remark }}
            </el-descriptions-item>
          </el-descriptions>
          <p v-if="renewPreview" class="current-card__preview">{{ renewPreview }}</p>
          <p v-else-if="currentProduct" class="current-card__preview">
            不选新卡种时，按「{{ currentProduct.name }}」规则续期
          </p>
        </div>
        <el-form-item label="卡种">
          <el-select v-model="renew.product_id" clearable placeholder="沿用原卡种（可选）" style="width: 100%">
            <el-option v-for="p in products" :key="p.id" :label="`${p.name} ¥${p.price}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="优惠券">
          <el-select
            v-model="renew.member_coupon_id"
            clearable
            filterable
            placeholder="会员可用优惠券"
            style="width: 100%"
            :disabled="!renew.membership_id"
            popper-class="coupon-select-popper"
            :fit-input-width="true"
            teleported
          >
            <el-option
              v-for="c in unusedCoupons"
              :key="c.id"
              :label="memberCouponName(c)"
              :value="c.id"
            >
              <div class="coupon-option">
                <div class="coupon-option__name">{{ memberCouponName(c) }}</div>
                <div class="coupon-option__meta">{{ memberCouponMeta(c) }}</div>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <div v-if="selectedRenewProduct" class="pay-summary">
          <div class="pay-row">
            <span>当前金额</span>
            <span>{{ moneyLabel(renewQuote.original) }}</span>
          </div>
          <div v-if="renewQuote.discount > 0" class="pay-row">
            <span>优惠抵扣</span>
            <span class="pay-off">-{{ moneyLabel(renewQuote.discount) }}</span>
          </div>
          <div class="pay-row pay-row--total">
            <span>支付金额</span>
            <span>{{ moneyLabel(renewQuote.payable) }}</span>
          </div>
          <p v-if="!renewQuote.usable" class="pay-warn">{{ renewQuote.reason }}</p>
        </div>
        <el-alert type="info" :closable="false" show-icon title="不选卡种时按原会籍规则续期" />
      </el-form>
      <template #footer>
        <el-button @click="renewDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!renewQuote.usable"
          @click="doRenew"
        >
          续卡并收款 {{ selectedRenewProduct ? moneyLabel(renewQuote.payable) : '' }}
        </el-button>
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

.section-title {
  margin: 0 0 12px;
  font-size: 0.95rem;
}

.detail-section {
  margin: 0 0 10px;
  font-size: 0.9rem;
}

.detail-section + .el-descriptions + .detail-section {
  margin-top: 20px;
}

.card-spec {
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.row-actions {
  display: inline-flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 0 2px;
  max-width: 100%;
}
.row-actions :deep(.el-button.is-link) {
  margin: 0;
  padding: 0 6px;
  height: 28px;
}
.more-icon {
  margin-left: 2px;
  font-size: 12px;
}
.filters {
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.detail-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 20px;
}

.consume-info {
  margin-bottom: 16px;
}

.coupon-option {
  line-height: 1.4;
  padding: 4px 0;
}

.coupon-option__name {
  color: var(--el-text-color-primary);
}

.coupon-option__meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.pay-summary {
  margin: 0 0 16px 90px;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}

.pay-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}

.pay-row--total {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.pay-off {
  color: var(--el-color-danger);
}

.pay-warn {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-color-warning);
}

.current-card {
  margin: 0 0 16px 90px;
}

.current-card__title {
  margin-bottom: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.current-card__type {
  margin-left: 6px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.current-card__preview {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--el-color-primary);
}
</style>
