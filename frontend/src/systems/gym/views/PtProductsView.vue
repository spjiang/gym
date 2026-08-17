<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Product = {
  id: number
  name: string
  price: string
  session_count: number
  valid_days: number
  is_active: boolean
}

const merchants = ref<Merchant[]>([])
const products = ref<Product[]>([])
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
  status: '' as '' | 'active' | 'inactive',
  price_min: undefined as number | undefined,
  price_max: undefined as number | undefined,
  session_min: undefined as number | undefined,
  session_max: undefined as number | undefined,
  valid_days_min: undefined as number | undefined,
  valid_days_max: undefined as number | undefined,
})
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ name: '', price: '1000', session_count: 10, valid_days: 90 })

const rules: FormRules = {
  name: [{ required: true, message: '请填写课包名称', trigger: 'blur' }],
  price: [
    { required: true, message: '请填写价格', trigger: 'blur' },
    {
      validator: (_r, v: string, cb) => {
        const n = Number(v)
        if (!Number.isFinite(n) || n <= 0) cb(new Error('价格必须大于 0'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

async function loadMerchants() {
  const { data } = await http.get('/merchants')
  merchants.value = merchantsWithSystem(data, 'gym')
  if (merchantId.value && !merchants.value.some((m) => m.id === merchantId.value)) {
    merchantId.value = undefined
  }
}

async function loadProducts() {
  const { data } = await http.get('/pt-products', {
    params: {
      merchant_id: merchantId.value,
      q: query.q.trim() || undefined,
      is_active: query.status === 'active' ? true : query.status === 'inactive' ? false : undefined,
      price_min: query.price_min,
      price_max: query.price_max,
      session_min: query.session_min,
      session_max: query.session_max,
      valid_days_min: query.valid_days_min,
      valid_days_max: query.valid_days_max,
      page: page.value,
      page_size: pageSize.value,
    },
  })
  products.value = data.items
  total.value = data.total
}

async function refresh() {
  loading.value = true
  try {
    await loadMerchants()
    await loadProducts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function refreshProducts() {
  loading.value = true
  try {
    await loadProducts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void refreshProducts()
}

function resetSearch() {
  query.q = ''
  query.status = ''
  query.price_min = undefined
  query.price_max = undefined
  query.session_min = undefined
  query.session_max = undefined
  query.valid_days_min = undefined
  query.valid_days_max = undefined
  page.value = 1
  void refreshProducts()
}

function openCreate() {
  editingId.value = null
  form.name = ''
  form.price = '1000'
  form.session_count = 10
  form.valid_days = 90
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

function openEdit(row: Product) {
  editingId.value = row.id
  form.name = row.name
  form.price = row.price
  form.session_count = row.session_count
  form.valid_days = row.valid_days
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    const payload = {
      merchant_id: mid,
      name: form.name.trim(),
      price: form.price,
      session_count: form.session_count,
      valid_days: form.valid_days,
      all_coaches: true,
    }
    if (editingId.value) {
      await http.patch(`/pt-products/${editingId.value}`, payload)
      ElMessage.success('课包已更新')
    } else {
      await http.post('/pt-products', payload)
      ElMessage.success('课包已创建')
    }
    dialogVisible.value = false
    await refreshProducts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function deactivate(row: Product) {
  try {
    await ElMessageBox.confirm(`确认停用「${row.name}」？停用后将无法继续售卖该课包。`, '停用确认', {
      type: 'warning',
      confirmButtonText: '停用',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await http.post(`/pt-products/${row.id}/deactivate`)
    ElMessage.success('已停用')
    await refreshProducts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '停用失败')
  }
}

async function activate(row: Product) {
  try {
    await ElMessageBox.confirm(`确认重新启用「${row.name}」？启用后可继续售卖。`, '启用确认', {
      type: 'info',
      confirmButtonText: '启用',
      cancelButtonText: '取消',
    })
  } catch {
    return
  }
  try {
    await http.post(`/pt-products/${row.id}/activate`)
    ElMessage.success('已重新启用')
    await refreshProducts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '启用失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>私教课包</h3>
        <p class="lead">配置可售私教课时商品。售卖与核销在「私教课管理 → 会员课包」。</p>
      </div>
      <el-button type="primary" @click="openCreate">新建课包</el-button>
    </div>
    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="名称 / ID" style="width: 160px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 110px">
          <el-option label="在售" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>
      </el-form-item>
      <el-form-item label="价格">
        <el-input-number v-model="query.price_min" :min="0" :controls="false" placeholder="最低" style="width: 100px" />
        <span class="range-sep">—</span>
        <el-input-number v-model="query.price_max" :min="0" :controls="false" placeholder="最高" style="width: 100px" />
      </el-form-item>
      <el-form-item label="课时">
        <el-input-number v-model="query.session_min" :min="1" :controls="false" placeholder="最少" style="width: 90px" />
        <span class="range-sep">—</span>
        <el-input-number v-model="query.session_max" :min="1" :controls="false" placeholder="最多" style="width: 90px" />
      </el-form-item>
      <el-form-item label="有效天">
        <el-input-number
          v-model="query.valid_days_min"
          :min="1"
          :controls="false"
          placeholder="最少"
          style="width: 90px"
        />
        <span class="range-sep">—</span>
        <el-input-number
          v-model="query.valid_days_max"
          :min="1"
          :controls="false"
          placeholder="最多"
          style="width: 90px"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>
    <el-table :data="products" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column label="价格" width="110">
        <template #default="{ row }">¥{{ row.price }}</template>
      </el-table-column>
      <el-table-column prop="session_count" label="课时" width="90" />
      <el-table-column prop="valid_days" label="有效天" width="90" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '在售' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.is_active" link type="danger" @click="deactivate(row)">停用</el-button>
          <el-button v-else link type="success" @click="activate(row)">启用</el-button>
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
        @current-change="refreshProducts"
        @size-change="
          () => {
            page = 1
            refreshProducts()
          }
        "
      />
    </div>
    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑课包' : '新建课包'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：私教 10 次卡" maxlength="128" />
        </el-form-item>
        <el-form-item label="价格" prop="price">
          <el-input v-model="form.price" />
        </el-form-item>
        <el-form-item label="课时">
          <el-input-number v-model="form.session_count" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="有效天">
          <el-input-number v-model="form.valid_days" :min="1" style="width: 100%" />
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
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}
.lead {
  margin: 0;
  max-width: 640px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--el-text-color-secondary);
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
