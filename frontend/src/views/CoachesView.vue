<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Merchant = { id: number; name: string }
type Staff = { id: number; display_name: string; username: string }
type Coach = {
  id: number
  display_name: string
  specialties: string | null
  is_active: boolean
  staff_user_id: number
}

const merchants = ref<Merchant[]>([])
const staff = ref<Staff[]>([])
const coaches = ref<Coach[]>([])
const merchantId = ref<number | undefined>()
const form = reactive({
  staff_user_id: undefined as number | undefined,
  display_name: '',
  specialties: '',
})

async function refresh() {
  const [m, s] = await Promise.all([http.get('/merchants'), http.get('/staff')])
  merchants.value = m.data
  staff.value = s.data
  if (!merchantId.value && m.data[0]) merchantId.value = m.data[0].id
  if (!merchantId.value) return
  const { data } = await http.get('/coaches', { params: { merchant_id: merchantId.value } })
  coaches.value = data
}

async function createCoach() {
  await http.post('/coaches', { ...form, merchant_id: merchantId.value })
  ElMessage.success('教练已创建')
  form.display_name = ''
  form.specialties = ''
  form.staff_user_id = undefined
  await refresh()
}

async function deactivate(id: number) {
  await http.post(`/coaches/${id}/deactivate`)
  ElMessage.success('已停用')
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div>
    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-card header="新建教练" style="margin-bottom: 16px">
      <el-form inline>
        <el-form-item label="员工">
          <el-select v-model="form.staff_user_id" style="width: 180px" filterable>
            <el-option v-for="s in staff" :key="s.id" :label="`${s.display_name} (${s.username})`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名">
          <el-input v-model="form.display_name" />
        </el-form-item>
        <el-form-item label="擅长">
          <el-input v-model="form.specialties" />
        </el-form-item>
        <el-button type="primary" @click="createCoach">创建</el-button>
      </el-form>
    </el-card>

    <el-table :data="coaches" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="display_name" label="姓名" />
      <el-table-column prop="specialties" label="擅长" />
      <el-table-column prop="is_active" label="启用" width="90">
        <template #default="{ row }">{{ row.is_active ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="row.is_active" link type="danger" @click="deactivate(row.id)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
