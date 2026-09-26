<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'
import RowActions from '../../../core/components/RowActions.vue'
import { orderStatusLabel } from '../../../core/labels'

type Item = {
  kind: string
  order_id?: number
  order_no?: string
  title?: string
  member_name?: string
  member_phone?: string
  order_status?: string
  amount?: string
  issue?: string
  created_at?: string
  intent_id?: number
  refund_intent_id?: number
  refund_status?: string
  out_trade_no?: string
  wechat_transaction_id?: string
  out_refund_no?: string
  status?: string
}

const tabs = [
  {
    value: 'pay_stale',
    label: '收款未到账',
    hint: '客人已经发起支付，超过 15 分钟还没到账。可向微信查询，或关闭后让客人重新支付。',
  },
  {
    value: 'pay_mismatch',
    label: '收款对不上',
    hint: '微信侧已经收款，或订单状态和收款记录不一致。确认后可以补记为已收款。',
  },
  {
    value: 'refund_abnormal',
    label: '退款未完成',
    hint: '退款已经提交，系统还没记成已退款。客人零钱已到账时，再确认为已退款。',
  },
]

const kind = ref('pay_stale')
const items = ref<Item[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ q: '', status: '' })

const currentTab = computed(() => tabs.find((tab) => tab.value === kind.value) || tabs[0])

