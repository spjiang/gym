<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Order = { id: number; title: string; amount: string; status: string; merchant_id: number }
type Merchant = { id: number; name: string }

const orders = ref<Order[]>([])
const merchants = ref<Merchant[]>([])
const form = reactive({
  merchant_id: undefined as number | undefined,
  title: '',
  amount: '99.00',
  order_type: 'retail',
})

async function load() {
  const [o, m] = await Promise.all([http.get('/orders'), http.get('/merchants')])
  orders.value = o.data
  merchants.value = m.data
  if (!form.merchant_id && merchants.value[0]) form.merchant_id = merchants.value[0].id
}

async function create() {
  await http.post('/orders', form)
  ElMessage.success('订单已创建')
  form.title = ''
  await load()
}

async function payOffline(id: number) {
  await http.post(`/orders/${id}/pay/offline`, { channel: 'offline_cash' })
  ElMessage.success('线下收款成功')
  await load()
}

async function refund(id: number) {
  await http.post(`/orders/${id}/refund`)
  ElMessage.success('已退款')
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <h3>创建订单（线下收款）</h3>
    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="form.merchant_id" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="标题"><el-input v-model="form.title" /></el-form-item>
      <el-form-item label="金额"><el-input v-model="form.amount" /></el-form-item>
      <el-button type="primary" @click="create">创建</el-button>
    </el-form>

    <el-table :data="orders" style="margin-top: 16px">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="title" label="标题" />
      <el-table-column prop="amount" label="金额" />
      <el-table-column prop="status" label="状态" />
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" :disabled="row.status !== 'pending'" @click="payOffline(row.id)">
            线下收款
          </el-button>
          <el-button size="small" :disabled="row.status !== 'paid'" @click="refund(row.id)">退款</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
