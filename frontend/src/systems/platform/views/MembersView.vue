<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { useAuthStore } from '../../../core/stores/auth'

type Member = {
  id: number
  phone: string
  name: string
  face_status: string
  merchant_ids: number[]
  acquisition_source?: string
  first_merchant_id?: number | null
  first_merchant_name?: string | null
  created_at?: string
}
type Merchant = { id: number; name: string }
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const auth = useAuthStore()
const canWrite = computed(
  () =>
    (auth.me?.permissions || []).includes('member:write') ||
    (auth.me?.permissions || []).includes('*'),
)

const members = ref<Member[]>([])
const merchants = ref<Merchant[]>([])
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ q: '' })

const createDialog = ref(false)
const linkDialog = ref(false)
const editDialog = ref(false)
const detailVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const linkFormRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()

const form = reactive({ phone: '', name: '', merchant_id: undefined as number | undefined })
const linkForm = reactive({ merchant_id: undefined as number | undefined })
const editForm = reactive({ name: '' })
const linkTarget = ref<Member | null>(null)
const editTarget = ref<Member | null>(null)
const detail = ref<Member | null>(null)

const rules: FormRules = {
  phone: [{ required: true, message: '请填写手机号', trigger: 'blur' }],
  name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
  merchant_id: [{ required: true, message: '请选择商户', trigger: 'change' }],
}

const linkRules: FormRules = {
  merchant_id: [{ required: true, message: '请选择目标商户', trigger: 'change' }],
}

const editRules: FormRules = {
  name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
}

function merchantName(id: number) {
  return merchants.value.find((m) => m.id === id)?.name || `#${id}`
}

function faceLabel(status: string) {
  return { enrolled: '已录入', not_enrolled: '未录入', pending: '待审核' }[status] || status
}

function sourceLabel(row: Member) {
  if (row.acquisition_source === 'merchant') {
    return row.first_merchant_name || merchantName(row.first_merchant_id || 0) || '商户获客'
  }
  return '综合运营平台'
}

async function load() {
  loading.value = true
  try {
    const [m, ms] = await Promise.all([
      http.get<Page<Member>>('/members', {
        params: { page: page.value, page_size: pageSize.value, q: query.q.trim() || undefined },
      }),
      http.get('/merchants'),
    ])
    members.value = m.data.items
    total.value = m.data.total
    merchants.value = ms.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void load()
}

function resetSearch() {
  query.q = ''
  page.value = 1
  void load()
}

function openCreate() {
  form.phone = ''
  form.name = ''
  form.merchant_id = merchants.value[0]?.id
  formRef.value?.clearValidate()
  createDialog.value = true
}

async function create() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/members', {
      phone: form.phone.trim(),
      name: form.name.trim(),
      merchant_id: form.merchant_id,
    })
    ElMessage.success('会员已创建')
    createDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openDetail(row: Member) {
  detail.value = row
  detailVisible.value = true
}

function openEdit(row: Member) {
  editTarget.value = row
  editForm.name = row.name
  editFormRef.value?.clearValidate()
  editDialog.value = true
}

async function saveEdit() {
  if (!editTarget.value) return
  const ok = await editFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    const { data } = await http.patch<Member>(`/members/${editTarget.value.id}`, {
      name: editForm.name.trim(),
    })
    ElMessage.success('已保存')
    editDialog.value = false
    if (detail.value?.id === data.id) detail.value = data
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

function openLink(row: Member) {
  linkTarget.value = row
  linkForm.merchant_id = merchants.value.find((m) => !row.merchant_ids.includes(m.id))?.id
  linkFormRef.value?.clearValidate()
  linkDialog.value = true
}

async function link() {
  if (!linkTarget.value) return
  const ok = await linkFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post(`/members/${linkTarget.value.id}/merchants`, { merchant_id: linkForm.merchant_id })
    ElMessage.success(`已关联到「${merchantName(linkForm.merchant_id!)}」`)
    linkDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '关联失败')
  } finally {
    submitting.value = false
  }
}

