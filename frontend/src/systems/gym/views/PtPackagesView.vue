<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { merchantsWithSystem } from '../../../core/nav/systems'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Member = { id: number; name: string; phone: string }
type Product = {
  id: number
  name: string
  price: string
  session_count: number
  valid_days: number
  is_active: boolean
}
type Pkg = {
  id: number
  member_id: number
  product_id: number
  status: string
  remaining_sessions: number
}

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const products = ref<Product[]>([])
const packages = ref<Pkg[]>([])
const merchantId = ref<number | undefined>()
const loading = ref(false)

const productDialog = ref(false)
const sellDialog = ref(false)
const submitting = ref(false)
const productFormRef = ref<FormInstance>()
const sellFormRef = ref<FormInstance>()

const productForm = reactive({
  name: '',
  price: '1000',
  session_count: 10,
  valid_days: 90,
})
const sell = reactive({
  member_id: undefined as number | undefined,
  product_id: undefined as number | undefined,
})

const productRules: FormRules = {
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

const sellRules: FormRules = {
  member_id: [{ required: true, message: '请选择会员', trigger: 'change' }],
  product_id: [{ required: true, message: '请选择课包', trigger: 'change' }],
}

function memberName(id: number, row?: { member?: { name: string; phone: string } | null }) {
  if (row?.member) return `${row.member.name} ${row.member.phone}`
  const m = members.value.find((x) => x.id === id)
  return m ? `${m.name} ${m.phone}` : `#${id}`
}

function productName(id: number) {
  return products.value.find((p) => p.id === id)?.name || `#${id}`
}

function statusLabel(s: string) {
  return { active: '使用中', exhausted: '已用尽', expired: '已过期' }[s] || s
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
    const [p, pkgs] = await Promise.all([
      http.get('/pt-products', { params: { merchant_id: merchantId.value } }),
      http.get('/pt-packages', {
        params: { merchant_id: merchantId.value, page: 1, page_size: 100 },
      }),
    ])
    products.value = p.data
    packages.value = pkgs.data.items
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openProductDialog() {
  productForm.name = ''
  productForm.price = '1000'
  productForm.session_count = 10
  productForm.valid_days = 90
  productFormRef.value?.clearValidate()
  productDialog.value = true
}

async function createProduct() {
  const ok = await productFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/pt-products', {
      merchant_id: merchantId.value,
      ...productForm,
      price: productForm.price,
      all_coaches: true,
    })
    ElMessage.success('课包商品已创建')
    productDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openSellDialog() {
  sell.member_id = undefined
  sell.product_id = products.value.find((x) => x.is_active)?.id
  sellFormRef.value?.clearValidate()
  sellDialog.value = true
}

async function sellPackage() {
  const ok = await sellFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    const { data: order } = await http.post('/pt-packages/purchase', {
      merchant_id: merchantId.value,
      member_id: sell.member_id,
      product_id: sell.product_id,
    })
    await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
    ElMessage.success('售课并收款成功')
    sellDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '售卖失败')
  } finally {
    submitting.value = false
  }
}

async function consume(id: number) {
  await http.post(`/pt-packages/${id}/consume`)
  ElMessage.success('已核销 1 课时')
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>私教课包</h3>
      <div class="toolbar-actions">
        <el-button type="primary" plain @click="openProductDialog">新建课包商品</el-button>
        <el-button type="primary" @click="openSellDialog">售卖课包</el-button>
      </div>
    </div>

    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <h3 class="section-title">课包商品</h3>
    <el-table :data="products.filter((x) => x.is_active)" v-loading="loading" stripe style="margin-bottom: 28px">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="price" label="价格" width="120" />
      <el-table-column prop="session_count" label="课时" width="90" />
      <el-table-column prop="valid_days" label="有效天" width="90" />
    </el-table>

    <h3 class="section-title">会员课包</h3>
    <el-table :data="packages" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="会员" width="180">
        <template #default="{ row }">{{ memberName(row.member_id, row) }}</template>
      </el-table-column>
      <el-table-column label="课包" width="160">
        <template #default="{ row }">{{ productName(row.product_id) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="remaining_sessions" label="剩余课时" width="110" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="row.status === 'active'" link type="primary" @click="consume(row.id)">核销</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建课包商品弹窗 -->
    <el-dialog v-model="productDialog" title="新建课包商品" width="480px" destroy-on-close>
      <el-form ref="productFormRef" :model="productForm" :rules="productRules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="productForm.name" placeholder="如：私教 10 次卡" maxlength="128" />
        </el-form-item>
        <el-form-item label="价格" prop="price">
          <el-input v-model="productForm.price" placeholder="0.00" />
        </el-form-item>
        <el-form-item label="课时">
          <el-input-number v-model="productForm.session_count" :min="1" style="width: 100%" />
        </el-form-item>
        <el-form-item label="有效天">
          <el-input-number v-model="productForm.valid_days" :min="1" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="productDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createProduct">创建</el-button>
      </template>
    </el-dialog>

    <!-- 售卖课包弹窗 -->
    <el-dialog v-model="sellDialog" title="售卖课包并收款" width="480px" destroy-on-close>
      <el-form ref="sellFormRef" :model="sell" :rules="sellRules" label-width="90px">
        <el-form-item label="会员" prop="member_id">
          <el-select v-model="sell.member_id" filterable style="width: 100%">
            <el-option v-for="x in members" :key="x.id" :label="`${x.name} ${x.phone}`" :value="x.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="课包" prop="product_id">
          <el-select v-model="sell.product_id" style="width: 100%">
            <el-option
              v-for="p in products.filter((x) => x.is_active)"
              :key="p.id"
              :label="`${p.name} ¥${p.price}`"
              :value="p.id"
            />
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
        <el-button type="primary" :loading="submitting" @click="sellPackage">售卖并收款</el-button>
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
</style>
