<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string }
type Scene = { code: string; name: string }
type Agreement = {
  id: number
  merchant_id: number
  merchant_name: string | null
  scene: string
  title: string
  content: string
  is_enabled: boolean
  updated_at: string | null
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const scenes = ref<Scene[]>([])
const rows = ref<Agreement[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const query = reactive({ scene: '' })
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void loadList()
})
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  merchant_id: undefined as number | undefined,
  scene: 'membership',
  title: '',
  content: '',
  is_enabled: true,
})
const rules: FormRules = {
  merchant_id: [{ required: true, message: '请选择商户', trigger: 'change' }],
  scene: [{ required: true, message: '请选择场景', trigger: 'change' }],
  title: [{ required: true, message: '请填写标题', trigger: 'blur' }],
  content: [{ required: true, message: '请填写正文', trigger: 'blur' }],
}

function sceneName(code: string) {
  return scenes.value.find((s) => s.code === code)?.name || code
}

async function loadMeta() {
  const [{ data: merchantList }, { data: sceneList }] = await Promise.all([
    http.get<Merchant[]>('/merchants'),
    http.get<Scene[]>('/agreements/scenes'),
  ])
  merchants.value = merchantList
  scenes.value = sceneList
}

async function loadList() {
  loading.value = true
  try {
    const { data } = await http.get<Page<Agreement>>('/agreements', {
      params: {
        merchant_id: merchantId.value,
        scene: query.scene || undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    rows.value = data.items
    total.value = data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
    rows.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function refresh() {
  await loadMeta()
  await loadList()
}

function search() {
  page.value = 1
  void loadList()
}

function openCreate() {
  const mid = requireMerchant('请先选择商户后再新建协议')
  if (!mid) return
  editingId.value = null
  form.merchant_id = mid
  form.scene = query.scene || 'membership'
  form.title = ''
  form.content = ''
  form.is_enabled = true
  dialogVisible.value = true
}

function openEdit(row: Agreement) {
  editingId.value = row.id
  form.merchant_id = row.merchant_id
  form.scene = row.scene
  form.title = row.title
  form.content = row.content
  form.is_enabled = row.is_enabled
  dialogVisible.value = true
}

async function save() {
  await formRef.value?.validate()
  submitting.value = true
  try {
    if (editingId.value) {
      await http.patch(`/agreements/${editingId.value}`, {
        title: form.title.trim(),
        content: form.content.trim(),
        is_enabled: form.is_enabled,
      })
      ElMessage.success('已保存')
    } else {
      await http.post('/agreements', {
        merchant_id: form.merchant_id,
        scene: form.scene,
        title: form.title.trim(),
        content: form.content.trim(),
        is_enabled: form.is_enabled,
      })
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await loadList()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function toggleEnabled(row: Agreement) {
  try {
    await http.patch(`/agreements/${row.id}`, { is_enabled: !row.is_enabled })
    ElMessage.success(row.is_enabled ? '已停用，会员端将无法购买' : '已启用')
    await loadList()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>协议管理</h3>
        <p class="hint">按商户和场景各维护一份。会员购买会籍、私教、报名活动或点餐前必须勾选已启用的协议。</p>
      </div>
      <el-button type="primary" @click="openCreate">新建协议</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="search">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="场景">
        <el-select v-model="query.scene" clearable placeholder="全部" style="width: 140px" @change="search">
          <el-option v-for="s in scenes" :key="s.code" :label="s.name" :value="s.code" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="rows" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="商户" min-width="140">
        <template #default="{ row }">{{ row.merchant_name || merchants.find((m) => m.id === row.merchant_id)?.name || row.merchant_id }}</template>
      </el-table-column>
      <el-table-column label="场景" width="120">
        <template #default="{ row }">{{ sceneName(row.scene) }}</template>
      </el-table-column>
      <el-table-column prop="title" label="标题" min-width="180" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_enabled ? 'success' : 'info'" size="small">{{ row.is_enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="180">
        <template #default="{ row }">{{ row.updated_at ? row.updated_at.replace('T', ' ').slice(0, 19) : '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link :type="row.is_enabled ? 'warning' : 'success'" @click="toggleEnabled(row)">
            {{ row.is_enabled ? '停用' : '启用' }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="loadList"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑协议' : '新建协议'" width="640px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="88px">
        <el-form-item label="商户" prop="merchant_id">
          <el-select v-model="form.merchant_id" :disabled="!!editingId" style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="场景" prop="scene">
          <el-select v-model="form.scene" :disabled="!!editingId" style="width: 100%">
            <el-option v-for="s in scenes" :key="s.code" :label="s.name" :value="s.code" />
          </el-select>
        </el-form-item>
        <el-form-item label="标题" prop="title">
          <el-input v-model="form.title" maxlength="128" show-word-limit />
        </el-form-item>
        <el-form-item label="正文" prop="content">
          <el-input v-model="form.content" type="textarea" :rows="12" placeholder="会员购买时将展示全文，可粘贴简单 HTML" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.is_enabled" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">{{ editingId ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.toolbar h3 {
  margin: 0;
}
.hint {
  margin: 6px 0 0;
  color: var(--admin-ink-muted, var(--el-text-color-secondary));
  font-size: 13px;
}
.filters {
  margin-bottom: 4px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
</style>
