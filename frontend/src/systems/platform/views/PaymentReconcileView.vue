<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import { orderStatusLabel } from '../../../core/labels'

type Item = Record<string, unknown>
const kind = ref('pay_stale')
const items = ref<Item[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ q: '', status: '' })
const filteredItems = computed(() => {
  const kw = query.q.trim()
  return items.value.filter((row) => {
    if (query.status && String(row.status || '') !== query.status) return false
    if (!kw) return true
    const hay = [row.order_id, row.intent_id, row.refund_intent_id, row.out_trade_no, row.status, row.amount]
      .map((v) => String(v ?? ''))
      .join(' ')
    return hay.includes(kw)
  })
})
const pagedItems = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredItems.value.slice(start, start + pageSize.value)
})
watch(query, () => {
  page.value = 1
}, { deep: true })

function resetSearch() {
  query.q = ''
  query.status = ''
  page.value = 1
}

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<{ items: Item[] }>('/site/payment-reconcile/items', {
      params: { kind: kind.value },
    })
    items.value = data.items || []
    page.value = 1
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function queryPay(row: Item) {
  try {
    await http.post('/site/payment-reconcile/actions/query-pay', { order_id: row.order_id })
    ElMessage.success('已查单')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '失败')
  }
}

async function closeIntent(row: Item) {
  try {
    await http.post('/site/payment-reconcile/actions/close-intent', {
      intent_id: row.intent_id,
      reason: '对账关闭',
    })
    ElMessage.success('已关闭')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '失败')
  }
}

async function forceFulfill(row: Item) {
  try {
    await http.post('/site/payment-reconcile/actions/force-fulfill', {
      order_id: row.order_id,
      reason: '对账强制履约',
    })
    ElMessage.success('已补履约')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '失败')
  }
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar">
      <h3>支付对账</h3>
      <el-select v-model="kind" style="width: 220px" @change="load">
        <el-option label="支付待确认" value="pay_stale" />
        <el-option label="支付不一致" value="pay_mismatch" />
        <el-option label="退款异常" value="refund_abnormal" />
      </el-select>
      <el-button @click="load">刷新</el-button>
    </div>
    <div class="filters">
      <el-input v-model="query.q" clearable placeholder="订单号 / 商户单号 / 意图" style="width: 240px" />
      <el-select v-model="query.status" clearable placeholder="订单状态" style="width: 140px">
        <el-option label="待支付" value="pending" />
        <el-option label="已收款" value="paid" />
        <el-option label="已退款" value="refunded" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-button @click="resetSearch">重置</el-button>
    </div>
    <el-table :data="pagedItems" stripe>
      <el-table-column prop="order_id" label="订单" width="90" />
      <el-table-column prop="intent_id" label="支付意图" width="100" />
      <el-table-column prop="refund_intent_id" label="退款意图" width="100" />
      <el-table-column prop="out_trade_no" label="商户单号" min-width="160" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">{{ orderStatusLabel(String(row.status || '')) || row.status || '—' }}</template>
      </el-table-column>
      <el-table-column prop="amount" label="金额" width="100" />
      <el-table-column label="操作" width="280" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="queryPay(row)">查单</el-button>
          <el-button size="small" @click="closeIntent(row)">关闭意图</el-button>
          <el-button size="small" type="danger" @click="forceFulfill(row)">强制履约</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="filteredItems.length"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
      />
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 12px;
}
.toolbar h3 {
  margin: 0;
  margin-right: auto;
}
.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
