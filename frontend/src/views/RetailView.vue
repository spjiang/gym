<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Merchant = { id: number; name: string }
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

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const categories = ref<Category[]>([])
const skus = ref<Sku[]>([])
const lowOnly = ref(false)
const merchantId = ref<number | undefined>()

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
  quantity: 1,
  target_qty: 0,
  note: '',
})
type MemberCoupon = { id: number; member_id: number; template_id: number; status: string }

const sellForm = reactive({
  member_id: undefined as number | undefined,
  sku_id: undefined as number | undefined,
  quantity: 1,
  member_coupon_id: undefined as number | undefined,
})
const unusedCoupons = ref<MemberCoupon[]>([])

async function loadUnusedCoupons() {
  sellForm.member_coupon_id = undefined
  unusedCoupons.value = []
  if (!merchantId.value || !sellForm.member_id) return
  const { data } = await http.get('/coupons/member-coupons', {
    params: {
      merchant_id: merchantId.value,
      member_id: sellForm.member_id,
      status: 'unused',
    },
  })
  unusedCoupons.value = data
}

async function refresh() {
  const [m, mem] = await Promise.all([http.get('/merchants'), http.get('/members')])
  merchants.value = m.data
  members.value = mem.data
  if (!merchantId.value && m.data[0]) merchantId.value = m.data[0].id
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
}

async function createCategory() {
  await http.post('/retail/categories', { merchant_id: merchantId.value, name: catForm.name })
  ElMessage.success('分类已创建')
  catForm.name = ''
  await refresh()
}

async function createSku() {
  await http.post('/retail/skus', {
    merchant_id: merchantId.value,
    ...skuForm,
    category_id: skuForm.category_id ?? null,
  })
  ElMessage.success('SKU 已创建')
  await refresh()
}

async function stockIn() {
  await http.post(`/retail/skus/${stockForm.sku_id}/stock/in`, {
    quantity: stockForm.quantity,
    note: stockForm.note,
  })
  ElMessage.success('入库成功')
  await refresh()
}

async function stockOut() {
  await http.post(`/retail/skus/${stockForm.sku_id}/stock/out`, {
    quantity: stockForm.quantity,
    note: stockForm.note,
  })
  ElMessage.success('出库成功')
  await refresh()
}

async function stockAdjust() {
  await http.post(`/retail/skus/${stockForm.sku_id}/stock/adjust`, {
    target_qty: stockForm.target_qty,
    note: stockForm.note,
  })
  ElMessage.success('盘点成功')
  await refresh()
}

async function sell() {
  const { data: order } = await http.post('/retail/orders', {
    merchant_id: merchantId.value,
    member_id: sellForm.member_id ?? null,
    items: [{ sku_id: sellForm.sku_id, quantity: sellForm.quantity }],
    member_coupon_id: sellForm.member_coupon_id ?? null,
  })
  await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
  ElMessage.success(`零售收款成功，实付 ¥${order.amount}`)
  await refresh()
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

    <el-card header="分类" style="margin-bottom: 12px">
      <el-form inline>
        <el-input v-model="catForm.name" placeholder="分类名" style="width: 160px; margin-right: 8px" />
        <el-button type="primary" @click="createCategory">新建分类</el-button>
      </el-form>
    </el-card>

    <el-card header="新建 SKU" style="margin-bottom: 12px">
      <el-form inline>
        <el-form-item label="名称"><el-input v-model="skuForm.name" /></el-form-item>
        <el-form-item label="价格"><el-input v-model="skuForm.price" style="width: 100px" /></el-form-item>
        <el-form-item label="单位"><el-input v-model="skuForm.unit" style="width: 80px" /></el-form-item>
        <el-form-item label="分类">
          <el-select v-model="skuForm.category_id" clearable style="width: 140px">
            <el-option v-for="c in categories" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="预警">
          <el-input-number v-model="skuForm.low_stock_threshold" :min="0" />
        </el-form-item>
        <el-button type="primary" @click="createSku">创建</el-button>
      </el-form>
    </el-card>

    <el-card header="库存操作" style="margin-bottom: 12px">
      <el-form inline>
        <el-select v-model="stockForm.sku_id" placeholder="SKU" style="width: 180px" filterable>
          <el-option v-for="s in skus" :key="s.id" :label="`${s.name}(${s.stock_qty})`" :value="s.id" />
        </el-select>
        <el-input-number v-model="stockForm.quantity" :min="1" style="margin: 0 8px" />
        <el-input v-model="stockForm.note" placeholder="备注" style="width: 120px; margin-right: 8px" />
        <el-button @click="stockIn">入库</el-button>
        <el-button @click="stockOut">出库</el-button>
        <el-input-number v-model="stockForm.target_qty" :min="0" style="margin: 0 8px" />
        <el-button @click="stockAdjust">盘点为目标</el-button>
      </el-form>
    </el-card>

    <el-card header="零售收银" style="margin-bottom: 12px">
      <el-form inline>
        <el-select
          v-model="sellForm.member_id"
          clearable
          filterable
          placeholder="会员(可选)"
          style="width: 180px"
          @change="loadUnusedCoupons"
        >
          <el-option v-for="x in members" :key="x.id" :label="`${x.name} ${x.phone}`" :value="x.id" />
        </el-select>
        <el-select v-model="sellForm.sku_id" filterable placeholder="商品" style="width: 180px; margin: 0 8px">
          <el-option
            v-for="s in skus.filter((x) => x.is_active)"
            :key="s.id"
            :label="`${s.name} ¥${s.price} 库存${s.stock_qty}`"
            :value="s.id"
          />
        </el-select>
        <el-input-number v-model="sellForm.quantity" :min="1" />
        <el-select
          v-model="sellForm.member_coupon_id"
          clearable
          placeholder="优惠券"
          style="width: 140px; margin-left: 8px"
          :disabled="!sellForm.member_id"
        >
          <el-option
            v-for="c in unusedCoupons"
            :key="c.id"
            :label="`券#${c.id}`"
            :value="c.id"
          />
        </el-select>
        <el-button type="primary" style="margin-left: 8px" @click="sell">下单并收款</el-button>
      </el-form>
    </el-card>

    <el-table :data="skus" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="price" label="单价" width="90" />
      <el-table-column prop="stock_qty" label="库存" width="80" />
      <el-table-column prop="low_stock_threshold" label="预警" width="80" />
      <el-table-column prop="is_active" label="启用" width="80">
        <template #default="{ row }">{{ row.is_active ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100">
        <template #default="{ row }">
          <el-button v-if="row.is_active" link type="danger" @click="deactivate(row.id)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
