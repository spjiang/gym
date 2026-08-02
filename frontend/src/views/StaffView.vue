<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Staff = {
  id: number
  username: string
  display_name: string
  merchant_id: number | null
  role_codes: string[]
}
type Merchant = { id: number; name: string }

const staff = ref<Staff[]>([])
const merchants = ref<Merchant[]>([])
const form = reactive({
  username: '',
  password: '',
  display_name: '',
  merchant_id: undefined as number | undefined,
  role_codes: ['front_desk'] as string[],
})

async function load() {
  const [s, m] = await Promise.all([http.get('/staff'), http.get('/merchants')])
  staff.value = s.data
  merchants.value = m.data
}

async function create() {
  await http.post('/staff', form)
  ElMessage.success('员工已创建')
  form.username = ''
  form.password = ''
  form.display_name = ''
  await load()
}

async function setRoles(row: Staff, role: string) {
  await http.put(`/staff/${row.id}/roles`, { role_codes: [role] })
  ElMessage.success('角色已更新')
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <h3>创建员工</h3>
    <el-form label-width="90px" style="max-width: 520px">
      <el-form-item label="用户名"><el-input v-model="form.username" /></el-form-item>
      <el-form-item label="密码"><el-input v-model="form.password" type="password" /></el-form-item>
      <el-form-item label="姓名"><el-input v-model="form.display_name" /></el-form-item>
      <el-form-item label="商户">
        <el-select v-model="form.merchant_id" clearable style="width: 100%">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="角色">
        <el-select v-model="form.role_codes" multiple style="width: 100%">
          <el-option label="商户管理员" value="merchant_admin" />
          <el-option label="前台" value="front_desk" />
          <el-option label="教练" value="coach" />
        </el-select>
      </el-form-item>
      <el-button type="primary" @click="create">创建</el-button>
    </el-form>

    <h3 style="margin-top: 24px">员工列表</h3>
    <el-table :data="staff">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="username" label="用户名" />
      <el-table-column prop="display_name" label="姓名" />
      <el-table-column prop="merchant_id" label="商户ID" />
      <el-table-column label="角色">
        <template #default="{ row }">{{ row.role_codes.join(', ') }}</template>
      </el-table-column>
      <el-table-column label="快捷改角色" width="280">
        <template #default="{ row }">
          <el-button size="small" @click="setRoles(row, 'front_desk')">前台</el-button>
          <el-button size="small" @click="setRoles(row, 'coach')">教练</el-button>
          <el-button size="small" @click="setRoles(row, 'merchant_admin')">商户管理员</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
