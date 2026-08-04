<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../api/http'

type Staff = {
  id: number
  username: string
  display_name: string
  merchant_id: number | null
  role_codes: string[]
}
type Merchant = { id: number; name: string }

const ROLE_OPTIONS = [
  { label: '商户管理员', value: 'merchant_admin' },
  { label: '前台', value: 'front_desk' },
  { label: '教练', value: 'coach' },
]

const staff = ref<Staff[]>([])
const merchants = ref<Merchant[]>([])
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  username: '',
  password: '',
  display_name: '',
  merchant_id: undefined as number | undefined,
  role_codes: ['front_desk'] as string[],
})

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

async function load() {
  const [s, m] = await Promise.all([http.get('/staff'), http.get('/merchants')])
  staff.value = s.data
  merchants.value = m.data
}

function openDialog() {
  form.username = ''
  form.password = ''
  form.display_name = ''
  form.merchant_id = merchants.value[0]?.id
  form.role_codes = ['front_desk']
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

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

    <el-table :data="staff" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="display_name" label="姓名" />
      <el-table-column label="商户" width="180">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
      <el-table-column label="角色">
        <template #default="{ row }">
          <el-tag v-for="r in row.role_codes" :key="r" size="small" style="margin-right: 6px">
            {{ ROLE_OPTIONS.find((o) => o.value === r)?.label || r }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="快捷改角色" width="300">
        <template #default="{ row }">
          <el-button
            v-for="o in ROLE_OPTIONS"
            :key="o.value"
            size="small"
            :disabled="row.role_codes.length === 1 && row.role_codes[0] === o.value"
            @click="setRoles(row, o.value)"
          >
            {{ o.label }}
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建员工弹窗 -->
    <el-dialog v-model="dialogVisible" title="创建员工" width="520px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="登录用户名" maxlength="64" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位" maxlength="64" />
        </el-form-item>
        <el-form-item label="姓名" prop="display_name">
          <el-input v-model="form.display_name" placeholder="员工姓名" maxlength="64" />
        </el-form-item>
        <el-form-item label="商户">
          <el-select v-model="form.merchant_id" clearable style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="角色" prop="role_codes">
          <el-select v-model="form.role_codes" multiple style="width: 100%">
            <el-option v-for="o in ROLE_OPTIONS" :key="o.value" :label="o.label" :value="o.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="create">创建</el-button>
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
  margin-bottom: 20px;
}

.toolbar h3 {
  margin: 0;
  font-size: 1.1rem;
}
</style>
