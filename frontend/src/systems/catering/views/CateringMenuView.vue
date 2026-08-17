<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

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
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const query = reactive({
  q: '',
  category: '',
  status: '' as '' | 'active' | 'inactive',
  price_min: undefined as number | undefined,
  price_max: undefined as number | undefined,
})
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
  if (merchantId.value && !list.some((m) => m.id === merchantId.value)) merchantId.value = undefined
}

function merchantName(id: number) {
  return merchants.value.find((m) => m.id === id)?.name || `#${id}`
}

async function loadItems() {
  loading.value = true
  try {
    const { data } = await http.get('/catering/menu-items', {
      params: {
        merchant_id: merchantId.value,
        q: query.q.trim() || undefined,
        category: query.category.trim() || undefined,
        is_active: query.status === 'active' ? true : query.status === 'inactive' ? false : undefined,
        price_min: query.price_min,
        price_max: query.price_max,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    items.value = data.items
    total.value = data.total
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

function search() {
  page.value = 1
  void loadItems()
}

function resetSearch() {
  query.q = ''
  query.category = ''
  query.status = ''
  query.price_min = undefined
  query.price_max = undefined
  page.value = 1
  void loadItems()
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
  const mid = requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    await http.post('/catering/menu-items', {
      merchant_id: mid,
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

async function deactivate(row: MenuItem) {
  try {
    await http.post(`/catering/menu-items/${row.id}/deactivate?merchant_id=${row.merchant_id}`)
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
      <el-button type="primary" @click="openDialog">新建菜品</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="餐饮商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="search">
          <el-option v-for="m in cateringMerchants()" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="名称 / ID" style="width: 150px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="分类">
        <el-input v-model="query.category" clearable placeholder="如：饮品" style="width: 120px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 110px">
          <el-option label="在售" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>
      </el-form-item>
      <el-form-item label="价格">
        <el-input-number v-model="query.price_min" :min="0" :controls="false" placeholder="最低" style="width: 90px" />
        <span class="range-sep">—</span>
        <el-input-number v-model="query.price_max" :min="0" :controls="false" placeholder="最高" style="width: 90px" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="!cateringMerchants().length"
      type="warning"
      :closable="false"
      title="当前没有关联「观野BAR」的商户"
      description="请在「商户组织」为酒吧商户勾选观野BAR。"
      style="margin-bottom: 16px"
    />

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="商户" width="160">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
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
          <el-button link type="danger" :disabled="!row.is_active" @click="deactivate(row)">
            停用
          </el-button>
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
        @current-change="loadItems"
        @size-change="
          () => {
            page = 1
            loadItems()
          }
        "
      />
    </div>

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
.filters {
  margin-bottom: 4px;
}
.range-sep {
  margin: 0 6px;
  color: var(--el-text-color-secondary);
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
