<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { merchantsWithSystem } from '../../../core/nav/systems'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Category = { id: number; name: string }
type Sku = {
  id: number
  name: string
  price: string
  unit: string
  stock_qty: number
  low_stock_threshold: number
  is_active: boolean
  category_id: number | null
}
type MemberCoupon = { id: number; member_id: number; template_id: number; status: string }

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const categories = ref<Category[]>([])
const skus = ref<Sku[]>([])
const lowOnly = ref(false)
const merchantId = ref<number | undefined>()
const loading = ref(false)

const catDialog = ref(false)
const skuDialog = ref(false)
const stockDialog = ref(false)
const sellDialog = ref(false)
const submitting = ref(false)
const catFormRef = ref<FormInstance>()
const skuFormRef = ref<FormInstance>()
const stockFormRef = ref<FormInstance>()
const sellFormRef = ref<FormInstance>()

const catForm = reactive({ name: '' })
const skuForm = reactive({
  name: '',
  price: '99.00',
  unit: '件',
  category_id: undefined as number | undefined,
  low_stock_threshold: 5,
})
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

const catRules: FormRules = {
  name: [{ required: true, message: '请填写分类名称', trigger: 'blur' }],
}

const skuRules: FormRules = {
  name: [{ required: true, message: '请填写 SKU 名称', trigger: 'blur' }],
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

const stockRules: FormRules = {
  sku_id: [{ required: true, message: '请选择 SKU', trigger: 'change' }],
}

const sellRules: FormRules = {
  sku_id: [{ required: true, message: '请选择商品', trigger: 'change' }],
  quantity: [{ required: true, message: '请填写数量', trigger: 'change' }],
}

const stockModeLabel = computed(() => ({ in: '入库', out: '出库', adjust: '盘点' })[stockForm.mode])

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
    if (!merchantId.value && merchants.value[0]) merchantId.value = merchants.value[0].id
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = merchants.value[0]?.id
    }
    if (!merchantId.value) return
    const [c, s] = await Promise.all([
      http.get('/retail/categories', { params: { merchant_id: merchantId.value } }),
      http.get('/retail/skus', {
        params: { merchant_id: merchantId.value, low_stock: lowOnly.value || undefined },
      }),
    ])
    categories.value = c.data
    skus.value = s.data
    await loadUnusedCoupons()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openCatDialog() {
  catForm.name = ''
  catFormRef.value?.clearValidate()
  catDialog.value = true
}

async function createCategory() {
  const ok = await catFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/retail/categories', { merchant_id: merchantId.value, name: catForm.name.trim() })
    ElMessage.success('分类已创建')
    catDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openSkuDialog() {
  skuForm.name = ''
  skuForm.price = '99.00'
  skuForm.unit = '件'
  skuForm.category_id = categories.value[0]?.id
  skuForm.low_stock_threshold = 5
  skuFormRef.value?.clearValidate()
  skuDialog.value = true
}

async function createSku() {
  const ok = await skuFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/retail/skus', {
      merchant_id: merchantId.value,
      ...skuForm,
      name: skuForm.name.trim(),
      category_id: skuForm.category_id ?? null,
    })
    ElMessage.success('SKU 已创建')
    skuDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openStockDialog() {
  stockForm.sku_id = skus.value[0]?.id
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
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  } finally {
    submitting.value = false
  }
}

function openSellDialog() {
  sellForm.member_id = undefined
  sellForm.sku_id = skus.value.find((x) => x.is_active)?.id
  sellForm.quantity = 1
  sellForm.member_coupon_id = undefined
  unusedCoupons.value = []
  sellFormRef.value?.clearValidate()
  sellDialog.value = true
}

async function sell() {
  const ok = await sellFormRef.value?.validate().catch(() => false)
  if (!ok) return
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
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '收款失败')
  } finally {
    submitting.value = false
  }
}

async function deactivate(id: number) {
  await http.post(`/retail/skus/${id}/deactivate`)
  ElMessage.success('已停用')
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>零售库存</h3>
      <div class="toolbar-actions">
        <el-button type="primary" plain @click="openCatDialog">新建分类</el-button>
        <el-button type="primary" plain @click="openSkuDialog">新建 SKU</el-button>
        <el-button @click="openStockDialog">库存操作</el-button>
        <el-button type="primary" @click="openSellDialog">零售收银</el-button>
      </div>
    </div>

    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-checkbox v-model="lowOnly" @change="refresh">仅低库存</el-checkbox>
      </el-form-item>
    </el-form>

    <h3 class="section-title">分类</h3>
    <el-table :data="categories" v-loading="loading" stripe style="margin-bottom: 28px">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" />
    </el-table>

    <h3 class="section-title">SKU 列表</h3>
    <el-table :data="skus" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="分类" width="140">
        <template #default="{ row }">
          {{ categories.find((c) => c.id === row.category_id)?.name || '—' }}
        </template>
      </el-table-column>
      <el-table-column prop="price" label="单价" width="100" />
      <el-table-column prop="unit" label="单位" width="70" />
      <el-table-column label="库存" width="90">
        <template #default="{ row }">
          <span :class="{ low: row.stock_qty <= row.low_stock_threshold }">{{ row.stock_qty }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="low_stock_threshold" label="预警线" width="90" />
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button v-if="row.is_active" link type="danger" @click="deactivate(row.id)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建分类弹窗 -->
    <el-dialog v-model="catDialog" title="新建分类" width="440px" destroy-on-close>
      <el-form ref="catFormRef" :model="catForm" :rules="catRules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="catForm.name" placeholder="如：补给 / 饮品" maxlength="64" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="catDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createCategory">创建</el-button>
      </template>
    </el-dialog>

    <!-- 新建 SKU 弹窗 -->
    <el-dialog v-model="skuDialog" title="新建 SKU" width="500px" destroy-on-close>
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
        <el-form-item label="分类">
          <el-select v-model="skuForm.category_id" clearable style="width: 100%">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="低库存预警">
          <el-input-number v-model="skuForm.low_stock_threshold" :min="0" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="skuDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createSku">创建</el-button>
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
            <el-option v-for="s in skus" :key="s.id" :label="`${s.name}（库存 ${s.stock_qty}）`" :value="s.id" />
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
              v-for="s in skus.filter((x) => x.is_active)"
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
            placeholder="会员可用优惠券"
            style="width: 100%"
            :disabled="!sellForm.member_id"
          >
            <el-option v-for="c in unusedCoupons" :key="c.id" :label="`券#${c.id}`" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-alert
          type="info"
          :closable="false"
          show-icon
          title="提交后将自动生成订单并登记线下收款（现金）"
        />
      </el-form>
      <template #footer>
        <el-button @click="sellDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="sell">下单并收款</el-button>
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

.toolbar-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.section-title {
  margin: 0 0 12px;
  font-size: 0.95rem;
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
</style>
