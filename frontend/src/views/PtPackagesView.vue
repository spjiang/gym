<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Merchant = { id: number; name: string }
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

async function refresh() {
  const [m, mem] = await Promise.all([http.get('/merchants'), http.get('/members')])
  merchants.value = m.data
  members.value = mem.data
  if (!merchantId.value && m.data[0]) merchantId.value = m.data[0].id
  if (!merchantId.value) return
  const [p, pkgs] = await Promise.all([
    http.get('/pt-products', { params: { merchant_id: merchantId.value } }),
    http.get('/pt-packages', { params: { merchant_id: merchantId.value } }),
  ])
  products.value = p.data
  packages.value = pkgs.data
}

async function createProduct() {
  await http.post('/pt-products', {
    merchant_id: merchantId.value,
    ...productForm,
    price: productForm.price,
    all_coaches: true,
  })
  ElMessage.success('课包商品已创建')
  await refresh()
}

async function sellPackage() {
  const { data: order } = await http.post('/pt-packages/purchase', {
    merchant_id: merchantId.value,
    member_id: sell.member_id,
    product_id: sell.product_id,
  })
  await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
  ElMessage.success('售课并收款成功')
  await refresh()
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
    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-card header="新建课包商品" style="margin-bottom: 16px">
      <el-form inline>
        <el-form-item label="名称"><el-input v-model="productForm.name" /></el-form-item>
        <el-form-item label="价格"><el-input v-model="productForm.price" /></el-form-item>
        <el-form-item label="课时">
          <el-input-number v-model="productForm.session_count" :min="1" />
        </el-form-item>
        <el-form-item label="有效天">
          <el-input-number v-model="productForm.valid_days" :min="1" />
        </el-form-item>
        <el-button type="primary" @click="createProduct">创建</el-button>
      </el-form>
    </el-card>

    <el-card header="售卖课包" style="margin-bottom: 16px">
      <el-form inline>
        <el-form-item label="会员">
          <el-select v-model="sell.member_id" filterable style="width: 200px">
            <el-option v-for="x in members" :key="x.id" :label="`${x.name} ${x.phone}`" :value="x.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="课包">
          <el-select v-model="sell.product_id" style="width: 200px">
            <el-option
              v-for="p in products.filter((x) => x.is_active)"
              :key="p.id"
              :label="`${p.name} ¥${p.price}`"
              :value="p.id"
            />
          </el-select>
        </el-form-item>
        <el-button type="primary" @click="sellPackage">售卖并线下收款</el-button>
      </el-form>
    </el-card>

    <h3>会员课包</h3>
    <el-table :data="packages" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="member_id" label="会员" width="90" />
      <el-table-column prop="product_id" label="商品" width="90" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="remaining_sessions" label="剩余课时" width="110" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button v-if="row.status === 'active'" link type="primary" @click="consume(row.id)">核销</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
