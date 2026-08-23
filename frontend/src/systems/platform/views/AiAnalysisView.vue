<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'
import MarkdownView from '../../../core/components/MarkdownView.vue'
import { useAuthStore } from '../../../core/stores/auth'

type PromptTemplate = {
  id: number
  name: string
  category: string
  data_source: string
  description: string | null
}

type LlmAccount = {
  id: number
  name: string
  model_name: string
  is_default: boolean
  has_api_key: boolean
}

type Merchant = { id: number; name: string }

type AnalysisRecord = {
  id: number
  template_id: number
  input_summary: string | null
  result_text: string | null
  status: string
  created_at: string
}

const auth = useAuthStore()
const isSiteWide = computed(() => auth.me?.role_codes?.includes('site_admin') || auth.me?.permissions?.includes('*'))

const templates = ref<PromptTemplate[]>([])
const accounts = ref<LlmAccount[]>([])
const merchants = ref<Merchant[]>([])
const history = ref<AnalysisRecord[]>([])
const loading = ref(false)
const analyzing = ref(false)
const resultText = ref('')

const today = new Date().toISOString().slice(0, 10)
const monthStart = `${today.slice(0, 8)}01`

const form = reactive({
  template_id: undefined as number | undefined,
  llm_account_id: undefined as number | undefined,
  merchant_id: undefined as number | undefined,
  date_from: monthStart,
  date_to: today,
  extra_instruction: '',
})

const selectedTemplate = computed(() => templates.value.find((t) => t.id === form.template_id))

async function loadOptions() {
  loading.value = true
  try {
    const [tplRes, accRes, histRes] = await Promise.all([
      http.get<{ items: PromptTemplate[] }>('/ai/prompt-templates', {
        params: { active_only: true, page_size: 100 },
      }),
      http.get<LlmAccount[]>('/ai/llm-accounts', { params: { active_only: true } }),
      http.get<{ items: AnalysisRecord[] }>('/ai/analysis-records', { params: { page_size: 10 } }),
    ])
    templates.value = tplRes.data.items
    accounts.value = accRes.data.filter((a) => a.has_api_key)
    history.value = histRes.data.items
    if (!form.template_id && templates.value[0]) form.template_id = templates.value[0].id
    const def = accounts.value.find((a) => a.is_default) || accounts.value[0]
    if (!form.llm_account_id && def) form.llm_account_id = def.id
    if (isSiteWide.value) {
      const { data } = await http.get<Merchant[]>('/merchants')
      merchants.value = data
    }
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载配置失败')
  } finally {
    loading.value = false
  }
}

async function analyze() {
  if (!form.template_id) {
    ElMessage.warning('请选择提示词模版')
    return
  }
  if (!form.llm_account_id) {
    ElMessage.warning('请选择大模型账号')
    return
  }
  analyzing.value = true
  resultText.value = ''
  try {
    const { data } = await http.post<{ result_text: string; input_summary: string }>(
      '/ai/analyze',
      {
        template_id: form.template_id,
        llm_account_id: form.llm_account_id,
        merchant_id: form.merchant_id ?? null,
        date_from: form.date_from,
        date_to: form.date_to,
        extra_instruction: form.extra_instruction.trim() || null,
      },
      { timeout: 180000 },
    )
    resultText.value = data.result_text
    ElMessage.success('分析完成')
    const hist = await http.get<{ items: AnalysisRecord[] }>('/ai/analysis-records', { params: { page_size: 10 } })
    history.value = hist.data.items
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '分析失败')
  } finally {
    analyzing.value = false
  }
}

async function loadRecord(row: AnalysisRecord) {
  if (row.result_text) {
    resultText.value = row.result_text
    return
  }
  try {
    const { data } = await http.get<AnalysisRecord>(`/ai/analysis-records/${row.id}`)
    resultText.value = data.result_text || ''
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载记录失败')
  }
}

onMounted(loadOptions)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <h2>AI 分析</h2>
      <p class="hint">选择提示词模版与大模型账号，系统将自动拉取对应业务数据并生成分析报告。</p>
    </div>

    <el-row :gutter="16">
      <el-col :span="10">
        <el-card shadow="never" v-loading="loading">
          <template #header>分析配置</template>
          <el-form label-width="110px">
            <el-form-item label="提示词模版" required>
              <el-select v-model="form.template_id" placeholder="选择模版" style="width: 100%" filterable>
                <el-option
                  v-for="t in templates"
                  :key="t.id"
                  :label="`${t.name}（${t.category}）`"
                  :value="t.id"
                />
              </el-select>
            </el-form-item>
            <el-form-item v-if="selectedTemplate?.description" label="模版说明">
              <span class="desc">{{ selectedTemplate.description }}</span>
            </el-form-item>
            <el-form-item label="大模型账号" required>
              <el-select v-model="form.llm_account_id" placeholder="选择大模型" style="width: 100%">
                <el-option
                  v-for="a in accounts"
                  :key="a.id"
                  :label="`${a.name} · ${a.model_name}`"
                  :value="a.id"
                />
              </el-select>
              <p v-if="!accounts.length" class="warn">请先在「大模型管理」中添加并配置 API Key</p>
            </el-form-item>
            <el-form-item v-if="isSiteWide" label="分析范围">
              <el-select v-model="form.merchant_id" clearable placeholder="全场地" style="width: 100%">
                <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="日期范围">
              <el-date-picker
                v-model="form.date_from"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="开始"
                style="width: 48%"
              />
              <span class="sep">~</span>
              <el-date-picker
                v-model="form.date_to"
                type="date"
                value-format="YYYY-MM-DD"
                placeholder="结束"
                style="width: 48%"
              />
            </el-form-item>
            <el-form-item label="补充要求">
              <el-input v-model="form.extra_instruction" type="textarea" :rows="3" placeholder="可选，追加给模型的额外指令" />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" :loading="analyzing" :disabled="!accounts.length" @click="analyze">
                开始分析
              </el-button>
            </el-form-item>
          </el-form>
        </el-card>

        <el-card v-if="history.length" shadow="never" class="history-card">
          <template #header>最近分析</template>
          <el-table :data="history" size="small" @row-click="loadRecord">
            <el-table-column prop="input_summary" label="摘要" min-width="160" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="70">
              <template #default="{ row }">
                <el-tag :type="row.status === 'success' ? 'success' : 'danger'" size="small">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="created_at" label="时间" width="160" />
          </el-table>
        </el-card>
      </el-col>

      <el-col :span="14">
        <el-card shadow="never" class="result-card">
          <template #header>分析结果</template>
          <div v-if="!resultText && !analyzing" class="empty">配置完成后点击「开始分析」</div>
          <div v-else-if="analyzing" class="empty">正在调用大模型，请稍候…</div>
          <div v-else class="result-wrap">
            <MarkdownView :content="resultText" />
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.page-head h2 {
  margin: 0 0 4px;
}
.hint {
  margin: 0 0 16px;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.desc {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}
.warn {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-color-warning);
}
.sep {
  display: inline-block;
  width: 4%;
  text-align: center;
}
.history-card {
  margin-top: 16px;
}
.result-card {
  min-height: 480px;
}
.empty {
  color: var(--el-text-color-secondary);
  padding: 48px 0;
  text-align: center;
}
.result-wrap {
  max-height: calc(100vh - 220px);
  overflow: auto;
  padding: 4px 2px;
}
</style>
