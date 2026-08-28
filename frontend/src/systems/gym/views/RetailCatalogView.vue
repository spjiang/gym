<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type UploadFile, type UploadRequestOptions, type UploadUserFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import http from '../../../core/api/http'
import { previewUploadFile } from '../../../core/imagePreview'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Category = { id: number; name: string; sort_order: number }
type Sku = {
  id: number
  name: string
  price: string
  unit: string
  barcode?: string | null
  stock_qty: number
  low_stock_threshold: number
  is_active: boolean
  category_id: number | null
  remark?: string | null
  image_urls?: string[]
}

const SKU_IMAGE_LIMIT = 9

const merchants = ref<Merchant[]>([])
const categories = ref<Category[]>([])
const skus = ref<Sku[]>([])
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
  category_id: undefined as number | undefined,
  status: '' as '' | 'active' | 'inactive',
})
const skuDialog = ref(false)
const detailVisible = ref(false)
const detail = ref<Sku | null>(null)
const submitting = ref(false)
const editingSkuId = ref<number | null>(null)
const skuFormRef = ref<FormInstance>()
const skuForm = reactive({
  name: '',
  price: '99.00',
  unit: '件',
  barcode: '',
  category_id: undefined as number | undefined,
  low_stock_threshold: 5,
  is_active: true,
  remark: '',
  image_urls: [] as string[],
})
const imageFileList = ref<UploadUserFile[]>([])
const uploading = ref(false)

