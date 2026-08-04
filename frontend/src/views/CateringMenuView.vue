<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../api/http'

type Merchant = { id: number; name: string; subsystem_codes: string[] }
type MenuItem = {
  id: number
  merchant_id: number
  name: string
  category: string
  price: string
  is_active: boolean
}

const merchants = ref<Merchant[]>([])
const items = ref<MenuItem[]>([])
const merchantId = ref<number | undefined>()
const loading = ref(false)
const dialogVisible = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const form = reactive({ name: '', category: '饮品', price: '38.00' })

const rules: FormRules = {
  name: [{ required: true, message: '请填写名称', trigger: 'blur' }],
  category: [{ required: true, message: '请填写分类', trigger: 'blur' }],
  price: [{ required: true, message: '请填写价格', trigger: 'blur' }],
}

const cateringMerchants = () =>
  merchants.value.filter((m) => (m.subsystem_codes || []).includes('catering'))

async function loadMerchants() {
  const { data } = await http.get('/merchants')
  merchants.value = data
  const list = cateringMerchants()
  if (!merchantId.value && list[0]) merchantId.value = list[0].id
}

async function loadItems() {
  if (!merchantId.value) {
    items.value = []
    return
  }
  loading.value = true
  try {
    const { data } = await http.get('/catering/menu-items', {
      params: { merchant_id: merchantId.value },
    })
    items.value = data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function refresh() {
  await loadMerchants()
  await loadItems()
}

function openDialog() {
  form.name = ''
  form.category = '饮品'
  form.price = '38.00'
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function create() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok || !merchantId.value) return
  submitting.value = true
  try {
    await http.post('/catering/menu-items', {
      merchant_id: merchantId.value,
      name: form.name.trim(),
      category: form.category.trim(),
      price: form.price,
    })
    ElMessage.success('菜单已创建')
    dialogVisible.value = false
    await loadItems()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

async function deactivate(id: number) {
  try {
    await http.post(`/catering/menu-items/${id}/deactivate?merchant_id=${merchantId.value}`)
    ElMessage.success('已停用')
    await loadItems()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>餐饮菜单</h3>
      <el-button type="primary" :disabled="!merchantId" @click="openDialog">新建菜品</el-button>
    </div>

    <el-form inline>
      <el-form-item label="餐饮商户">
        <el-select v-model="merchantId" style="width: 220px" @change="loadItems">
          <el-option v-for="m in cateringMerchants()" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="!cateringMerchants().length"
      type="warning"
      :closable="false"
      title="当前没有关联「餐饮管理」的商户"
      description="请在「商户组织」为清吧等商户勾选餐饮子系统。"
      style="margin-bottom: 16px"
    />

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="category" label="分类" width="120" />
      <el-table-column label="价格" width="100">
        <template #default="{ row }">¥{{ row.price }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '在售' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button link type="danger" :disabled="!row.is_active" @click="deactivate(row.id)">
            停用
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="新建菜品" width="440px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="分类" prop="category"><el-input v-model="form.category" /></el-form-item>
        <el-form-item label="价格" prop="price"><el-input v-model="form.price" /></el-form-item>
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
  margin-bottom: 8px;
}
.toolbar h3 {
  margin: 0;
}
</style>
