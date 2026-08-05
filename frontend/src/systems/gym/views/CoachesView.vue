<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { merchantsWithSystem } from '../../../core/nav/systems'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
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
const loading = ref(false)

const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({
  staff_user_id: undefined as number | undefined,
  display_name: '',
  specialties: '',
})

const rules: FormRules = {
  staff_user_id: [{ required: true, message: '请选择员工账号', trigger: 'change' }],
  display_name: [{ required: true, message: '请填写教练显示名', trigger: 'blur' }],
}

function staffName(id: number | undefined) {
  const s = staff.value.find((x) => x.id === id)
  return s ? `${s.display_name} (${s.username})` : ''
}

async function refresh() {
  loading.value = true
  try {
    const [m, s] = await Promise.all([
      http.get('/merchants'),
      http.get('/staff', { params: { page: 1, page_size: 100 } }),
    ])
    merchants.value = merchantsWithSystem(m.data, 'gym')
    staff.value = s.data.items
    if (!merchantId.value && merchants.value[0]) merchantId.value = merchants.value[0].id
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = merchants.value[0]?.id
    }
    if (!merchantId.value) return
    const { data } = await http.get('/coaches', { params: { merchant_id: merchantId.value } })
    coaches.value = data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openDialog() {
  form.staff_user_id = undefined
  form.display_name = ''
  form.specialties = ''
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function createCoach() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/coaches', {
      ...form,
      display_name: form.display_name.trim(),
      merchant_id: merchantId.value,
    })
    ElMessage.success('教练已创建')
    dialogVisible.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
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
    <div class="toolbar">
      <h3>教练档案</h3>
      <el-button type="primary" @click="openDialog">新建教练</el-button>
    </div>

    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-table :data="coaches" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="display_name" label="姓名" />
      <el-table-column label="员工账号" width="200">
        <template #default="{ row }">{{ staffName(row.staff_user_id) }}</template>
      </el-table-column>
      <el-table-column prop="specialties" label="擅长" />
      <el-table-column label="启用" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="row.is_active" link type="danger" @click="deactivate(row.id)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建教练弹窗 -->
    <el-dialog v-model="dialogVisible" title="新建教练" width="500px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="员工账号" prop="staff_user_id">
          <el-select v-model="form.staff_user_id" filterable style="width: 100%">
            <el-option v-for="s in staff" :key="s.id" :label="`${s.display_name} (${s.username})`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="显示名" prop="display_name">
          <el-input v-model="form.display_name" placeholder="对外展示的教练姓名" maxlength="64" />
        </el-form-item>
        <el-form-item label="擅长">
          <el-input v-model="form.specialties" placeholder="如：减脂 / 力量训练 / 普拉提" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createCoach">创建</el-button>
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
