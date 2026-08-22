<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'

type PromptTemplate = {
  id: number
  code: string
  name: string
  category: string
  data_source: string
  system_prompt: string
  user_prompt_template: string
  description: string | null
  is_builtin: boolean
  is_active: boolean
  sort_order: number
}

type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const DATA_SOURCES = [
  { value: 'operations', label: '综合运营' },
  { value: 'audit_logs', label: '操作日志' },
  { value: 'members', label: '会员' },
  { value: 'orders', label: '订单' },
  { value: 'promotion', label: '推广' },
  { value: 'access', label: '门禁' },
  { value: 'membership', label: '会籍' },
  { value: 'catering', label: '餐饮' },
]

const rows = ref<PromptTemplate[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()

const query = reactive({
  q: '',
  category: '',
  data_source: '',
  is_active: '' as '' | 'true' | 'false',
  is_builtin: '' as '' | 'true' | 'false',
})

const form = reactive({
  code: '',
  name: '',
  category: '自定义',
  data_source: 'operations',
  system_prompt: '',
  user_prompt_template: '请分析以下数据：\n\n{{data}}',
  description: '',
  is_active: true,
  sort_order: 100,
})

const rules: FormRules = {
  code: [{ required: true, message: '请填写编码', trigger: 'blur' }],
  name: [{ required: true, message: '请填写名称', trigger: 'blur' }],
  system_prompt: [{ required: true, message: '请填写系统提示词', trigger: 'blur' }],
  user_prompt_template: [{ required: true, message: '请填写用户提示词模版', trigger: 'blur' }],
}

const categoryOptions = computed(() => {
  const set = new Set(rows.value.map((r) => r.category).filter(Boolean))
  return Array.from(set).sort()
})

const isBuiltinEdit = computed(() => {
  if (!editingId.value) return false
  return rows.value.find((r) => r.id === editingId.value)?.is_builtin ?? false
})

function dataSourceLabel(v: string) {
  return DATA_SOURCES.find((d) => d.value === v)?.label || v
}

function boolParam(v: '' | 'true' | 'false'): boolean | undefined {
  if (v === 'true') return true
  if (v === 'false') return false
  return undefined
}

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<Page<PromptTemplate>>('/ai/prompt-templates', {
      params: {
        page: page.value,
        page_size: pageSize.value,
        q: query.q.trim() || undefined,
        category: query.category.trim() || undefined,
        data_source: query.data_source || undefined,
        is_active: boolParam(query.is_active),
        is_builtin: boolParam(query.is_builtin),
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
  void load()
}

function openDialog(row?: PromptTemplate) {
  editingId.value = row?.id ?? null
  form.code = row?.code || ''
  form.name = row?.name || ''
  form.category = row?.category || '自定义'
  form.data_source = row?.data_source || 'operations'
  form.system_prompt = row?.system_prompt || ''
  form.user_prompt_template = row?.user_prompt_template || '请分析以下数据：\n\n{{data}}'
  form.description = row?.description || ''
  form.is_active = row?.is_active ?? true
  form.sort_order = row?.sort_order ?? 100
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    const payload = {
      name: form.name.trim(),
      category: form.category.trim(),
      data_source: form.data_source,
      system_prompt: form.system_prompt.trim(),
      user_prompt_template: form.user_prompt_template.trim(),
      description: form.description.trim() || null,
      is_active: form.is_active,
      sort_order: form.sort_order,
    }
    if (editingId.value) {
      await http.patch(`/ai/prompt-templates/${editingId.value}`, payload)
      ElMessage.success('已更新')
    } else {
      await http.post('/ai/prompt-templates', { ...payload, code: form.code.trim() })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function remove(row: PromptTemplate) {
  if (row.is_builtin) {
    ElMessage.warning('内置模版不可删除，可停用')
    return
  }
  try {
    await http.delete(`/ai/prompt-templates/${row.id}`)
    ElMessage.success('已删除')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>提示词模版管理</h2>
        <p class="hint">
          支持占位符：<span v-pre>{{data}}</span>、<span v-pre>{{date_from}}</span>、<span v-pre>{{date_to}}</span>、<span v-pre>{{merchant_name}}</span>
        </p>
      </div>
      <el-button type="primary" @click="openDialog()">新建模版</el-button>
    </div>

    <el-form inline class="filters" @submit.prevent="onSearch">
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="名称/编码/分类/说明" style="width: 200px" />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="query.category" clearable filterable allow-create placeholder="全部" style="width: 130px">
          <el-option v-for="c in categoryOptions" :key="c" :label="c" :value="c" />
        </el-select>
      </el-form-item>
      <el-form-item label="数据源">
        <el-select v-model="query.data_source" clearable placeholder="全部" style="width: 120px">
          <el-option v-for="d in DATA_SOURCES" :key="d.value" :label="d.label" :value="d.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="query.is_builtin" clearable placeholder="全部" style="width: 100px">
          <el-option label="内置" value="true" />
          <el-option label="自定义" value="false" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.is_active" clearable placeholder="全部" style="width: 100px">
          <el-option label="启用" value="true" />
          <el-option label="停用" value="false" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSearch">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="sort_order" label="排序" width="70" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column label="数据源" width="110">
        <template #default="{ row }">{{ dataSourceLabel(row.data_source) }}</template>
      </el-table-column>
      <el-table-column prop="description" label="说明" min-width="180" show-overflow-tooltip />
      <el-table-column label="类型" width="80">
        <template #default="{ row }">
          <el-tag v-if="row.is_builtin" size="small">内置</el-tag>
          <el-tag v-else size="small" type="info">自定义</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button v-if="!row.is_builtin" link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        :total="total"
        @current-change="load"
        @size-change="() => { page = 1; load() }"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑模版' : '新建模版'" width="720px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="110px">
        <el-form-item v-if="!editingId" label="编码" prop="code">
          <el-input v-model="form.code" placeholder="唯一编码，如 my_report" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="分类">
          <el-input v-model="form.category" />
        </el-form-item>
        <el-form-item label="数据源">
          <el-select v-model="form.data_source" style="width: 100%">
            <el-option v-for="d in DATA_SOURCES" :key="d.value" :label="d.label" :value="d.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="系统提示词" prop="system_prompt">
          <el-input v-model="form.system_prompt" type="textarea" :rows="5" />
        </el-form-item>
        <el-form-item label="用户提示词" prop="user_prompt_template">
          <el-input v-model="form.user_prompt_template" type="textarea" :rows="8" />
        </el-form-item>
        <el-alert v-if="isBuiltinEdit" type="info" :closable="false" title="内置模版仅可修改内容与启用状态，不可删除" />
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">保存</el-button>
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
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