const skuRules: FormRules = {
  name: [{ required: true, message: '请填写商品名称', trigger: 'blur' }],
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

function categoryName(id: number | null) {
  return categories.value.find((c) => c.id === id)?.name || '—'
}

async function refresh() {
  loading.value = true
  try {
    const { data } = await http.get('/merchants')
    merchants.value = merchantsWithSystem(data, 'gym')
    if (merchantId.value && !merchants.value.some((m) => m.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const [c, s] = await Promise.all([
      http.get('/retail/categories', { params: { merchant_id: merchantId.value, page: 1, page_size: 100 } }),
      http.get('/retail/skus', {
        params: {
          merchant_id: merchantId.value,
          q: query.q.trim() || undefined,
          category_id: query.category_id,
          is_active: query.status === 'active' ? true : query.status === 'inactive' ? false : undefined,
          page: page.value,
          page_size: pageSize.value,
        },
      }),
    ])
    categories.value = c.data.items
    skus.value = s.data.items
    total.value = s.data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function search() {
  page.value = 1
  void refresh()
}

function resetSearch() {
  query.q = ''
  query.category_id = undefined
  query.status = ''
  page.value = 1
  void refresh()
}

function syncImageList() {
  imageFileList.value = skuForm.image_urls.map((url, i) => ({
    name: `图${i + 1}`,
    url,
    uid: i + 1,
  }))
}

function openSku(row?: Sku) {
  editingSkuId.value = row?.id ?? null
  skuForm.name = row?.name || ''
  skuForm.price = row?.price || '99.00'
  skuForm.unit = row?.unit || '件'
  skuForm.barcode = row?.barcode || ''
  skuForm.category_id = row?.category_id ?? categories.value[0]?.id
  skuForm.low_stock_threshold = row?.low_stock_threshold ?? 5
  skuForm.is_active = row?.is_active ?? true
  skuForm.remark = row?.remark || ''
  skuForm.image_urls = [...(row?.image_urls || [])]
  syncImageList()
  skuFormRef.value?.clearValidate()
  skuDialog.value = true
}

async function uploadSkuImage(opt: UploadRequestOptions) {
  if (skuForm.image_urls.length >= SKU_IMAGE_LIMIT) {
    ElMessage.warning(`最多上传 ${SKU_IMAGE_LIMIT} 张图片`)
    return
  }
  const fd = new FormData()
  fd.append('file', opt.file)
  uploading.value = true
  try {
    const { data } = await http.post<{ url: string }>('/uploads', fd, { timeout: 30000 })
    skuForm.image_urls.push(data.url)
    syncImageList()
    opt.onSuccess(data)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

function removeSkuImage(file: UploadFile) {
  skuForm.image_urls = skuForm.image_urls.filter((url) => url !== file.url)
  syncImageList()
}

function onImageExceed() {
  ElMessage.warning(`最多上传 ${SKU_IMAGE_LIMIT} 张图片`)
}

async function openDetail(row: Sku) {
  detail.value = row
  detailVisible.value = true
  try {
    const { data } = await http.get<Sku>(`/retail/skus/${row.id}`)
    detail.value = data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载详情失败')
  }
}

function editFromDetail() {
  if (!detail.value) return
  openSku(detail.value)
}

async function saveSku() {
  const ok = await skuFormRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    const payload = {
      merchant_id: mid,
      name: skuForm.name.trim(),
      price: skuForm.price,
      unit: skuForm.unit,
      barcode: skuForm.barcode.trim() || null,
      category_id: skuForm.category_id ?? null,
      low_stock_threshold: skuForm.low_stock_threshold,
      is_active: skuForm.is_active,
      remark: skuForm.remark.trim() || null,
      image_urls: skuForm.image_urls,
    }
    if (editingSkuId.value) await http.patch(`/retail/skus/${editingSkuId.value}`, payload)
    else await http.post('/retail/skus', payload)
    ElMessage.success(editingSkuId.value ? '商品已更新' : '商品已创建')
    skuDialog.value = false
    await refresh()
    if (detailVisible.value && editingSkuId.value) {
      const current = skus.value.find((s) => s.id === editingSkuId.value)
      if (current) detail.value = current
    }
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function deactivate(row: Sku) {
  try {
    await ElMessageBox.confirm(
      `确认停用「${row.name}」？停用后前台将无法继续收银该商品。`,
      '停用确认',
      { type: 'warning', confirmButtonText: '停用', cancelButtonText: '取消', appendTo: document.body },
    )
  } catch {
    return
  }
  try {
    await http.post(`/retail/skus/${row.id}/deactivate`)
    ElMessage.success('已停用')
    await refresh()
    if (detail.value?.id === row.id) detail.value = { ...detail.value, is_active: false }
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '停用失败')
  }
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>商品管理</h3>
        <p class="lead">维护可售 SKU。分类请到「商品分类」，入库出库与收银请到「库存收银」。</p>
      </div>
      <el-button type="primary" @click="openSku()">新建商品</el-button>
    </div>
    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input
          v-model="query.q"
          clearable
          placeholder="商品名称 / 条码"
          style="width: 180px"
          @keyup.enter="search"
        />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="query.category_id" clearable placeholder="全部" style="width: 140px">
          <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="在售" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="skus" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="商品" min-width="220">
        <template #default="{ row }">
          <div class="sku-cell">
            <img v-if="row.image_urls?.[0]" class="sku-thumb" :src="row.image_urls[0]" alt="" />
            <div>
              <el-button link type="primary" @click="openDetail(row)">{{ row.name }}</el-button>
              <div v-if="row.barcode" class="sku-barcode">条码 {{ row.barcode }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="分类" width="120">
        <template #default="{ row }">{{ categoryName(row.category_id) }}</template>
      </el-table-column>
      <el-table-column label="单价" width="100">
        <template #default="{ row }">¥{{ row.price }}</template>
      </el-table-column>
      <el-table-column prop="unit" label="单位" width="70" />
      <el-table-column prop="stock_qty" label="库存" width="80" />
      <el-table-column label="状态" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '在售' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button link type="primary" @click="openSku(row)">编辑</el-button>
          <el-button v-if="row.is_active" link type="danger" @click="deactivate(row)">停用</el-button>
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
        @current-change="refresh"
        @size-change="
          () => {
            page = 1
            refresh()
          }
        "
      />
    </div>

    <el-drawer v-model="detailVisible" :title="detail ? `商品详情 · ${detail.name}` : '商品详情'" size="520px">
      <template v-if="detail">
        <div v-if="detail.image_urls?.length" class="detail-hero">
          <el-image
            v-for="(url, index) in detail.image_urls"
            :key="url"
            :src="url"
            :preview-src-list="detail.image_urls"
            :initial-index="index"
            fit="cover"
            preview-teleported
          />
        </div>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ categoryName(detail.category_id) }}</el-descriptions-item>
          <el-descriptions-item label="单价">¥{{ detail.price }}</el-descriptions-item>
          <el-descriptions-item label="单位">{{ detail.unit }}</el-descriptions-item>
          <el-descriptions-item label="条码">{{ detail.barcode || '—' }}</el-descriptions-item>
          <el-descriptions-item label="库存">{{ detail.stock_qty }}</el-descriptions-item>
          <el-descriptions-item label="低库存预警">{{ detail.low_stock_threshold }}</el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="detail.is_active ? 'success' : 'info'" size="small">
              {{ detail.is_active ? '在售' : '停用' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '—' }}</el-descriptions-item>
        </el-descriptions>
        <div class="detail-actions">
          <el-button type="primary" @click="editFromDetail">编辑</el-button>
          <el-button v-if="detail.is_active" type="danger" plain @click="deactivate(detail)">停用</el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="skuDialog" :title="editingSkuId ? '编辑商品' : '新建商品'" width="640px" destroy-on-close>
      <el-form ref="skuFormRef" :model="skuForm" :rules="skuRules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="skuForm.name" placeholder="如：蛋白粉 500g" maxlength="128" />
        </el-form-item>
        <el-form-item label="价格" prop="price">
          <el-input v-model="skuForm.price" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="skuForm.unit" maxlength="16" />
        </el-form-item>
        <el-form-item label="条码">
          <el-input v-model="skuForm.barcode" maxlength="64" placeholder="可选" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="skuForm.category_id" clearable style="width: 100%" placeholder="请选择分类">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="图片">
          <el-upload
            :class="{ 'hide-uploader': skuForm.image_urls.length >= SKU_IMAGE_LIMIT }"
            list-type="picture-card"
            accept=".jpg,.jpeg,.png,.webp"
            :limit="SKU_IMAGE_LIMIT"
            :file-list="imageFileList"
            :http-request="uploadSkuImage"
            :on-preview="(file: UploadFile) => previewUploadFile(file, imageFileList)"
            :on-remove="removeSkuImage"
            :on-exceed="onImageExceed"
            :disabled="uploading"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
          <p class="hint">最多 {{ SKU_IMAGE_LIMIT }} 张，单张不超过 8MB，支持 JPG / PNG / WEBP。</p>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="skuForm.remark"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="规格、口味、陈列位置等，选填"
          />
        </el-form-item>
        <el-form-item label="低库存预警">
          <el-input-number v-model="skuForm.low_stock_threshold" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用售卖">
          <el-switch v-model="skuForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="skuDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveSku">保存</el-button>
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
.sku-barcode {
  margin-top: 2px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.sku-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}
.sku-thumb {
  width: 40px;
  height: 40px;
  object-fit: cover;
  border-radius: 6px;
  background: var(--el-fill-color-light);
  flex-shrink: 0;
}
.hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
.hide-uploader :deep(.el-upload--picture-card) {
  display: none;
}
.detail-hero {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
.detail-hero :deep(.el-image) {
  width: 96px;
  height: 96px;
  border-radius: 8px;
  overflow: hidden;
  background: var(--el-fill-color-light);
  cursor: zoom-in;
}
.detail-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
