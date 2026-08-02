<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Merchant = { id: number; name: string }
type Member = { id: number; name: string; phone: string }
type Product = { id: number; name: string; price: string; is_active: boolean }
type Membership = {
  id: number
  member_id: number
  product_id: number
  status: string
  ends_at: string | null
  remaining_sessions: number | null
  balance: string | null
}

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const products = ref<Product[]>([])
const memberships = ref<Membership[]>([])
const merchantId = ref<number | undefined>()

type MemberCoupon = { id: number; member_id: number; template_id: number; status: string }

const purchase = reactive({
  member_id: undefined as number | undefined,
  product_id: undefined as number | undefined,
  member_coupon_id: undefined as number | undefined,
})
const renew = reactive({ membership_id: undefined as number | undefined, product_id: undefined as number | undefined })
const unusedCoupons = ref<MemberCoupon[]>([])

async function loadUnusedCoupons() {
  purchase.member_coupon_id = undefined
  unusedCoupons.value = []
  if (!merchantId.value || !purchase.member_id) return
  const { data } = await http.get('/coupons/member-coupons', {
    params: {
      merchant_id: merchantId.value,
      member_id: purchase.member_id,
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
  const [p, ms] = await Promise.all([
    http.get('/membership-products', { params: { merchant_id: merchantId.value } }),
    http.get('/memberships', { params: { merchant_id: merchantId.value } }),
  ])
  products.value = p.data.filter((x: Product) => x.is_active)
  memberships.value = ms.data
  await loadUnusedCoupons()
}

async function doPurchase() {
  const { data: order } = await http.post('/memberships/purchase', {
    member_id: purchase.member_id,
    product_id: purchase.product_id,
    merchant_id: merchantId.value,
    member_coupon_id: purchase.member_coupon_id ?? null,
  })
  await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
  ElMessage.success(`办卡并收款成功，实付 ¥${order.amount}`)
  await refresh()
}

async function doRenew() {
  const { data: order } = await http.post('/memberships/renew', {
    membership_id: renew.membership_id,
    product_id: renew.product_id,
    merchant_id: merchantId.value,
  })
  await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
  ElMessage.success('续卡并收款成功')
  await refresh()
}

async function freeze(id: number) {
  await http.post(`/memberships/${id}/freeze`)
  ElMessage.success('已停卡')
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

    <h3>办卡</h3>
    <el-form inline>
      <el-form-item label="会员">
        <el-select v-model="purchase.member_id" style="width: 200px" @change="loadUnusedCoupons">
          <el-option v-for="m in members" :key="m.id" :label="`${m.name}(${m.phone})`" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="卡种">
        <el-select v-model="purchase.product_id" style="width: 200px">
          <el-option v-for="p in products" :key="p.id" :label="`${p.name} ¥${p.price}`" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="优惠券">
        <el-select v-model="purchase.member_coupon_id" clearable style="width: 160px">
          <el-option v-for="c in unusedCoupons" :key="c.id" :label="`券#${c.id}`" :value="c.id" />
        </el-select>
      </el-form-item>
      <el-button type="primary" @click="doPurchase">办卡并线下收款</el-button>
    </el-form>

    <h3>续卡</h3>
    <el-form inline>
      <el-form-item label="会籍ID">
        <el-input-number v-model="renew.membership_id" :min="1" />
      </el-form-item>
      <el-form-item label="卡种(可选)">
        <el-select v-model="renew.product_id" clearable style="width: 200px">
          <el-option v-for="p in products" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-button type="primary" @click="doRenew">续卡并线下收款</el-button>
    </el-form>

    <h3 style="margin-top: 24px">会籍列表</h3>
    <el-table :data="memberships">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="member_id" label="会员" />
      <el-table-column prop="product_id" label="卡种" />
      <el-table-column prop="status" label="状态" />
      <el-table-column prop="ends_at" label="到期" />
      <el-table-column prop="remaining_sessions" label="剩余次" />
      <el-table-column prop="balance" label="余额" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" :disabled="row.status !== 'active'" @click="freeze(row.id)">停卡</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
