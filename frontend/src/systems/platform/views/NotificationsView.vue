<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import http from '../../../core/api/http'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string }
type Note = {
  id: number
  merchant_id: number | null
  member_id: number | null
  event_type: string
  title: string
  body: string
  created_at: string
  member?: { id: number; name: string; phone: string } | null
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const notes = ref<Note[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const { merchantId } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const query = reactive({ q: '', event_type: '' })
const detailVisible = ref(false)
const detail = ref<Note | null>(null)

function memberLabel(row: Note) {
  if (row.member) return `${row.member.name} ${row.member.phone}`
  if (row.member_id) return `#${row.member_id}`
  return '—'
}

async function refresh() {
  loading.value = true
  try {
    const { data: m } = await http.get('/merchants')
    merchants.value = m
    const { data } = await http.get<Page<Note>>('/notifications', {
      params: {
        merchant_id: merchantId.value || undefined,
        q: query.q.trim() || undefined,
        event_type: query.event_type || undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    notes.value = data.items
    total.value = data.total
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
  query.event_type = ''
  page.value = 1
  void refresh()
}

function openDetail(row: Note) {
  detail.value = row
  detailVisible.value = true
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>通知中心</h3>
    </div>
    <div class="filters">
      <el-select
        v-model="merchantId"
        clearable
        placeholder="商户"
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
      <el-input
        v-model="query.q"
        clearable
        placeholder="标题 / 内容 / 事件"
        style="width: 220px"
        @keyup.enter="search"
      />
      <el-select v-model="query.event_type" clearable placeholder="事件类型" style="width: 180px">
        <el-option label="订单已收款" value="order.paid" />
        <el-option label="会籍履约" value="membership.fulfilled" />
        <el-option label="团课预约" value="group.booked" />
      </el-select>
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="notes" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="event_type" label="事件" width="160" />
      <el-table-column prop="title" label="标题" min-width="140" />
      <el-table-column prop="body" label="内容" min-width="180" show-overflow-tooltip />
      <el-table-column label="会员" min-width="140">
        <template #default="{ row }">{{ memberLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="时间" width="180">
        <template #default="{ row }">{{ row.created_at?.slice(0, 19).replace('T', ' ') }}</template>
      </el-table-column>
      <el-table-column label="操作" width="90">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
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

    <el-drawer v-model="detailVisible" title="通知详情" size="420px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="事件">{{ detail.event_type }}</el-descriptions-item>
          <el-descriptions-item label="标题">{{ detail.title }}</el-descriptions-item>
          <el-descriptions-item label="内容">{{ detail.body }}</el-descriptions-item>
          <el-descriptions-item label="会员">{{ memberLabel(detail) }}</el-descriptions-item>
          <el-descriptions-item label="时间">
            {{ detail.created_at?.slice(0, 19).replace('T', ' ') }}
          </el-descriptions-item>
        </el-descriptions>
      </template>
    </el-drawer>
  </div>
</template>

<style scoped>
.toolbar h3 {
  margin: 0 0 12px;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 12px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
