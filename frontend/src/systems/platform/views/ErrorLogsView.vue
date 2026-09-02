<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type ErrorEvent = {
  id: number
  request_id: string | null
  error_code: string
  status_code: number | null
  message: string
  exception_type: string | null
  stack_trace: string | null
  http_method: string | null
  request_path: string | null
  module: string | null
  actor_name: string | null
  merchant_name: string | null
  extra_json: Record<string, unknown> | null
  created_at: string
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const rows = ref<ErrorEvent[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const { merchantId } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})

const query = reactive({
  q: '',
  error_code: '',
  module: '',
  request_id: '',
})

const detailVisible = ref(false)
const detail = ref<ErrorEvent | null>(null)

function fmtTime(v: string) {
  return v.replace('T', ' ').slice(0, 19)
}

async function refresh() {
  loading.value = true
  try {
    const { data } = await http.get<Page<ErrorEvent>>('/ops/error-events', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        merchant_id: merchantId.value,
        q: query.q.trim() || undefined,
        error_code: query.error_code.trim() || undefined,
        module: query.module.trim() || undefined,
        request_id: query.request_id.trim() || undefined,
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
  void refresh()
}

function resetSearch() {
  query.q = ''
  query.error_code = ''
  query.module = ''
  query.request_id = ''
  page.value = 1
  void refresh()
}

function openDetail(row: ErrorEvent) {
  detail.value = row
  detailVisible.value = true
}

onMounted(refresh)
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <h3>错误日志</h3>
      <p class="hint">系统异常、支付通道失败与未捕获 500。业务拒单请看操作日志。</p>
    </div>
    <div class="filters">
      <el-input v-model="query.q" clearable placeholder="文案 / 路径 / 错误码" style="width: 200px" @keyup.enter="search" />
      <el-input v-model="query.error_code" clearable placeholder="错误码" style="width: 160px" @keyup.enter="search" />
      <el-input v-model="query.module" clearable placeholder="模块" style="width: 140px" @keyup.enter="search" />
      <el-input v-model="query.request_id" clearable placeholder="request_id" style="width: 220px" @keyup.enter="search" />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="rows" v-loading="loading" stripe @row-dblclick="openDetail">
      <el-table-column prop="id" label="ID" width="72" />
      <el-table-column label="时间" width="168">
        <template #default="{ row }">{{ fmtTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column prop="error_code" label="错误码" width="180" show-overflow-tooltip />
      <el-table-column prop="module" label="模块" width="110" show-overflow-tooltip />
      <el-table-column prop="message" label="摘要" min-width="220" show-overflow-tooltip />
      <el-table-column prop="request_path" label="路径" min-width="160" show-overflow-tooltip />
      <el-table-column prop="actor_name" label="操作人" width="100" show-overflow-tooltip />
      <el-table-column label="" width="72" fixed="right">
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
        layout="total, prev, pager, next, sizes"
        :page-sizes="[20, 50, 100]"
        @current-change="refresh"
        @size-change="() => { page = 1; refresh() }"
      />
    </div>

    <el-dialog v-model="detailVisible" title="错误详情" width="760px" destroy-on-close>
      <el-descriptions v-if="detail" :column="2" border>
        <el-descriptions-item label="时间" :span="2">{{ fmtTime(detail.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="错误码">{{ detail.error_code }}</el-descriptions-item>
        <el-descriptions-item label="HTTP">{{ detail.status_code ?? '—' }}</el-descriptions-item>
        <el-descriptions-item label="模块">{{ detail.module || '—' }}</el-descriptions-item>
        <el-descriptions-item label="商户">{{ detail.merchant_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="操作人">{{ detail.actor_name || '—' }}</el-descriptions-item>
        <el-descriptions-item label="异常类型">{{ detail.exception_type || '—' }}</el-descriptions-item>
        <el-descriptions-item label="路径" :span="2">
          {{ detail.http_method || '' }} {{ detail.request_path || '—' }}
        </el-descriptions-item>
        <el-descriptions-item label="request_id" :span="2">
          <code>{{ detail.request_id || '—' }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="摘要" :span="2">{{ detail.message }}</el-descriptions-item>
        <el-descriptions-item v-if="detail.extra_json" label="附加" :span="2">
          <pre class="json-box">{{ JSON.stringify(detail.extra_json, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item v-if="detail.stack_trace" label="堆栈" :span="2">
          <pre class="json-box">{{ detail.stack_trace }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar h3 {
  margin: 0 0 4px;
}
.hint {
  margin: 0 0 16px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
.json-box {
  margin: 0;
  max-height: 280px;
  overflow: auto;
  padding: 8px;
  background: var(--el-fill-color-light);
  border-radius: 6px;
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
