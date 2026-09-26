<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'

type RefundRow = {
  id: number
  order_id: number
  order_no: string
  title: string
  merchant_id: number
  merchant_name?: string | null
  member_name?: string | null
  member_phone?: string | null
  amount: string
  channel: string
  status: string
  reason?: string | null
  out_refund_no: string
  provider_ref?: string | null
  actor_name?: string | null
  created_at?: string | null
  succeeded_at?: string | null
}

const router = useRouter()
const rows = ref<RefundRow[]>([])
const merchants = ref<{ id: number; name: string }[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const query = reactive({
  q: '',
  status: '',
  merchant_id: undefined as number | undefined,
  createdRange: null as [string, string] | null,
})

const statusMeta: Record<string, { type: 'success' | 'warning' | 'info' | 'danger'; label: string }> = {
  succeeded: { type: 'success', label: '已到账' },
  processing: { type: 'warning', label: '处理中' },
  created: { type: 'info', label: '已发起' },
  failed: { type: 'danger', label: '失败' },
}

function statusOf(status: string) {
  return statusMeta[status] || { type: 'info' as const, label: status }
}

function channelLabel(channel: string) {
  return (
    {
      wechat_original: '退回微信',
      offline_cash: '现金',
      offline_transfer: '转账',
      online: '线上',
    }[channel] || channel
  )
}

function memberLabel(row: RefundRow) {
  if (!row.member_name && !row.member_phone) return '—'
  return [row.member_name, row.member_phone].filter(Boolean).join(' ')
}

function formatTime(value?: string | null) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

async function loadMerchants() {
  try {
    const { data } = await http.get<{ id: number; name: string }[]>('/merchants')
    merchants.value = data
  } catch {
    merchants.value = []
  }
}

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<{ items: RefundRow[]; total: number }>('/orders/refunds', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        q: query.q || undefined,
        status: query.status || undefined,
        merchant_id: query.merchant_id,
        created_from: query.createdRange?.[0],
        created_to: query.createdRange?.[1],
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
  load()
}

function resetSearch() {
  query.q = ''
  query.status = ''
  query.merchant_id = undefined
  query.createdRange = null
  search()
}

onMounted(() => {
  loadMerchants()
  load()
})
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>退款记录</h3>
      <el-button @click="router.push('/orders')">返回订单收款</el-button>
    </div>

    <div class="filters">
      <el-input
        v-model="query.q"
        clearable
        placeholder="订单号 / 标题 / 会员 / 退款单号"
        style="width: 240px"
        @keyup.enter="search"
      />
      <el-select v-model="query.status" clearable placeholder="状态" style="width: 140px">
        <el-option label="已到账" value="succeeded" />
        <el-option label="处理中" value="processing" />
        <el-option label="已发起" value="created" />
        <el-option label="失败" value="failed" />
      </el-select>
      <el-select v-model="query.merchant_id" clearable placeholder="商户" style="width: 180px">
        <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-date-picker
        v-model="query.createdRange"
        type="daterange"
        value-format="YYYY-MM-DD"
        start-placeholder="退款开始"
        end-placeholder="退款结束"
        range-separator="至"
        style="width: 260px"
      />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="order_no" label="订单号" min-width="210" />
      <el-table-column prop="title" label="标题" min-width="160" />
      <el-table-column label="会员" min-width="160">
        <template #default="{ row }">{{ memberLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="商户" width="140">
        <template #default="{ row }">{{ row.merchant_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="退款金额" width="110">
        <template #default="{ row }"><b>¥{{ row.amount }}</b></template>
      </el-table-column>
      <el-table-column label="退款方式" width="110">
        <template #default="{ row }">{{ channelLabel(row.channel) }}</template>
      </el-table-column>
      <el-table-column label="原因" min-width="140">
        <template #default="{ row }">{{ row.reason || '—' }}</template>
      </el-table-column>
      <el-table-column prop="out_refund_no" label="退款单号" min-width="180" />
      <el-table-column label="操作人" width="110">
        <template #default="{ row }">{{ row.actor_name || '—' }}</template>
      </el-table-column>
      <el-table-column label="发起时间" min-width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="到账时间" min-width="170">
        <template #default="{ row }">{{ formatTime(row.succeeded_at) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100" fixed="right">
        <template #default="{ row }">
          <el-tag :type="statusOf(row.status).type" size="small">{{ statusOf(row.status).label }}</el-tag>
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
  </div>
</template>
