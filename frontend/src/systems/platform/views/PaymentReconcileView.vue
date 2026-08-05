<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import { orderStatusLabel } from '../../../core/labels'

type Item = Record<string, unknown>
const kind = ref('pay_stale')
const items = ref<Item[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<{ items: Item[] }>('/site/payment-reconcile/items', {
      params: { kind: kind.value },
    })
    items.value = data.items || []
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
    <el-table :data="items" stripe>
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
</style>
