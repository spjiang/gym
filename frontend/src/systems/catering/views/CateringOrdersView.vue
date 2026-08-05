<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'

type Merchant = { id: number; name: string; subsystem_codes: string[] }
type MenuItem = { id: number; name: string; category: string; price: string; is_active: boolean }
type Order = {
  id: number
  title: string
  amount: string
  status: string
  merchant_id: number
  order_type: string
  member_id?: number | null
  member?: { id: number; name: string; phone: string } | null
  pickup_code?: string | null
}

const merchants = ref<Merchant[]>([])
const menu = ref<MenuItem[]>([])
const orders = ref<Order[]>([])
const merchantId = ref<number | undefined>()
const loading = ref(false)
const paying = ref(false)
const cart = reactive<Record<number, number>>({})
const orderTotal = ref(0)
const orderPage = ref(1)
const orderPageSize = ref(20)
const orderQuery = reactive({ q: '', status: '' })

const cateringMerchants = () =>
  merchants.value.filter((m) => (m.subsystem_codes || []).includes('catering'))

const cartLines = computed(() =>
  menu.value
    .filter((m) => (cart[m.id] || 0) > 0)
    .map((m) => ({
      item: m,
      qty: cart[m.id],
      amount: Number(m.price) * cart[m.id],
    })),
)

const cartTotal = computed(() => cartLines.value.reduce((s, l) => s + l.amount, 0))

function statusMeta(status: string) {
  return {
    paid: { type: 'success' as const, label: '已收款' },
    pending: { type: 'warning' as const, label: '待支付' },
    refunded: { type: 'danger' as const, label: '已退款' },
  }[status] || { type: 'info' as const, label: status }
}

function memberLabel(row: Order) {
  if (row.member) return `${row.member.name} ${row.member.phone}`
  if (row.member_id) return `#${row.member_id}`
  return '—'
}

async function refresh() {
  loading.value = true
  try {
    const { data: ms } = await http.get('/merchants')
    merchants.value = ms
    const list = cateringMerchants()
    if (!merchantId.value && list[0]) merchantId.value = list[0].id
    await loadMerchantData()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function loadMerchantData() {
  if (!merchantId.value) {
    menu.value = []
    orders.value = []
    orderTotal.value = 0
    return
  }
  const [m, o] = await Promise.all([
    http.get('/catering/menu-items', { params: { merchant_id: merchantId.value, active_only: true } }),
    http.get('/orders', {
      params: {
        merchant_id: merchantId.value,
        order_type: 'dining',
        page: orderPage.value,
        page_size: orderPageSize.value,
        q: orderQuery.q.trim() || undefined,
        status: orderQuery.status || undefined,
      },
    }),
  ])
  menu.value = m.data
  orders.value = o.data.items
  orderTotal.value = o.data.total
  for (const key of Object.keys(cart)) delete cart[Number(key)]
}

function searchOrders() {
  orderPage.value = 1
  void loadMerchantData()
}

function resetOrderSearch() {
  orderQuery.q = ''
  orderQuery.status = ''
  orderPage.value = 1
  void loadMerchantData()
}

function add(id: number) {
  cart[id] = (cart[id] || 0) + 1
}

function dec(id: number) {
  const n = (cart[id] || 0) - 1
  if (n <= 0) delete cart[id]
  else cart[id] = n
}

async function checkout() {
  if (!merchantId.value || !cartLines.value.length) {
    ElMessage.warning('请先选择菜品')
    return
  }
  paying.value = true
  try {
    const { data: order } = await http.post('/catering/checkout', {
      merchant_id: merchantId.value,
      items: cartLines.value.map((l) => ({ menu_item_id: l.item.id, quantity: l.qty })),
    })
    await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
    ElMessage.success(`收款成功 ¥${order.amount}`)
    await loadMerchantData()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '点单失败')
  } finally {
    paying.value = false
  }
}

async function payPending(row: Order) {
  try {
    await http.post(`/orders/${row.id}/pay/offline`, { channel: 'offline_cash' })
    ElMessage.success('线下收款成功')
    await loadMerchantData()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '收款失败')
  }
}

