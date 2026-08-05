<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { merchantsWithSystem } from '../../../core/nav/systems'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Product = { id: number; name: string; price: string; is_active: boolean }
type Membership = {
  id: number
  member_id: number
  product_id: number
  status: string
  ends_at: string | null
  remaining_sessions: number | null
  balance: string | null
  member?: { id: number; name: string; phone: string } | null
}
type MemberCoupon = { id: number; member_id: number; template_id: number; status: string }
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const products = ref<Product[]>([])
const memberships = ref<Membership[]>([])
const merchantId = ref<number | undefined>()
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ q: '', status: '' as string })
const detailVisible = ref(false)
const detail = ref<Membership | null>(null)

const purchaseDialog = ref(false)
const renewDialog = ref(false)
const submitting = ref(false)
const purchaseFormRef = ref<FormInstance>()
const renewFormRef = ref<FormInstance>()

const purchase = reactive({
  member_id: undefined as number | undefined,
  product_id: undefined as number | undefined,
  member_coupon_id: undefined as number | undefined,
})
const renew = reactive({
  membership_id: undefined as number | undefined,
  product_id: undefined as number | undefined,
})
const unusedCoupons = ref<MemberCoupon[]>([])

const purchaseRules: FormRules = {
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
  product_id: [{ required: true, message: '请选择卡种', trigger: 'change' }],
}

const renewRules: FormRules = {
  membership_id: [{ required: true, message: '请选择要续卡的会籍', trigger: 'change' }],
}

const activeMemberships = computed(() => memberships.value.filter((x) => x.status === 'active'))

function memberName(id: number, row?: Membership) {
  if (row?.member) return `${row.member.name}(${row.member.phone})`
  const m = members.value.find((x) => x.id === id)
  return m ? `${m.name}(${m.phone})` : `#${id}`
}

function productName(id: number) {
  return products.value.find((p) => p.id === id)?.name || `#${id}`
}

function statusLabel(s: string) {
  return { active: '在籍', frozen: '已停卡', expired: '已到期' }[s] || s
}

function openDetail(row: Membership) {
  detail.value = row
  detailVisible.value = true
}

async function loadUnusedCoupons() {
  purchase.member_coupon_id = undefined
  unusedCoupons.value = []
  if (!merchantId.value || !purchase.member_id) return
  const { data } = await http.get('/coupons/member-coupons', {
    params: {
      merchant_id: merchantId.value,
      member_id: purchase.member_id,
      status: 'unused',
      page: 1,
      page_size: 100,
    },
  })
  unusedCoupons.value = data.items
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
    const [p, ms] = await Promise.all([
      http.get('/membership-products', { params: { merchant_id: merchantId.value } }),
      http.get<Page<Membership>>('/memberships', {
        params: {
          merchant_id: merchantId.value,
          page: page.value,
          page_size: pageSize.value,
          q: query.q.trim() || undefined,
          status: query.status || undefined,
        },
      }),
    ])
    products.value = p.data.filter((x: Product) => x.is_active)
    memberships.value = ms.data.items
    total.value = ms.data.total
    await loadUnusedCoupons()
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
  if (!ok) return
  submitting.value = true
  try {
    const { data: order } = await http.post('/memberships/purchase', {
      member_id: purchase.member_id,
      product_id: purchase.product_id,
      merchant_id: merchantId.value,
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
  renewFormRef.value?.clearValidate()
  renewDialog.value = true
}

async function doRenew() {
  const ok = await renewFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    const { data: order } = await http.post('/memberships/renew', {
      membership_id: renew.membership_id,
      product_id: renew.product_id ?? null,
      merchant_id: merchantId.value,
    })
    await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
    ElMessage.success('续卡并收款成功')
    renewDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '续卡失败')
  } finally {
    submitting.value = false
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
      <h3>办卡会籍</h3>
      <el-button type="primary" @click="openPurchaseDialog">办卡并收款</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select
          v-model="merchantId"
          style="width: 200px"
          @change="
            () => {
              page = 1
              refresh()
            }
          "
        >
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
      <el-table-column label="卡种" width="160">
        <template #default="{ row }">{{ productName(row.product_id) }}</template>
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
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="row.status === 'active'" link type="primary" @click="openRenewDialog(row)">续卡</el-button>
          <el-button v-if="row.status === 'active'" link type="danger" @click="freeze(row)">停卡</el-button>
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

    <el-drawer v-model="detailVisible" title="会籍详情" size="420px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="会员">{{ memberName(detail.member_id, detail) }}</el-descriptions-item>
          <el-descriptions-item label="卡种">{{ productName(detail.product_id) }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ statusLabel(detail.status) }}</el-descriptions-item>
          <el-descriptions-item label="到期">{{ detail.ends_at?.slice(0, 10) || '—' }}</el-descriptions-item>
          <el-descriptions-item label="剩余次">{{ detail.remaining_sessions ?? '—' }}</el-descriptions-item>
          <el-descriptions-item label="余额">
            {{ detail.balance != null ? `¥${detail.balance}` : '—' }}
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>

    <!-- 办卡弹窗 -->
    <el-dialog v-model="purchaseDialog" title="办卡并收款" width="500px" destroy-on-close>
      <el-form ref="purchaseFormRef" :model="purchase" :rules="purchaseRules" label-width="90px">
        <el-form-item label="会员" prop="member_id">
          <el-select v-model="purchase.member_id" filterable style="width: 100%" @change="loadUnusedCoupons">
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
            placeholder="会员可用优惠券"
            style="width: 100%"
            :disabled="!purchase.member_id"
          >
            <el-option v-for="c in unusedCoupons" :key="c.id" :label="`券#${c.id}`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon title="提交后将自动生成订单并登记线下收款（现金）" />
      </el-form>
      <template #footer>
        <el-button @click="purchaseDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="doPurchase">办卡并收款</el-button>
      </template>
    </el-dialog>

    <!-- 续卡弹窗 -->
    <el-dialog v-model="renewDialog" title="续卡并收款" width="480px" destroy-on-close>
      <el-form ref="renewFormRef" :model="renew" :rules="renewRules" label-width="90px">
        <el-form-item label="会籍" prop="membership_id">
          <el-select v-model="renew.membership_id" filterable style="width: 100%">
            <el-option
              v-for="x in activeMemberships"
              :key="x.id"
              :label="`#${x.id} ${memberName(x.member_id)}（${productName(x.product_id)}）`"
              :value="x.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="卡种">
          <el-select v-model="renew.product_id" clearable placeholder="沿用原卡种（可选）" style="width: 100%">
            <el-option v-for="p in products" :key="p.id" :label="`${p.name} ¥${p.price}`" :value="p.id" />
          </el-select>
        </el-form-item>
        <el-alert type="info" :closable="false" show-icon title="不选卡种时按原会籍规则续期" />
      </el-form>
      <template #footer>
        <el-button @click="renewDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="doRenew">续卡并收款</el-button>
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

.section-title {
  margin: 0 0 12px;
  font-size: 0.95rem;
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