async function remove(row: Member) {
  try {
    await ElMessageBox.confirm(
      `确认删除会员「${row.name || row.phone || `#${row.id}`}」？删除后不可恢复。`,
      '删除会员',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await http.delete(`/members/${row.id}`)
    ElMessage.success('已删除')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>会员主档</h3>
      <el-button v-if="canWrite" type="primary" @click="openCreate">创建会员</el-button>
    </div>

    <div class="filters">
      <el-input
        v-model="query.q"
        clearable
        placeholder="手机号 / 姓名"
        style="width: 220px"
        @keyup.enter="search"
      />
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="members" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="phone" label="手机号" />
      <el-table-column prop="name" label="姓名" />
      <el-table-column label="人脸状态" width="120">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="row.face_status === 'enrolled' ? 'success' : row.face_status === 'pending' ? 'warning' : 'info'"
          >
            {{ faceLabel(row.face_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="首次来源" min-width="140">
        <template #default="{ row }">{{ sourceLabel(row) }}</template>
      </el-table-column>
      <el-table-column label="关联商户">
        <template #default="{ row }">
          <el-tag
            v-for="id in row.merchant_ids"
            :key="id"
            size="small"
            effect="plain"
            style="margin-right: 6px"
          >
            {{ merchantName(id) }}
          </el-tag>
          <span v-if="!row.merchant_ids.length">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button v-if="canWrite" link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="canWrite" link type="primary" @click="openLink(row)">关联商户</el-button>
          <el-button v-if="canWrite" link type="danger" @click="remove(row)">删除</el-button>
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

    <el-drawer v-model="detailVisible" title="会员详情" size="420px">
      <template v-if="detail">
        <el-descriptions :column="1" border>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="手机号">{{ detail.phone }}</el-descriptions-item>
          <el-descriptions-item label="姓名">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="人脸">{{ faceLabel(detail.face_status) }}</el-descriptions-item>
          <el-descriptions-item label="首次来源">{{ sourceLabel(detail) }}</el-descriptions-item>
          <el-descriptions-item label="关联商户">
            <template v-if="detail.merchant_ids.length">
              <el-tag
                v-for="id in detail.merchant_ids"
                :key="id"
                size="small"
                style="margin-right: 6px"
              >
                {{ merchantName(id) }}
              </el-tag>
            </template>
            <span v-else>—</span>
          </el-descriptions-item>
        </el-descriptions>
        <div v-if="canWrite" class="drawer-actions">
          <el-button type="primary" @click="openEdit(detail)">编辑</el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="createDialog" title="创建会员" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="会员手机号，必填" maxlength="32" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="会员姓名，必填" maxlength="128" />
        </el-form-item>
        <el-form-item label="商户" prop="merchant_id">
          <el-select v-model="form.merchant_id" style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editDialog" title="编辑会员" width="420px" destroy-on-close>
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="80px">
        <el-form-item label="姓名" prop="name">
          <el-input v-model="editForm.name" maxlength="128" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="linkDialog"
      :title="`关联商户 · ${linkTarget ? linkTarget.name || linkTarget.phone : ''}`"
      width="460px"
      destroy-on-close
    >
      <el-alert
        v-if="linkTarget"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 14px"
        title="关联后该会员可访问对应商户的权益与门禁授权"
      />
      <el-form ref="linkFormRef" :model="linkForm" :rules="linkRules" label-width="80px">
        <el-form-item label="目标商户" prop="merchant_id">
          <el-select v-model="linkForm.merchant_id" style="width: 100%" placeholder="请选择要关联到的商户">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="linkDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="link">确认关联</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.toolbar h3 {
  margin: 0;
  font-size: 1.1rem;
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
.drawer-actions {
  margin-top: 16px;
}
</style>
