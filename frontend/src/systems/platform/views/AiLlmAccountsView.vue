<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'

type LlmAccount = {
  id: number
  name: string
  provider: string
  base_url: string
  model_name: string
  has_api_key: boolean
  is_default: boolean
  is_active: boolean
  remark: string | null
}

const PROVIDER_PRESETS: Record<string, { label: string; base_url: string }> = {
  openai: { label: 'OpenAI', base_url: 'https://api.openai.com/v1' },
  deepseek: { label: 'DeepSeek', base_url: 'https://api.deepseek.com/v1' },
  qwen: { label: '通义千问', base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1' },
  zhipu: { label: '智谱 AI', base_url: 'https://openai.zhipuai.cn/api/paas/v4' },
  custom: { label: '自定义', base_url: '' },
}

const rows = ref<LlmAccount[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  provider: 'deepseek',
  base_url: PROVIDER_PRESETS.deepseek.base_url,
  api_key: '',
  model_name: 'deepseek-chat',
  is_default: false,
  is_active: true,
  remark: '',
})

const rules: FormRules = {
  name: [{ required: true, message: '请填写账号名称', trigger: 'blur' }],
  base_url: [{ required: true, message: '请填写 API 地址', trigger: 'blur' }],
  model_name: [{ required: true, message: '请填写模型名称', trigger: 'blur' }],
}

watch(
  () => form.provider,
  (p) => {
    const preset = PROVIDER_PRESETS[p]
    if (preset?.base_url && !editingId.value) {
      form.base_url = preset.base_url
    }
  },
)

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<LlmAccount[]>('/ai/llm-accounts')
    rows.value = data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openDialog(row?: LlmAccount) {
  editingId.value = row?.id ?? null
  form.name = row?.name || ''
  const provider = row?.provider
  form.provider = provider && provider in PROVIDER_PRESETS ? provider : 'custom'
  form.base_url = row?.base_url || PROVIDER_PRESETS.deepseek.base_url
  form.api_key = ''
  form.model_name = row?.model_name || 'deepseek-chat'
  form.is_default = row?.is_default ?? false
  form.is_active = row?.is_active ?? true
  form.remark = row?.remark || ''
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      provider: form.provider,
      base_url: form.base_url.trim(),
      model_name: form.model_name.trim(),
      is_default: form.is_default,
      is_active: form.is_active,
      remark: form.remark.trim() || null,
    }
    if (form.api_key.trim()) payload.api_key = form.api_key.trim()
    if (editingId.value) {
      await http.patch(`/ai/llm-accounts/${editingId.value}`, payload)
      ElMessage.success('已更新')
    } else {
      if (!form.api_key.trim()) {
        ElMessage.error('新建账号请填写 API Key')
        return
      }
      await http.post('/ai/llm-accounts', payload)
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

async function remove(row: LlmAccount) {
  try {
    await http.delete(`/ai/llm-accounts/${row.id}`)
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
        <h2>大模型管理</h2>
        <p class="hint">配置 OpenAI 兼容接口的 Base URL、API Key 与模型名；密钥加密存储。</p>
      </div>
      <el-button type="primary" @click="openDialog()">添加大模型</el-button>
    </div>

    <el-table v-loading="loading" :data="rows" stripe>
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column prop="provider" label="提供商" width="100" />
      <el-table-column prop="model_name" label="模型" min-width="140" />
      <el-table-column prop="base_url" label="API 地址" min-width="200" show-overflow-tooltip />
      <el-table-column label="密钥" width="80">
        <template #default="{ row }">
          <el-tag :type="row.has_api_key ? 'success' : 'danger'" size="small">{{ row.has_api_key ? '已配置' : '未配置' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="默认" width="70">
        <template #default="{ row }">
          <el-tag v-if="row.is_default" type="warning" size="small">默认</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="remark" label="备注" min-width="120" show-overflow-tooltip />
      <el-table-column label="操作" width="140" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDialog(row)">编辑</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑大模型' : '添加大模型'" width="560px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：DeepSeek 生产" />
        </el-form-item>
        <el-form-item label="提供商">
          <el-select v-model="form.provider" style="width: 100%">
            <el-option v-for="(p, key) in PROVIDER_PRESETS" :key="key" :label="p.label" :value="key" />
          </el-select>
        </el-form-item>
        <el-form-item label="API 地址" prop="base_url">
          <el-input v-model="form.base_url" placeholder="https://api.example.com/v1" />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" show-password :placeholder="editingId ? '留空则不修改' : '必填'" />
        </el-form-item>
        <el-form-item label="模型名称" prop="model_name">
          <el-input v-model="form.model_name" placeholder="如 gpt-4o-mini / deepseek-chat" />
        </el-form-item>
        <el-form-item label="设为默认">
          <el-switch v-model="form.is_default" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
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
</style>
