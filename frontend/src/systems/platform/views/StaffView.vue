<script setup lang="ts">
import { onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'

type Staff = {
  id: number
  username: string
  display_name: string
  merchant_id: number | null
  role_codes: string[]
  is_active: boolean
}
type Merchant = { id: number; name: string }
type RoleOpt = { id: number; code: string; name: string; merchant_id: number | null }

const staff = ref<Staff[]>([])
const merchants = ref<Merchant[]>([])
const roleOptions = ref<RoleOpt[]>([])
const dialogVisible = ref(false)
const editVisible = ref(false)
const editing = ref<Staff | null>(null)
const submitting = ref(false)
const loading = ref(false)
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ q: '', merchant_id: undefined as number | undefined, status: '' as '' | 'active' | 'inactive' })
const formRef = ref<FormInstance>()
const form = reactive({
  username: '',
  password: '',
  display_name: '',
  merchant_id: undefined as number | undefined,
  role_codes: [] as string[],
})
const editForm = reactive({
  display_name: '',
  password: '',
  merchant_id: undefined as number | undefined,
  role_codes: [] as string[],
})
const pwdVisible = ref(false)
const pwdTarget = ref<Staff | null>(null)
const pwdFormRef = ref<FormInstance>()
const pwdForm = reactive({ password: '', confirm: '' })
const pwdRules: FormRules = {
  password: [
    { required: true, message: '请填写新密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, callback) => {
        if (value !== pwdForm.password) callback(new Error('两次输入的密码不一致'))
        else callback()
      },
      trigger: 'blur',
    },
  ],
}

const rules: FormRules = {
  username: [{ required: true, message: '请填写用户名', trigger: 'blur' }],
  password: [
    { required: true, message: '请填写密码', trigger: 'blur' },
    { min: 6, message: '密码至少 6 位', trigger: 'blur' },
  ],
  display_name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
  role_codes: [{ required: true, message: '请选择角色', trigger: 'change' }],
}

function merchantName(id: number | null) {
  return merchants.value.find((m) => m.id === id)?.name || (id == null ? '—' : `#${id}`)
}

function roleLabel(code: string) {
  return roleOptions.value.find((o) => o.code === code)?.name || code
}

async function loadAssignable(merchantId?: number | null) {
  const { data } = await http.get('/rbac/roles/assignable', {
    params: { merchant_id: merchantId || undefined },
  })
  roleOptions.value = data
}

async function load() {
  loading.value = true
  try {
    const [s, m] = await Promise.all([
      http.get('/staff', {
        params: {
          page: page.value,
          page_size: pageSize.value,
          q: query.q.trim() || undefined,
          merchant_id: query.merchant_id,
          is_active: query.status === 'active' ? true : query.status === 'inactive' ? false : undefined,
        },
      }),
      http.get('/merchants'),
    ])
    staff.value = s.data.items
    total.value = s.data.total
    merchants.value = m.data
    await loadAssignable(merchants.value[0]?.id)
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
  query.merchant_id = undefined
  query.status = ''
  page.value = 1
  void load()
}

function openDialog() {
  form.username = ''
  form.password = ''
  form.display_name = ''
  form.merchant_id = merchants.value[0]?.id
  form.role_codes = roleOptions.value[0] ? [roleOptions.value[0].code] : []
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

watch(
  () => form.merchant_id,
  async (id) => {
    if (!dialogVisible.value) return
    await loadAssignable(id)
    if (!form.role_codes.some((c) => roleOptions.value.some((o) => o.code === c))) {
      form.role_codes = roleOptions.value[0] ? [roleOptions.value[0].code] : []
    }
  },
)

async function create() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/staff', {
      username: form.username.trim(),
      password: form.password,
      display_name: form.display_name.trim(),
      merchant_id: form.merchant_id ?? null,
      role_codes: form.role_codes,
    })
    ElMessage.success('员工已创建')
    dialogVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openEdit(row: Staff) {
  editing.value = row
  editForm.display_name = row.display_name
  editForm.password = ''
  editForm.merchant_id = row.merchant_id ?? undefined
  editForm.role_codes = [...row.role_codes]
  void loadAssignable(row.merchant_id)
  editVisible.value = true
}

async function saveEdit() {
  if (!editing.value) return
  submitting.value = true
  try {
    const payload: Record<string, unknown> = {
      display_name: editForm.display_name.trim(),
      merchant_id: editForm.merchant_id ?? null,
      role_codes: editForm.role_codes,
    }
    if (editForm.password) payload.password = editForm.password
    await http.patch(`/staff/${editing.value.id}`, payload)
    ElMessage.success('员工已更新')
    editVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '更新失败')
  } finally {
    submitting.value = false
  }
}

