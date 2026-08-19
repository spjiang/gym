<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'
import { diningStatusLabel } from '../../../core/labels'
import { canAny } from '../../../core/nav/systems'
import { useAuthStore } from '../../../core/stores/auth'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes: string[] }
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
  dining_status?: string | null
}

const merchants = ref<Merchant[]>([])
const orders = ref<Order[]>([])
const { merchantId } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const router = useRouter()
const auth = useAuthStore()
const canOperate = computed(() => canAny(auth.me?.permissions || [], ['catering:order', '*']))
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ q: '', status: '', dining_status: '' })

const cateringMerchants = () =>
  merchants.value.filter((m) => (m.subsystem_codes || []).includes('catering'))

function statusMeta(status: string) {
  return {
    paid: { type: 'success' as const, label: '已收款' },
    pending: { type: 'warning' as const, label: '待支付' },
    refunded: { type: 'danger' as const, label: '已退款' },
    cancelled: { type: 'info' as const, label: '已取消' },
  }[status] || { type: 'info' as const, label: status }
}

function diningMeta(status: string | null | undefined) {
  return {
    preparing: { type: 'warning' as const },
    ready: { type: 'success' as const },
    completed: { type: 'info' as const },
  }[status || ''] || { type: 'info' as const }
}

function kitchenStatus(row: Order) {
  if (row.status !== 'paid') return '—'
  return diningStatusLabel(row.dining_status || 'preparing')
}

function memberLabel(row: Order) {
  if (row.member) return `${row.member.name} ${row.member.phone}`
  if (row.member_id) return `#${row.member_id}`
  return '—'
}

async function loadMerchants() {
  const { data } = await http.get('/merchants')
  merchants.value = data
  const list = cateringMerchants()
  if (merchantId.value && !list.some((m) => m.id === merchantId.value)) merchantId.value = undefined
}

async function loadOrders() {
  loading.value = true
  try {
    const { data } = await http.get('/orders', {
      params: {
        merchant_id: merchantId.value,
        order_type: 'dining',
        page: page.value,
        page_size: pageSize.value,
        q: query.q.trim() || undefined,
        status: query.status || undefined,
        dining_status: query.dining_status || undefined,
      },
    })
    orders.value = data.items
    total.value = data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
    orders.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function refresh() {
  await loadMerchants()
  await loadOrders()
}

function search() {
  page.value = 1
  void loadOrders()
}

function resetSearch() {
  query.q = ''
  query.status = ''
  query.dining_status = ''
  page.value = 1
  void loadOrders()
}

async function payPending(row: Order) {
  try {
    await http.post(`/orders/${row.id}/pay/offline`, { channel: 'offline_cash' })
    ElMessage.success('线下收款成功，已送出餐看板')
    await router.replace({ name: 'catering-kitchen', query: { ticket: String(row.id) } })
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '收款失败')
  }
}

async function cancelPending(row: Order) {
  try {
    await ElMessageBox.confirm(`取消待支付订单 #${row.id}？优惠券将退回。`, '取消订单', {
      type: 'warning',
    })
  } catch {
    return
  }
  try {
    await http.post(`/catering/orders/${row.id}/cancel`)
    ElMessage.success('已取消')
    await loadOrders()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '取消失败')
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
    await loadOrders()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '退款失败')
  }
}

async function markReady(row: Order) {
  try {
    await http.post(`/catering/orders/${row.id}/ready`)
    ElMessage.success('已出餐，待取餐')
    await loadOrders()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '出餐失败')
  }
}

async function markComplete(row: Order) {
  try {
    await http.post(`/catering/orders/${row.id}/complete`)
    ElMessage.success('已完成取餐')
    await loadOrders()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '完成失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>餐饮订单</h3>
        <p class="hint">查询餐饮单、待支付收款、退款。现场点菜请走「吧台点单」，出餐请看出餐看板。</p>
      </div>
      <el-button v-if="canOperate" type="primary" @click="router.push('/catering/pos')">去吧台点单</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="餐饮商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="search">
          <el-option v-for="m in cateringMerchants()" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input
          v-model="query.q"
          clearable
          placeholder="单号 / 标题 / 会员"
          style="width: 200px"
          @keyup.enter="search"
        />
      </el-form-item>
      <el-form-item label="收款状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px" @change="search">
          <el-option label="待支付" value="pending" />
          <el-option label="已收款" value="paid" />
          <el-option label="已退款" value="refunded" />
          <el-option label="已取消" value="cancelled" />
        </el-select>
      </el-form-item>
      <el-form-item label="制作进度">
        <el-select v-model="query.dining_status" clearable placeholder="全部" style="width: 120px" @change="search">
          <el-option label="制作中" value="preparing" />
          <el-option label="待取餐" value="ready" />
          <el-option label="已完成" value="completed" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="!cateringMerchants().length"
      type="warning"
      :closable="false"
      title="没有餐饮商户"
      style="margin-bottom: 16px"
    />

    <el-table :data="orders" v-loading="loading" stripe>
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
      <el-table-column label="收款" width="90">
        <template #default="{ row }">
          <el-tag :type="statusMeta(row.status).type" size="small">{{ statusMeta(row.status).label }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="制作进度" width="100">
        <template #default="{ row }">
          <el-tag v-if="row.status === 'paid'" :type="diningMeta(row.dining_status || 'preparing').type" size="small">
            {{ kitchenStatus(row) }}
          </el-tag>
          <span v-else>—</span>
        </template>
      </el-table-column>
      <el-table-column v-if="canOperate" label="操作" min-width="300">
        <template #default="{ row }">
          <el-button size="small" :disabled="row.status !== 'pending'" @click="payPending(row)">收款</el-button>
          <el-button size="small" :disabled="row.status !== 'pending'" @click="cancelPending(row)">取消</el-button>
          <el-button
            size="small"
            type="primary"
            :disabled="row.status !== 'paid' || (row.dining_status || 'preparing') !== 'preparing'"
            @click="markReady(row)"
          >
            出餐
          </el-button>
          <el-button
            size="small"
            :disabled="row.status !== 'paid' || row.dining_status !== 'ready'"
            @click="markComplete(row)"
          >
            完成
          </el-button>
          <el-button size="small" :disabled="row.status !== 'paid'" @click="refund(row)">退款</el-button>
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
        @current-change="loadOrders"
        @size-change="
          () => {
            page = 1
            loadOrders()
          }
        "
      />
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.toolbar h3 {
  margin: 0;
}
.hint {
  margin: 6px 0 0;
  color: var(--admin-ink-muted);
  font-size: 13px;
}
.filters {
  margin-bottom: 4px;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
</style>
