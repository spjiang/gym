<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules, type UploadRequestOptions, type UploadUserFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import http from '../../../core/api/http'
import { previewUploadFile } from '../../../core/imagePreview'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes: string[] }
type MenuItem = {
  id: number
  merchant_id: number
  name: string
  category: string
  category_id: number | null
  price: string
  image_url: string | null
  description: string | null
  is_active: boolean
}
type Category = { id: number; name: string; is_active: boolean }

const router = useRouter()
const merchants = ref<Merchant[]>([])
const items = ref<MenuItem[]>([])
const categories = ref<Category[]>([])
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const loading = ref(false)
const uploading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const query = reactive({
  q: '',
  category_id: undefined as number | undefined,
  status: '' as '' | 'active' | 'inactive',
  price_min: undefined as number | undefined,
  price_max: undefined as number | undefined,
})
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const editingMerchantId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const imageList = ref<UploadUserFile[]>([])
const form = reactive({
  name: '',
  category_id: undefined as number | undefined,
  price: '38.00',
  description: '',
  image_url: '',
  is_active: true,
})

const rules: FormRules = {
  name: [{ required: true, message: '请填写名称', trigger: 'blur' }],
  category_id: [{ required: true, message: '请选择分类', trigger: 'change' }],
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

function syncImageList() {
  imageList.value = form.image_url ? [{ name: '菜品图', url: form.image_url, uid: 1 }] : []
}

async function loadItems() {
  loading.value = true
  try {
    const { data } = await http.get('/catering/menu-items', {
      params: {
        merchant_id: merchantId.value,
        q: query.q.trim() || undefined,
        category_id: query.category_id,
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

async function loadCategories() {
  if (!merchantId.value) {
    categories.value = []
    return
  }
  const { data } = await http.get('/catering/categories', {
    params: { merchant_id: merchantId.value, page: 1, page_size: 100 },
  })
  categories.value = data.items
}

async function refresh() {
  await loadMerchants()
  await loadCategories()
  await loadItems()
}

function search() {
  page.value = 1
  void loadItems()
}

function resetSearch() {
  query.q = ''
  query.category_id = undefined
  query.status = ''
  query.price_min = undefined
  query.price_max = undefined
  page.value = 1
  void loadItems()
}

function resetForm() {
  form.name = ''
  form.category_id = categories.value[0]?.id
  form.price = '38.00'
  form.description = ''
  form.image_url = ''
  form.is_active = true
  editingId.value = null
  editingMerchantId.value = null
  syncImageList()
  formRef.value?.clearValidate()
}

function openCreate() {
  resetForm()
  dialogVisible.value = true
}

function openEdit(row: MenuItem) {
  editingId.value = row.id
  editingMerchantId.value = row.merchant_id
  form.name = row.name
  form.category_id = row.category_id || undefined
  form.price = row.price
  form.description = row.description || ''
  form.image_url = row.image_url || ''
  form.is_active = row.is_active
  syncImageList()
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function uploadImage(opt: UploadRequestOptions) {
  const fd = new FormData()
  fd.append('file', opt.file as File)
  uploading.value = true
  try {
    const { data } = await http.post<{ url: string }>('/uploads', fd, { timeout: 30000 })
    form.image_url = data.url
    syncImageList()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '图片上传失败')
  } finally {
    uploading.value = false
  }
}

function removeImage() {
  form.image_url = ''
  syncImageList()
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  const mid = editingMerchantId.value || requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    const payload = {
      merchant_id: mid,
      name: form.name.trim(),
      category_id: form.category_id,
      price: form.price,
      description: form.description.trim() || null,
      image_url: form.image_url || null,
      is_active: form.is_active,
    }
    if (editingId.value) {
      await http.patch(`/catering/menu-items/${editingId.value}`, payload)
      ElMessage.success('菜品已更新')
    } else {
      await http.post('/catering/menu-items', payload)
      ElMessage.success('菜品已创建')
    }
    dialogVisible.value = false
    await loadItems()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function setActive(row: MenuItem, is_active: boolean) {
  try {
    await http.patch(`/catering/menu-items/${row.id}`, {
      merchant_id: row.merchant_id,
      name: row.name,
      category_id: row.category_id,
      category: row.category,
      price: row.price,
      description: row.description,
      image_url: row.image_url,
      is_active,
    })
    ElMessage.success(is_active ? '已上架' : '已停用')
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
      <div class="toolbar-actions">
        <el-button @click="router.push('/catering/categories')">菜单分类</el-button>
        <el-button type="primary" @click="openCreate">新建菜品</el-button>
      </div>
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
        <el-select v-model="query.category_id" clearable placeholder="全部" style="width: 140px">
          <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
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
    <el-alert
      v-else-if="merchantId && !categories.some((c) => c.is_active)"
      type="warning"
      :closable="false"
      show-icon
      title="还没有启用中的菜单分类，点餐侧栏会无法归类。"
      description="请先到「菜单分类」创建分类，再把菜品挂上去。"
      style="margin-bottom: 16px"
    />

    <el-table :data="items" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="图片" width="80">
        <template #default="{ row }">
          <img v-if="row.image_url" class="thumb" :src="row.image_url" alt="" />
          <span v-else class="muted">—</span>
        </template>
      </el-table-column>
      <el-table-column label="商户" width="140">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
      <el-table-column prop="name" label="名称" min-width="140" />
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column label="价格" width="100">
        <template #default="{ row }">¥{{ row.price }}</template>
      </el-table-column>
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '在售' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button v-if="row.is_active" link type="danger" @click="setActive(row, false)">停用</el-button>
          <el-button v-else link type="success" @click="setActive(row, true)">上架</el-button>
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

    <el-dialog
      v-model="dialogVisible"
      :title="editingId ? '编辑菜品' : '新建菜品'"
      width="520px"
      destroy-on-close
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="name"><el-input v-model="form.name" maxlength="128" /></el-form-item>
        <el-form-item label="分类" prop="category_id">
          <el-select v-model="form.category_id" placeholder="请选择分类" style="width: 100%">
            <el-option
              v-for="c in categories"
              :key="c.id"
              :label="c.is_active ? c.name : `${c.name}（停用）`"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="价格" prop="price"><el-input v-model="form.price" /></el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="2" maxlength="255" show-word-limit />
        </el-form-item>
        <el-form-item label="菜品图">
          <el-upload
            list-type="picture-card"
            accept=".jpg,.jpeg,.png,.webp"
            :limit="1"
            :file-list="imageList"
            :http-request="uploadImage"
            :on-preview="previewUploadFile"
            :on-remove="removeImage"
            :disabled="uploading"
            :class="{ 'hide-uploader': !!form.image_url }"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
          <p class="hint">一张，不超过 8MB，支持 JPG / PNG / WEBP。</p>
        </el-form-item>
        <el-form-item v-if="editingId" label="状态">
          <el-switch v-model="form.is_active" active-text="在售" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">
          {{ editingId ? '保存' : '创建' }}
        </el-button>
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
.toolbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
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
.thumb {
  width: 48px;
  height: 48px;
  object-fit: cover;
  border-radius: 6px;
  border: 1px solid var(--el-border-color-lighter);
}
.muted {
  color: var(--el-text-color-placeholder);
}
.hint {
  margin: 8px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.hide-uploader :deep(.el-upload--picture-card) {
  display: none;
}
</style>
