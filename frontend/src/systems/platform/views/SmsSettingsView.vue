<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'

type Settings = {
  provider: string
  api_base_url: string
  sign_name: string
  enabled: boolean
  api_key: { configured: boolean }
  api_secret: { configured: boolean }
}
type Template = {
  id: number
  code: string
  name: string
  content: string
  scene: string
  is_enabled: boolean
}

const loading = ref(false)
const saving = ref(false)
const templates = ref<Template[]>([])
const page = ref(1)
const pageSize = ref(20)
const tplQuery = reactive({ q: '', scene: '', is_enabled: '' as string })
const filteredTemplates = computed(() => {
  const kw = tplQuery.q.trim()
  return templates.value.filter((row) => {
    if (kw && !row.code.includes(kw) && !row.name.includes(kw) && !row.content.includes(kw)) return false
    if (tplQuery.scene && row.scene !== tplQuery.scene) return false
    if (tplQuery.is_enabled === '1' && !row.is_enabled) return false
    if (tplQuery.is_enabled === '0' && row.is_enabled) return false
    return true
  })
})
const pagedTemplates = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredTemplates.value.slice(start, start + pageSize.value)
})
const dialogVisible = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  provider: 'http',
  api_base_url: '',
  sign_name: '',
  enabled: false,
  api_key: '',
  api_secret: '',
})
const meta = reactive({ api_key: false, api_secret: false })
const tpl = reactive({
  code: '',
  name: '',
  content: '',
  scene: 'otp',
  is_enabled: true,
})

async function load() {
  loading.value = true
  try {
    const [s, t] = await Promise.all([http.get<Settings>('/site/sms/settings'), http.get<Template[]>('/site/sms/templates')])
    form.provider = s.data.provider
    form.api_base_url = s.data.api_base_url
    form.sign_name = s.data.sign_name
    form.enabled = s.data.enabled
    form.api_key = ''
    form.api_secret = ''
    meta.api_key = !!s.data.api_key?.configured
    meta.api_secret = !!s.data.api_secret?.configured
    templates.value = t.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function saveSettings() {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      provider: form.provider,
      api_base_url: form.api_base_url,
      sign_name: form.sign_name,
      enabled: form.enabled,
    }
    if (form.api_key) payload.api_key = form.api_key
    if (form.api_secret) payload.api_secret = form.api_secret
    await http.put('/site/sms/settings', payload)
    ElMessage.success('短信接口已保存')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

function openTpl(row?: Template) {
  editingId.value = row?.id ?? null
  tpl.code = row?.code || ''
  tpl.name = row?.name || ''
  tpl.content = row?.content || ''
  tpl.scene = row?.scene || 'otp'
  tpl.is_enabled = row?.is_enabled ?? true
  dialogVisible.value = true
}

async function saveTpl() {
  try {
    if (editingId.value) {
      await http.patch(`/site/sms/templates/${editingId.value}`, { ...tpl })
    } else {
      await http.post('/site/sms/templates', { ...tpl })
    }
    ElMessage.success('模版已保存')
    dialogVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  }
}

async function removeTpl(row: Template) {
  try {
    await ElMessageBox.confirm(`删除模版「${row.name}」？`, '确认', { type: 'warning' })
  } catch {
    return
  }
  await http.delete(`/site/sms/templates/${row.id}`)
  ElMessage.success('已删除')
  await load()
}

onMounted(load)
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar">
      <h3>短信配置</h3>
      <el-button type="primary" :loading="saving" @click="saveSettings">保存接口配置</el-button>
    </div>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
      title="配置短信 HTTP API 与签名；密钥仅写入不回显。模版用于验证码、开卡通知等场景。"
    />

    <h4>短信 API 接口</h4>
    <el-form label-width="140px" style="max-width: 720px">
      <el-form-item label="通道">
        <el-select v-model="form.provider" style="width: 240px">
          <el-option label="HTTP 网关" value="http" />
          <el-option label="阿里云" value="aliyun" />
          <el-option label="腾讯云" value="tencent" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用">
        <el-switch v-model="form.enabled" />
      </el-form-item>
      <el-form-item label="API 地址">
        <el-input v-model="form.api_base_url" placeholder="https://sms.example.com/send" />
      </el-form-item>
      <el-form-item :label="`API Key${meta.api_key ? '（已配置）' : ''}`">
        <el-input v-model="form.api_key" type="password" show-password placeholder="留空不修改" />
      </el-form-item>
      <el-form-item :label="`API Secret${meta.api_secret ? '（已配置）' : ''}`">
        <el-input v-model="form.api_secret" type="password" show-password placeholder="留空不修改" />
      </el-form-item>
      <el-form-item label="短信签名">
        <el-input v-model="form.sign_name" placeholder="如：观野SPACE" />
      </el-form-item>
    </el-form>

    <div class="toolbar" style="margin-top: 28px">
      <h4>短信模版管理</h4>
      <el-button type="primary" @click="openTpl()">新建模版</el-button>
    </div>
    <el-form inline class="filters">
      <el-form-item label="关键词">
        <el-input v-model="tplQuery.q" clearable placeholder="编码 / 名称 / 内容" style="width: 200px" @input="page = 1" />
      </el-form-item>
      <el-form-item label="场景">
        <el-select v-model="tplQuery.scene" clearable placeholder="全部" style="width: 130px" @change="page = 1">
          <el-option label="验证码" value="otp" />
          <el-option label="开卡通知" value="membership" />
          <el-option label="预约提醒" value="booking" />
          <el-option label="其他" value="other" />
        </el-select>
      </el-form-item>
      <el-form-item label="启用">
        <el-select v-model="tplQuery.is_enabled" clearable placeholder="全部" style="width: 110px" @change="page = 1">
          <el-option label="启用" value="1" />
          <el-option label="停用" value="0" />
        </el-select>
      </el-form-item>
    </el-form>
    <el-table :data="pagedTemplates" stripe>
      <el-table-column prop="code" label="编码" width="140" />
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="scene" label="场景" width="100" />
      <el-table-column prop="content" label="内容" min-width="240" />
      <el-table-column label="启用" width="80">
        <template #default="{ row }">{{ row.is_enabled ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button size="small" @click="openTpl(row)">编辑</el-button>
          <el-button size="small" @click="removeTpl(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="filteredTemplates.length"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑模版' : '新建模版'" width="520px">
      <el-form label-width="80px">
        <el-form-item label="编码">
          <el-input v-model="tpl.code" placeholder="如 otp_login" />
        </el-form-item>
        <el-form-item label="名称">
          <el-input v-model="tpl.name" />
        </el-form-item>
        <el-form-item label="场景">
          <el-select v-model="tpl.scene" style="width: 100%">
            <el-option label="验证码" value="otp" />
            <el-option label="开卡通知" value="membership" />
            <el-option label="预约提醒" value="booking" />
            <el-option label="其他" value="other" />
          </el-select>
        </el-form-item>
        <el-form-item label="内容">
          <el-input v-model="tpl.content" type="textarea" :rows="4" placeholder="您的验证码是 {code}，5 分钟内有效。" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="tpl.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTpl">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.toolbar h3,
.toolbar h4 {
  margin: 0;
}
h4 {
  margin: 0 0 12px;
}
.filters {
  margin-bottom: 4px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
