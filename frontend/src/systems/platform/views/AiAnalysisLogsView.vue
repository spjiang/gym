<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import MarkdownView from '../../../core/components/MarkdownView.vue'

type AnalysisRecord = {
  id: number
  template_id: number
  llm_account_id: number
  merchant_id: number | null
  staff_id: number | null
  status: string
  input_summary: string | null
  result_text: string | null
  error_message: string | null
  created_at: string
  template_name: string | null
  llm_account_name: string | null
  merchant_name: string | null
  staff_name: string | null
}

type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const rows = ref<AnalysisRecord[]>([])
const loading = ref(false)
const exporting = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)

const monthStart = `${new Date().toISOString().slice(0, 8)}01`
const today = new Date().toISOString().slice(0, 10)
const query = reactive({
  q: '',
  status: '',
  date_from: monthStart,
  date_to: today,
})

const detailVisible = ref(false)
const detail = ref<AnalysisRecord | null>(null)

async function refresh() {
  loading.value = true
  try {
    const { data } = await http.get<Page<AnalysisRecord>>('/ai/analysis-records', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        q: query.q.trim() || undefined,
        status: query.status || undefined,
        date_from: query.date_from || undefined,
        date_to: query.date_to || undefined,
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

function onSearch() {
  page.value = 1
  void refresh()
}

async function openDetail(row: AnalysisRecord) {
  try {
    const { data } = await http.get<AnalysisRecord>(`/ai/analysis-records/${row.id}`)
    detail.value = data
    detailVisible.value = true
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载详情失败')
  }
}

async function downloadRecord(row: AnalysisRecord) {
  try {
    const resp = await http.get(`/ai/analysis-records/${row.id}/download`, { responseType: 'blob' })
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai-analysis-${row.id}.md`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '下载失败')
  }
}

async function exportCsv() {
  exporting.value = true
  try {
    const resp = await http.get('/ai/analysis-records/export', {
      params: {
        q: query.q.trim() || undefined,
        status: query.status || undefined,
        date_from: query.date_from || undefined,
        date_to: query.date_to || undefined,
      },
      responseType: 'blob',
    })
    const url = URL.createObjectURL(resp.data)
    const a = document.createElement('a')
    a.href = url
    a.download = `ai-analysis-logs-${query.date_from}-${query.date_to}.csv`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导出失败')
  } finally {
    exporting.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>分析日志</h2>
        <p class="hint">查看历史 AI 分析记录，支持下载单条 Markdown 报告或导出 CSV 清单。</p>
      </div>
      <el-button :loading="exporting" @click="exportCsv">导出 CSV</el-button>
    </div>

    <el-form inline class="filters" @submit.prevent="onSearch">
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="摘要/错误信息" style="width: 180px" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="成功" value="success" />
          <el-option label="失败" value="failure" />
          <el-option label="进行中" value="running" />
        </el-select>
      </el-form-item>
      <el-form-item label="日期">
        <el-date-picker v-model="query.date_from" type="date" value-format="YYYY-MM-DD" style="width: 140px" />
        <span class="sep">~</span>
        <el-date-picker v-model="query.date_to" type="date" value-format="YYYY-MM-DD" style="width: 140px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSearch">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="input_summary" label="摘要" min-width="220" show-overflow-tooltip />
      <el-table-column prop="template_name" label="模版" width="140" show-overflow-tooltip />
      <el-table-column prop="llm_account_name" label="大模型" width="120" show-overflow-tooltip />
      <el-table-column prop="merchant_name" label="范围" width="100" show-overflow-tooltip />
      <el-table-column prop="staff_name" label="操作人" width="100" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.status === 'success' ? 'success' : row.status === 'failure' ? 'danger' : 'info'" size="small">
            {{ row.status === 'success' ? '成功' : row.status === 'failure' ? '失败' : row.status }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="时间" width="170" />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button link type="primary" :disabled="row.status !== 'success'" @click="downloadRecord(row)">下载</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        layout="total, prev, pager, next"
        :total="total"
        @current-change="refresh"
        @size-change="() => { page = 1; refresh() }"
      />
    </div>

    <el-dialog v-model="detailVisible" title="分析详情" width="760px" destroy-on-close>
      <template v-if="detail">
        <el-descriptions :column="2" border size="small" class="meta">
          <el-descriptions-item label="摘要" :span="2">{{ detail.input_summary || '-' }}</el-descriptions-item>
          <el-descriptions-item label="模版">{{ detail.template_name || detail.template_id }}</el-descriptions-item>
          <el-descriptions-item label="大模型">{{ detail.llm_account_name || detail.llm_account_id }}</el-descriptions-item>
          <el-descriptions-item label="范围">{{ detail.merchant_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="操作人">{{ detail.staff_name || '-' }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.status }}</el-descriptions-item>
          <el-descriptions-item label="时间">{{ detail.created_at }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="detail.error_message" class="error">{{ detail.error_message }}</div>
        <div v-else-if="detail.result_text" class="result-wrap">
          <MarkdownView :content="detail.result_text" />
        </div>
        <div v-else class="empty">无内容</div>
      </template>
      <template #footer>
        <el-button v-if="detail?.status === 'success'" type="primary" @click="detail && downloadRecord(detail)">下载报告</el-button>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.page-head h2 {
  margin: 0 0 4px;
}
.hint {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.filters {
  margin-bottom: 12px;
}
.sep {
  margin: 0 6px;
  color: var(--el-text-color-secondary);
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
.meta {
  margin-bottom: 12px;
}
.result-wrap {
  max-height: 420px;
  overflow: auto;
}
.error {
  color: var(--el-color-danger);
  padding: 12px;
  background: var(--el-color-danger-light-9);
  border-radius: 8px;
}
.empty {
  color: var(--el-text-color-secondary);
  padding: 24px;
  text-align: center;
}
</style>