async function toggleActive(row: Staff) {
  try {
    await http.patch(`/staff/${row.id}`, { is_active: !row.is_active })
    ElMessage.success(row.is_active ? '已禁用' : '已启用')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '更新失败')
  }
}

function openResetPwd(row: Staff) {
  pwdTarget.value = row
  pwdForm.password = ''
  pwdForm.confirm = ''
  pwdFormRef.value?.clearValidate()
  pwdVisible.value = true
}

async function saveResetPwd() {
  if (!pwdTarget.value) return
  const ok = await pwdFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post(`/staff/${pwdTarget.value.id}/password`, { password: pwdForm.password })
    ElMessage.success(`已重置「${pwdTarget.value.display_name || pwdTarget.value.username}」的登录密码`)
    pwdVisible.value = false
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '改密失败')
  } finally {
    submitting.value = false
  }
}

async function setRoles(row: Staff, role: string) {
  try {
    await http.put(`/staff/${row.id}/roles`, { role_codes: [role] })
    ElMessage.success('角色已更新')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '更新失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>员工与权限</h3>
      <el-button type="primary" @click="openDialog">创建员工</el-button>
    </div>

    <div class="filters">
      <el-input
        v-model="query.q"
        clearable
        placeholder="用户名 / 姓名"
        style="width: 200px"
        @keyup.enter="search"
      />
      <el-select v-model="query.merchant_id" clearable placeholder="商户" style="width: 180px">
        <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-select v-model="query.status" clearable placeholder="状态" style="width: 120px">
        <el-option label="启用" value="active" />
        <el-option label="禁用" value="inactive" />
      </el-select>
      <el-button type="primary" @click="search">查询</el-button>
      <el-button @click="resetSearch">重置</el-button>
    </div>

    <el-table :data="staff" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="display_name" label="姓名" />
      <el-table-column label="商户" width="180">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
      <el-table-column label="角色">
        <template #default="{ row }">
          <el-tag v-for="r in row.role_codes" :key="r" size="small" style="margin-right: 6px">
            {{ roleLabel(r) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="340">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="warning" plain @click="openResetPwd(row)">改密</el-button>
          <el-button
            size="small"
            :type="row.is_active ? 'warning' : 'success'"
            @click="toggleActive(row)"
          >
            {{ row.is_active ? '禁用' : '启用' }}
          </el-button>
          <el-select
            :model-value="row.role_codes[0]"
            placeholder="切换角色"
            style="width: 120px; margin-left: 8px"
            @change="(v: string) => setRoles(row, v)"
          >
            <el-option v-for="o in roleOptions" :key="o.code" :label="o.name" :value="o.code" />
          </el-select>
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

    <el-dialog v-model="dialogVisible" title="创建员工" width="480px">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password />
        </el-form-item>
        <el-form-item label="姓名" prop="display_name">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item label="商户">
          <el-select v-model="form.merchant_id" clearable style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色" prop="role_codes">
          <el-select v-model="form.role_codes" multiple style="width: 100%">
            <el-option v-for="o in roleOptions" :key="o.code" :label="o.name" :value="o.code" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="editVisible" title="编辑员工" width="480px">
      <el-form label-width="90px">
        <el-form-item label="用户名">
          <el-input :model-value="editing?.username" disabled />
        </el-form-item>
        <el-form-item label="姓名">
          <el-input v-model="editForm.display_name" />
        </el-form-item>
        <el-form-item label="新密码">
          <el-input v-model="editForm.password" type="password" show-password placeholder="留空不修改" />
        </el-form-item>
        <el-form-item label="商户">
          <el-select v-model="editForm.merchant_id" clearable style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色">
          <el-select v-model="editForm.role_codes" multiple style="width: 100%">
            <el-option v-for="o in roleOptions" :key="o.code" :label="o.name" :value="o.code" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="pwdVisible"
      :title="`修改密码 · ${pwdTarget?.display_name || pwdTarget?.username || ''}`"
      width="440px"
      destroy-on-close
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 14px"
        title="重置后对方需使用新密码登录后台，原密码立即失效。"
      />
      <el-form ref="pwdFormRef" :model="pwdForm" :rules="pwdRules" label-width="90px">
        <el-form-item label="新密码" prop="password">
          <el-input v-model="pwdForm.password" type="password" show-password maxlength="64" placeholder="至少 6 位" />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input v-model="pwdForm.confirm" type="password" show-password maxlength="64" placeholder="再次输入新密码" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pwdVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveResetPwd">确认改密</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0;
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
