<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules, type UploadFile, type UploadRequestOptions, type UploadUserFile } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import http from '../../../core/api/http'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'
import {
  memberCouponMeta,
  memberCouponName,
  moneyLabel,
  quoteCoupon,
  type MemberCoupon,
} from '../couponUi'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Category = { id: number; name: string }
type Sku = {
  id: number
  merchant_id?: number
  name: string
  price: string
  unit: string
  barcode?: string | null
  stock_qty: number
  low_stock_threshold: number
  is_active: boolean
  category_id: number | null
  promo_price?: string | null
  effective_price?: string | null
  remark?: string | null
  image_urls?: string[]
}
type Movement = {
  id: number
  sku_id: number
  movement_type: string
  quantity_delta: number
  stock_after: number
  order_id: number | null
  note: string | null
  created_at: string
  actor_name: string | null
}
type Page<T> = { items: T[]; total: number; page: number; page_size: number }

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const categories = ref<Category[]>([])
const skus = ref<Sku[]>([])
const lowOnly = ref(false)
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const optionSkus = ref<Sku[]>([])
const query = reactive({
  q: '',
  category_id: undefined as number | undefined,
  status: '' as '' | 'active' | 'inactive',
})

const stockDialog = ref(false)
const sellDialog = ref(false)
const editDialog = ref(false)
const detailVisible = ref(false)
const submitting = ref(false)
const stockFormRef = ref<FormInstance>()
const sellFormRef = ref<FormInstance>()
const editFormRef = ref<FormInstance>()
const detail = ref<Sku | null>(null)
const movements = ref<Movement[]>([])
const movementsLoading = ref(false)
const movementTotal = ref(0)
const movementPage = ref(1)
const movementPageSize = ref(10)
const editing = ref<Sku | null>(null)
const editForm = reactive({
  name: '',
  price: '',
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
const SKU_IMAGE_LIMIT = 9

const stockForm = reactive({
  sku_id: undefined as number | undefined,
  mode: 'in' as 'in' | 'out' | 'adjust',
  quantity: 1,
  target_qty: 0,
  note: '',
})

const sellForm = reactive({
  member_id: undefined as number | undefined,
  sku_id: undefined as number | undefined,
  quantity: 1,
  member_coupon_id: undefined as number | undefined,
})
const unusedCoupons = ref<MemberCoupon[]>([])

const stockRules: FormRules = {
  sku_id: [{ required: true, message: '请选择 SKU', trigger: 'change' }],
}

const sellRules: FormRules = {
  sku_id: [{ required: true, message: '请选择商品', trigger: 'change' }],
  quantity: [{ required: true, message: '请填写数量', trigger: 'change' }],
}

const editRules: FormRules = {
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

const stockModeLabel = computed(() => ({ in: '入库', out: '出库', adjust: '盘点' })[stockForm.mode])

const selectedSellSku = computed(
  () => optionSkus.value.find((s) => s.id === sellForm.sku_id) || skus.value.find((s) => s.id === sellForm.sku_id),
)
const selectedSellCoupon = computed(() => unusedCoupons.value.find((c) => c.id === sellForm.member_coupon_id))
const sellOriginal = computed(() => Number(selectedSellSku.value?.price ?? 0) * Number(sellForm.quantity || 0))
const sellQuote = computed(() => quoteCoupon(sellOriginal.value, selectedSellCoupon.value, 'retail'))

function categoryName(id: number | null | undefined) {
  if (!id) return '—'
  return categories.value.find((c) => c.id === id)?.name || '—'
}

function movementLabel(t: string) {
  return { in: '入库', out: '出库', adjust: '盘点', sale: '销售', refund: '退货' }[t] || t
}

function fmtDateTime(iso: string | null | undefined) {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadUnusedCoupons() {
  sellForm.member_coupon_id = undefined
  unusedCoupons.value = []
  if (!merchantId.value || !sellForm.member_id) return
  const { data } = await http.get('/coupons/member-coupons', {
    params: {
      merchant_id: merchantId.value,
      member_id: sellForm.member_id,
      status: 'unused',
      page: 1,
      page_size: 100,
    },
  })
  unusedCoupons.value = data.items
}

async function refresh() {
  loading.value = true
  try {
    const [m, mem] = await Promise.all([
      http.get('/merchants'),
      http.get('/members', { params: { page: 1, page_size: 100 } }),
    ])
    merchants.value = merchantsWithSystem(m.data, 'gym')
    members.value = mem.data.items
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const [c, s, opts] = await Promise.all([
      http.get('/retail/categories', { params: { merchant_id: merchantId.value, page: 1, page_size: 100 } }),
      http.get('/retail/skus', {
        params: {
          merchant_id: merchantId.value,
          q: query.q.trim() || undefined,
          category_id: query.category_id,
          is_active: query.status === 'active' ? true : query.status === 'inactive' ? false : undefined,
          low_stock: lowOnly.value || undefined,
          page: page.value,
          page_size: pageSize.value,
        },
      }),
      http.get('/retail/skus', {
        params: { merchant_id: merchantId.value, page: 1, page_size: 100 },
      }),
    ])
    categories.value = c.data.items
    skus.value = s.data.items
    total.value = s.data.total
    optionSkus.value = opts.data.items
    await loadUnusedCoupons()
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
  lowOnly.value = false
  page.value = 1
  void refresh()
}

async function loadMovements(skuId: number) {
  movementsLoading.value = true
  try {
    const { data } = await http.get<Page<Movement>>('/retail/movements', {
      params: {
        sku_id: skuId,
        merchant_id: merchantId.value,
        page: movementPage.value,
        page_size: movementPageSize.value,
      },
    })
    movements.value = data.items
    movementTotal.value = data.total
  } catch (e: unknown) {
    movements.value = []
    movementTotal.value = 0
    ElMessage.error(e instanceof Error ? e.message : '加载库存流水失败')
  } finally {
    movementsLoading.value = false
  }
}

function onMovementPageChange() {
  if (detail.value) void loadMovements(detail.value.id)
}

function onMovementPageSizeChange() {
  movementPage.value = 1
  onMovementPageChange()
}

async function openDetail(row: Sku) {
  detail.value = row
  detailVisible.value = true
  movements.value = []
  movementTotal.value = 0
  movementPage.value = 1
  try {
    const { data } = await http.get<Sku>(`/retail/skus/${row.id}`)
    detail.value = data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载详情失败')
  }
  await loadMovements(row.id)
}

function openEdit(row: Sku) {
  editing.value = row
  editForm.name = row.name
  editForm.price = row.price
  editForm.unit = row.unit || '件'
  editForm.barcode = row.barcode || ''
  editForm.category_id = row.category_id ?? undefined
  editForm.low_stock_threshold = row.low_stock_threshold
  editForm.is_active = row.is_active
  editForm.remark = row.remark || ''
  editForm.image_urls = [...(row.image_urls || [])]
  syncEditImages()
  editFormRef.value?.clearValidate()
  editDialog.value = true
}

function syncEditImages() {
  imageFileList.value = editForm.image_urls.map((url, i) => ({ name: `图${i + 1}`, url, uid: i + 1 }))
}

async function uploadSkuImage(opt: UploadRequestOptions) {
  if (editForm.image_urls.length >= SKU_IMAGE_LIMIT) {
    ElMessage.warning(`最多上传 ${SKU_IMAGE_LIMIT} 张图片`)
    return
  }
  const fd = new FormData()
  fd.append('file', opt.file)
  uploading.value = true
  try {
    const { data } = await http.post<{ url: string }>('/uploads', fd, { timeout: 30000 })
    editForm.image_urls.push(data.url)
    syncEditImages()
    opt.onSuccess(data)
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '上传失败')
  } finally {
    uploading.value = false
  }
}

function removeSkuImage(file: UploadFile) {
  editForm.image_urls = editForm.image_urls.filter((url) => url !== file.url)
  syncEditImages()
}

function onImageExceed() {
  ElMessage.warning(`最多上传 ${SKU_IMAGE_LIMIT} 张图片`)
}

async function saveEdit() {
  const ok = await editFormRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid || !editing.value) return
  submitting.value = true
  try {
    const { data } = await http.patch<Sku>(`/retail/skus/${editing.value.id}`, {
      merchant_id: mid,
      name: editForm.name.trim(),
      price: editForm.price,
      unit: editForm.unit.trim() || '件',
      barcode: editForm.barcode.trim() || null,
      category_id: editForm.category_id ?? null,
      low_stock_threshold: editForm.low_stock_threshold,
      is_active: editForm.is_active,
      remark: editForm.remark.trim() || null,
      image_urls: editForm.image_urls,
    })
    ElMessage.success('商品已更新')
    editDialog.value = false
    if (detail.value?.id === data.id) detail.value = data
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

function openStockDialog(row?: Sku) {
  if (!requireMerchant()) return
  stockForm.sku_id = row?.id ?? skus.value[0]?.id
  stockForm.mode = 'in'
  stockForm.quantity = 1
  stockForm.target_qty = 0
  stockForm.note = ''
  stockFormRef.value?.clearValidate()
  stockDialog.value = true
}

async function submitStock() {
  const ok = await stockFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    if (stockForm.mode === 'in') {
      await http.post(`/retail/skus/${stockForm.sku_id}/stock/in`, {
        quantity: stockForm.quantity,
        note: stockForm.note,
      })
      ElMessage.success('入库成功')
    } else if (stockForm.mode === 'out') {
      await http.post(`/retail/skus/${stockForm.sku_id}/stock/out`, {
        quantity: stockForm.quantity,
        note: stockForm.note,
      })
      ElMessage.success('出库成功')
    } else {
      await http.post(`/retail/skus/${stockForm.sku_id}/stock/adjust`, {
        target_qty: stockForm.target_qty,
        note: stockForm.note,
      })
      ElMessage.success('盘点成功')
    }
    stockDialog.value = false
    if (detail.value && stockForm.sku_id === detail.value.id) await openDetail(detail.value)
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  } finally {
    submitting.value = false
  }
}

function openSellDialog(row?: Sku) {
  if (!requireMerchant()) return
  sellForm.member_id = undefined
  sellForm.sku_id = row?.id ?? skus.value.find((x) => x.is_active)?.id
  sellForm.quantity = 1
  sellForm.member_coupon_id = undefined
  unusedCoupons.value = []
  sellFormRef.value?.clearValidate()
  sellDialog.value = true
}

async function sell() {
  const ok = await sellFormRef.value?.validate().catch(() => false)
  if (!ok) return
  if (!sellQuote.value.usable) {
    ElMessage.warning(sellQuote.value.reason || '当前优惠券不可用')
    return
  }
  submitting.value = true
  try {
    const { data: order } = await http.post('/retail/orders', {
      merchant_id: merchantId.value,
      member_id: sellForm.member_id ?? null,
      items: [{ sku_id: sellForm.sku_id, quantity: sellForm.quantity }],
      member_coupon_id: sellForm.member_coupon_id ?? null,
    })
    await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
    ElMessage.success(`零售收款成功，实付 ¥${order.amount}`)
    sellDialog.value = false
    if (detail.value && sellForm.sku_id === detail.value.id) await openDetail(detail.value)
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '收款失败')
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
    if (detail.value?.id === row.id) detail.value = { ...detail.value, is_active: false }
    await refresh()
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
        <h3>库存收银</h3>
        <p class="lead">入库出库、盘点与前台收银。商品档案请到「零售管理 → 商品管理」。</p>
      </div>
      <div class="toolbar-actions">
        <el-button @click="openStockDialog">库存操作</el-button>
        <el-button type="primary" @click="openSellDialog">零售收银</el-button>
      </div>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input
          v-model="query.q"
          clearable
          placeholder="商品名称 / 条码"
          style="width: 200px"
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
        <el-checkbox v-model="lowOnly">仅低库存</el-checkbox>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="skus" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="商品" min-width="200">
        <template #default="{ row }">
          <div class="sku-cell">
            <img v-if="row.image_urls?.[0]" class="sku-thumb" :src="row.image_urls[0]" alt="" />
            <div>
              <el-button link type="primary" @click="openDetail(row)">{{ row.name }}</el-button>
              <div v-if="row.barcode" class="card-spec">条码 {{ row.barcode }}</div>
            </div>
          </div>
        </template>
      </el-table-column>
      <el-table-column label="分类" width="120">
        <template #default="{ row }">{{ categoryName(row.category_id) }}</template>
      </el-table-column>
      <el-table-column label="单价" width="110">
        <template #default="{ row }">{{ moneyLabel(row.effective_price || row.price) }}</template>
      </el-table-column>
      <el-table-column prop="unit" label="单位" width="70" />
      <el-table-column label="库存" width="90">
        <template #default="{ row }">
          <span :class="{ low: row.stock_qty <= row.low_stock_threshold }">{{ row.stock_qty }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="low_stock_threshold" label="预警线" width="90" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '在售' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="260" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openDetail(row)">详情</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link type="primary" @click="openStockDialog(row)">库存</el-button>
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

    <el-drawer v-model="detailVisible" title="商品详情" size="520px">
      <template v-if="detail">
        <h4 class="detail-section">商品</h4>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="ID">{{ detail.id }}</el-descriptions-item>
          <el-descriptions-item label="名称">{{ detail.name }}</el-descriptions-item>
          <el-descriptions-item label="分类">{{ categoryName(detail.category_id) }}</el-descriptions-item>
          <el-descriptions-item label="单价">{{ moneyLabel(detail.effective_price || detail.price) }}</el-descriptions-item>
          <el-descriptions-item label="标价">{{ moneyLabel(detail.price) }}</el-descriptions-item>
          <el-descriptions-item label="单位">{{ detail.unit }}</el-descriptions-item>
          <el-descriptions-item label="条码">{{ detail.barcode || '—' }}</el-descriptions-item>
          <el-descriptions-item label="库存">
            <span :class="{ low: detail.stock_qty <= detail.low_stock_threshold }">{{ detail.stock_qty }}</span>
          </el-descriptions-item>
          <el-descriptions-item label="预警线">{{ detail.low_stock_threshold }}</el-descriptions-item>
          <el-descriptions-item label="状态">{{ detail.is_active ? '在售' : '停用' }}</el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '—' }}</el-descriptions-item>
          <el-descriptions-item v-if="detail.image_urls?.length" label="图片">
            <div class="detail-images">
              <img v-for="url in detail.image_urls" :key="url" :src="url" alt="" />
            </div>
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="detail-section">库存流水</h4>
        <el-table :data="movements" v-loading="movementsLoading" size="small" stripe empty-text="暂无库存流水">
          <el-table-column label="时间" min-width="150">
            <template #default="{ row }">{{ fmtDateTime(row.created_at) }}</template>
          </el-table-column>
          <el-table-column label="类型" width="80">
            <template #default="{ row }">{{ movementLabel(row.movement_type) }}</template>
          </el-table-column>
          <el-table-column label="变动" width="80">
            <template #default="{ row }">{{ row.quantity_delta > 0 ? `+${row.quantity_delta}` : row.quantity_delta }}</template>
          </el-table-column>
          <el-table-column label="结存" width="70" prop="stock_after" />
          <el-table-column label="操作人" min-width="90">
            <template #default="{ row }">{{ row.actor_name || '—' }}</template>
          </el-table-column>
        </el-table>
        <div class="pager pager--drawer">
          <el-pagination
            v-model:current-page="movementPage"
            v-model:page-size="movementPageSize"
            :total="movementTotal"
            :page-sizes="[10, 20, 50]"
            :pager-count="5"
            small
            background
            layout="total, sizes, prev, pager, next"
            @current-change="onMovementPageChange"
            @size-change="onMovementPageSizeChange"
          />
        </div>

        <div class="detail-actions">
          <el-button @click="openStockDialog(detail)">库存操作</el-button>
          <el-button v-if="detail.is_active" type="primary" @click="openSellDialog(detail)">收银</el-button>
          <el-button type="primary" @click="openEdit(detail)">编辑</el-button>
          <el-button v-if="detail.is_active" type="danger" plain @click="deactivate(detail)">停用</el-button>
          <el-button @click="detailVisible = false">关闭</el-button>
        </div>
      </template>
    </el-drawer>

    <el-dialog v-model="editDialog" title="编辑商品" width="640px" destroy-on-close>
      <el-form ref="editFormRef" :model="editForm" :rules="editRules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="editForm.name" maxlength="128" />
        </el-form-item>
        <el-form-item label="单价" prop="price">
          <el-input v-model="editForm.price" />
        </el-form-item>
        <el-form-item label="单位">
          <el-input v-model="editForm.unit" maxlength="16" />
        </el-form-item>
        <el-form-item label="条码">
          <el-input v-model="editForm.barcode" maxlength="64" placeholder="可选" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="editForm.category_id" clearable style="width: 100%">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="图片">
          <el-upload
            :class="{ 'hide-uploader': editForm.image_urls.length >= SKU_IMAGE_LIMIT }"
            list-type="picture-card"
            accept=".jpg,.jpeg,.png,.webp"
            :limit="SKU_IMAGE_LIMIT"
            :file-list="imageFileList"
            :http-request="uploadSkuImage"
            :on-remove="removeSkuImage"
            :on-exceed="onImageExceed"
            :disabled="uploading"
          >
            <el-icon><Plus /></el-icon>
          </el-upload>
          <p class="form-hint">最多 {{ SKU_IMAGE_LIMIT }} 张，单张不超过 8MB，支持 JPG / PNG / WEBP。</p>
        </el-form-item>
        <el-form-item label="备注">
          <el-input
            v-model="editForm.remark"
            type="textarea"
            :rows="3"
            maxlength="500"
            show-word-limit
            placeholder="规格、口味、陈列位置等，选填"
          />
        </el-form-item>
        <el-form-item label="低库存预警">
          <el-input-number v-model="editForm.low_stock_threshold" :min="0" style="width: 100%" />
        </el-form-item>
        <el-form-item label="启用售卖">
          <el-switch v-model="editForm.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveEdit">保存</el-button>
      </template>
    </el-dialog>

    <!-- 库存操作弹窗 -->
    <el-dialog v-model="stockDialog" :title="`库存操作 · ${stockModeLabel}`" width="480px" destroy-on-close>
      <el-form ref="stockFormRef" :model="stockForm" :rules="stockRules" label-width="90px">
        <el-form-item label="操作类型">
          <el-radio-group v-model="stockForm.mode">
            <el-radio-button value="in">入库</el-radio-button>
            <el-radio-button value="out">出库</el-radio-button>
            <el-radio-button value="adjust">盘点</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="SKU" prop="sku_id">
          <el-select v-model="stockForm.sku_id" filterable style="width: 100%">
            <el-option v-for="s in optionSkus" :key="s.id" :label="`${s.name}（库存 ${s.stock_qty}）`" :value="s.id" />
          </el-select>
        </el-form-item>
        <el-form-item v-if="stockForm.mode !== 'adjust'" label="数量">
          <el-input-number v-model="stockForm.quantity" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item v-else label="目标库存">
          <el-input-number v-model="stockForm.target_qty" :min="0" style="width: 100%" />
          <div class="form-hint">盘点将以目标值校准实际库存</div>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="stockForm.note" placeholder="可选" maxlength="255" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="stockDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="submitStock">提交</el-button>
      </template>
    </el-dialog>

    <!-- 零售收银弹窗 -->
    <el-dialog v-model="sellDialog" title="零售收银" width="500px" destroy-on-close>
      <el-form ref="sellFormRef" :model="sellForm" :rules="sellRules" label-width="90px">
        <el-form-item label="会员">
          <el-select
            v-model="sellForm.member_id"
            clearable
            filterable
            placeholder="会员（可选）"
            style="width: 100%"
            @change="loadUnusedCoupons"
          >
            <el-option v-for="x in members" :key="x.id" :label="`${x.name} ${x.phone}`" :value="x.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="商品" prop="sku_id">
          <el-select v-model="sellForm.sku_id" filterable style="width: 100%">
            <el-option
              v-for="s in optionSkus.filter((x) => x.is_active)"
              :key="s.id"
              :label="`${s.name} ¥${s.price}（库存 ${s.stock_qty}）`"
              :value="s.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="数量" prop="quantity">
          <el-input-number v-model="sellForm.quantity" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="优惠券">
          <el-select
            v-model="sellForm.member_coupon_id"
            clearable
            filterable
            placeholder="会员可用优惠券"
            style="width: 100%"
            :disabled="!sellForm.member_id"
            popper-class="coupon-select-popper"
            :fit-input-width="true"
            teleported
          >
            <el-option
              v-for="c in unusedCoupons"
              :key="c.id"
              :label="memberCouponName(c)"
              :value="c.id"
            >
              <div class="coupon-option">
                <div class="coupon-option__name">{{ memberCouponName(c) }}</div>
                <div class="coupon-option__meta">{{ memberCouponMeta(c) }}</div>
              </div>
            </el-option>
          </el-select>
        </el-form-item>
        <div v-if="selectedSellSku" class="pay-summary">
          <div class="pay-row">
            <span>当前金额</span>
            <span>{{ moneyLabel(sellQuote.original) }}</span>
          </div>
          <div v-if="sellQuote.discount > 0" class="pay-row">
            <span>优惠抵扣</span>
            <span class="pay-off">-{{ moneyLabel(sellQuote.discount) }}</span>
          </div>
          <div class="pay-row pay-row--total">
            <span>支付金额</span>
            <span>{{ moneyLabel(sellQuote.payable) }}</span>
          </div>
          <p v-if="!sellQuote.usable" class="pay-warn">{{ sellQuote.reason }}</p>
        </div>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="提交后将自动生成订单并登记线下收款（现金）"
        />
      </el-form>
      <template #footer>
        <el-button @click="sellDialog = false">取消</el-button>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!sellQuote.usable"
          @click="sell"
        >
          下单并收款 {{ selectedSellSku ? moneyLabel(sellQuote.payable) : '' }}
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
  gap: 12px;
  margin-bottom: 20px;
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

.toolbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.section-title {
  margin: 0 0 12px;
  font-size: 0.95rem;
}

.filters {
  margin-bottom: 8px;
}

.card-spec {
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
.detail-images {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.detail-images img {
  width: 72px;
  height: 72px;
  object-fit: cover;
  border-radius: 6px;
}
.hide-uploader :deep(.el-upload--picture-card) {
  display: none;
}

.detail-section {
  margin: 0 0 10px;
  font-size: 0.9rem;
}

.detail-section + .el-descriptions + .detail-section {
  margin-top: 20px;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 20px;
}

.pager {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}

.pager--drawer {
  flex-wrap: wrap;
}

.low {
  color: var(--admin-danger);
  font-weight: 700;
}

.form-hint {
  width: 100%;
  margin-top: 6px;
  font-size: 0.78rem;
  color: var(--admin-ink-muted);
}

.coupon-option {
  line-height: 1.4;
  padding: 4px 0;
}

.coupon-option__name {
  color: var(--el-text-color-primary);
}

.coupon-option__meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.pay-summary {
  margin: 0 0 16px 90px;
  padding: 12px 14px;
  border-radius: 8px;
  background: var(--el-fill-color-light);
}

.pay-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  font-size: 13px;
  line-height: 1.8;
  color: var(--el-text-color-regular);
}

.pay-row--total {
  margin-top: 4px;
  font-size: 15px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.pay-off {
  color: var(--el-color-danger);
}

.pay-warn {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--el-color-warning);
}
</style>