const filteredItems = computed(() => {
  const kw = query.q.trim().toLowerCase()
  return items.value.filter((row) => {
    if (query.status && (row.order_status || '') !== query.status) return false
    if (!kw) return true
    const hay = [
      row.order_no,
      row.order_id,
      row.title,
      row.member_name,
      row.member_phone,
      row.out_trade_no,
      row.wechat_transaction_id,
      row.out_refund_no,
      row.issue,
    ]
      .map((value) => String(value ?? '').toLowerCase())
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

function memberLabel(row: Item) {
  if (!row.member_name && !row.member_phone) return '—'
  return [row.member_name, row.member_phone].filter(Boolean).join(' ')
}

function formatTime(value?: string) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value.replace('T', ' ').slice(0, 19)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

function progressLabel(row: Item) {
  if (row.kind === 'refund_abnormal') {
    return (
      {
        processing: '处理中',
        failed: '失败',
        created: '未完成',
      }[row.refund_status || row.status || ''] || '未完成'
    )
  }
  return orderStatusLabel(row.order_status || '') || '—'
}

function progressType(row: Item) {
  const code = row.kind === 'refund_abnormal' ? row.refund_status || row.status : row.order_status
  if (code === 'failed') return 'danger'
  if (code === 'processing' || code === 'created' || code === 'pending') return 'warning'
  if (code === 'paid' || code === 'refunded') return 'success'
  return 'info'
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

function fail(e: unknown, fallback: string) {
  if (e === 'cancel') return
  ElMessage.error(e instanceof Error ? e.message : fallback)
}

async function queryPay(row: Item) {
  try {
    await http.post('/site/payment-reconcile/actions/query-pay', { order_id: row.order_id })
    ElMessage.success('已向微信查询')
    await load()
  } catch (e: unknown) {
    fail(e, '查询失败')
  }
}

async function closeIntent(row: Item) {
  try {
    await ElMessageBox.confirm('这笔支付还没到账。关闭后，客人需要重新发起支付。', '关闭未到账的支付', {
      type: 'warning',
      confirmButtonText: '关闭',
      cancelButtonText: '取消',
    })
    await http.post('/site/payment-reconcile/actions/close-intent', {
      intent_id: row.intent_id,
      reason: '对账关闭未到账支付',
    })
    ElMessage.success('已关闭')
    await load()
  } catch (e: unknown) {
    fail(e, '关闭失败')
  }
}

async function markPaid(row: Item) {
  try {
    await ElMessageBox.confirm('确认微信已经收到这笔钱？确认后订单会记为已收款。', '补记为已收款', {
      type: 'warning',
      confirmButtonText: '补记已收款',
      cancelButtonText: '取消',
    })
    await http.post('/site/payment-reconcile/actions/force-fulfill', {
      order_id: row.order_id,
      reason: '对账补记已收款',
    })
    ElMessage.success('已记为已收款')
    await load()
  } catch (e: unknown) {
    fail(e, '补记失败')
  }
}

async function markRefunded(row: Item) {
  try {
    await ElMessageBox.confirm(
      '确认客人已经收到这笔退款？确认后，订单会按已退款入账。',
      '确认为已退款',
      { type: 'warning', confirmButtonText: '确认已退款', cancelButtonText: '取消' },
    )
    await http.post('/site/payment-reconcile/actions/force-refund-success', {
      refund_intent_id: row.refund_intent_id,
      reason: '对账确认退款已到账',
    })
    ElMessage.success('已记为已退款')
    await load()
  } catch (e: unknown) {
    fail(e, '确认失败')
  }
}

function moreActions(row: Item) {
  if (row.kind === 'pay_stale' && row.intent_id) {
    return [{ command: 'close', label: '关闭这笔支付', danger: true }]
  }
  return []
}

function onMore(row: Item, command: string) {
  if (command === 'close') closeIntent(row)
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar">
      <div>
        <h3>收退款异常</h3>
        <p class="lead">只处理没收齐、退不完，或和微信对不上的单据。正常收款看「订单收款」，正常退款看「退款记录」。</p>
      </div>
      <el-button @click="load">刷新</el-button>
    </div>

    <el-radio-group v-model="kind" class="tabs" @change="load">
      <el-radio-button v-for="tab in tabs" :key="tab.value" :value="tab.value">{{ tab.label }}</el-radio-button>
    </el-radio-group>
    <p class="hint">{{ currentTab.hint }}</p>

    <div class="filters">
      <el-input
        v-model="query.q"
        clearable
        placeholder="订单号 / 标题 / 会员 / 微信单号"
        style="width: 280px"
      />
      <el-select v-model="query.status" clearable placeholder="订单状态" style="width: 140px">
        <el-option label="待支付" value="pending" />
        <el-option label="已收款" value="paid" />
        <el-option label="已退款" value="refunded" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="pagedItems" stripe>
      <el-table-column label="订单号" min-width="200">
        <template #default="{ row }">
          <div>{{ row.order_no || '—' }}</div>
          <div v-if="row.wechat_transaction_id" class="sub">微信 {{ row.wechat_transaction_id }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="160">
        <template #default="{ row }">{{ row.title || '—' }}</template>
      </el-table-column>
      <el-table-column label="会员" min-width="150">
        <template #default="{ row }">{{ memberLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="金额" width="100">
        <template #default="{ row }"><b>¥{{ row.amount || '—' }}</b></template>
      </el-table-column>
      <el-table-column label="问题" min-width="240">
        <template #default="{ row }">{{ row.issue || '—' }}</template>
      </el-table-column>
      <el-table-column label="进度" width="100">
        <template #default="{ row }">
          <el-tag :type="progressType(row)" size="small">{{ progressLabel(row) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="时间" width="150">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <RowActions :more="moreActions(row)" @more="(command) => onMore(row, command)">
            <el-button v-if="row.kind === 'pay_stale'" size="small" type="primary" @click="queryPay(row)">
              查询结果
            </el-button>
            <el-button v-else-if="row.kind === 'pay_mismatch'" size="small" type="primary" @click="markPaid(row)">
              补记已收款
            </el-button>
            <el-button v-else size="small" type="primary" @click="markRefunded(row)">确认为已退款</el-button>
          </RowActions>
        </template>
      </el-table-column>
      <template #empty>
        <span class="empty">当前没有这类异常</span>
      </template>
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
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0;
}
.lead,
.hint,
.sub,
.empty {
  color: var(--admin-ink-muted, #8b939c);
  font-size: 13px;
}
.lead {
  margin: 6px 0 0;
}
.tabs {
  margin-bottom: 8px;
}
.hint {
  margin: 0 0 12px;
}
.filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.sub {
  margin-top: 4px;
  font-size: 12px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