async function refund(row: Order) {
  try {
    await ElMessageBox.confirm(`确认退款订单 #${row.id}（¥${row.amount}）？`, '退款', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await http.post(`/orders/${row.id}/refund`)
    ElMessage.success('已退款')
    await loadMerchantData()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '退款失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar">
      <h3>点单收款</h3>
      <el-form inline>
        <el-form-item label="餐饮商户">
          <el-select v-model="merchantId" style="width: 220px" @change="loadMerchantData">
            <el-option v-for="m in cateringMerchants()" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
    </div>

    <el-alert
      v-if="!cateringMerchants().length"
      type="warning"
      :closable="false"
      title="没有餐饮商户"
      style="margin-bottom: 16px"
    />

    <div v-else class="layout">
      <section>
        <h4>菜单</h4>
        <div v-for="m in menu" :key="m.id" class="menu-row">
          <div>
            <strong>{{ m.name }}</strong>
            <div class="meta">{{ m.category }} · ¥{{ m.price }}</div>
          </div>
          <div class="qty">
            <el-button size="small" @click="dec(m.id)" :disabled="!(cart[m.id] > 0)">-</el-button>
            <span>{{ cart[m.id] || 0 }}</span>
            <el-button size="small" type="primary" @click="add(m.id)">+</el-button>
          </div>
        </div>
        <div v-if="!menu.length" class="empty">暂无在售菜品，请先维护菜单</div>
      </section>

      <section class="cart">
        <h4>当前点单</h4>
        <div v-for="l in cartLines" :key="l.item.id" class="cart-line">
          <span>{{ l.item.name }} × {{ l.qty }}</span>
          <span>¥{{ l.amount.toFixed(2) }}</span>
        </div>
        <div v-if="!cartLines.length" class="empty">尚未选择菜品</div>
        <div class="total">合计 <b>¥{{ cartTotal.toFixed(2) }}</b></div>
        <el-button type="primary" :loading="paying" :disabled="!cartLines.length" @click="checkout">
          下单并线下收款
        </el-button>
      </section>
    </div>

    <h4 style="margin-top: 28px">餐饮订单</h4>
    <div class="filters">
      <el-input
        v-model="orderQuery.q"
        clearable
        placeholder="单号 / 标题 / 会员"
        style="width: 200px"
        @keyup.enter="searchOrders"
      />
      <el-select v-model="orderQuery.status" clearable placeholder="状态" style="width: 120px">
        <el-option label="待支付" value="pending" />
        <el-option label="已收款" value="paid" />
        <el-option label="已退款" value="refunded" />
      </el-select>
      <el-button type="primary" @click="searchOrders">查询</el-button>
      <el-button @click="resetOrderSearch">重置</el-button>
    </div>
    <el-table :data="orders" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column label="会员" min-width="140">
        <template #default="{ row }">{{ memberLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="取餐号" width="90">
        <template #default="{ row }">{{ row.pickup_code || '—' }}</template>
      </el-table-column>
      <el-table-column label="金额" width="100">
        <template #default="{ row }">¥{{ row.amount }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="200">
        <template #default="{ row }">
          <el-button size="small" :disabled="row.status !== 'pending'" @click="payPending(row)">收款</el-button>
          <el-button size="small" :disabled="row.status !== 'paid'" @click="refund(row)">退款</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="orderPage"
        v-model:page-size="orderPageSize"
        :total="orderTotal"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
        @current-change="loadMerchantData"
        @size-change="
          () => {
            orderPage = 1
            loadMerchantData()
          }
        "
      />
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.toolbar h3 {
  margin: 0;
}
.layout {
  display: grid;
  grid-template-columns: 1.4fr 1fr;
  gap: 16px;
}
.menu-row,
.cart-line {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(28, 25, 23, 0.08);
}
.meta {
  font-size: 12px;
  color: var(--admin-ink-muted);
}
.qty {
  display: flex;
  align-items: center;
  gap: 8px;
}
.cart {
  padding: 14px;
  border: 1px solid rgba(28, 25, 23, 0.08);
  border-radius: 12px;
  background: #fffcf8;
}
.total {
  margin: 12px 0;
  font-size: 15px;
}
.empty {
  color: var(--admin-ink-muted);
  font-size: 13px;
  padding: 12px 0;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin: 8px 0 12px;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
@media (max-width: 900px) {
  .layout {
    grid-template-columns: 1fr;
  }
}
</style>
