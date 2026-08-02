<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Merchant = { id: number; name: string }
type Point = { id: number; name: string; merchant_id: number | null }
type Product = {
  id: number
  name: string
  product_type: string
  price: string
  duration_days: number | null
  is_active: boolean
  is_trial: boolean
  access_point_ids: number[]
}

const router = useRouter()
const merchants = ref<Merchant[]>([])
const points = ref<Point[]>([])
const products = ref<Product[]>([])
const merchantId = ref<number | undefined>()
const creating = ref(false)
const form = reactive({
  name: '',
  product_type: 'term',
  price: '299.00',
  duration_days: 30 as number | null,
  session_count: null as number | null,
  stored_value: null as string | null,
  access_point_ids: [] as number[],
  is_active: true,
  is_trial: false,
  promo_price: '' as string,
  promo_days: 0,
})

const noPoints = computed(() => points.value.length === 0)

async function loadMerchants() {
  const { data } = await http.get('/merchants')
  merchants.value = data
  if (!merchantId.value && data[0]) merchantId.value = data[0].id
}

async function loadPoints() {
  if (!merchantId.value) return
  const { data } = await http.get('/access-points')
  points.value = data.filter(
    (p: Point) => p.merchant_id === merchantId.value || p.merchant_id == null,
  )
  // 仅有一个门禁点时默认勾选，减少空提交
  if (form.access_point_ids.length === 0 && points.value.length === 1) {
    form.access_point_ids = [points.value[0].id]
  }
}

async function loadProducts() {
  if (!merchantId.value) return
  const { data } = await http.get('/membership-products', { params: { merchant_id: merchantId.value } })
  products.value = data
}

async function refresh() {
  form.access_point_ids = []
  await loadMerchants()
  await loadPoints()
  await loadProducts()
}

async function create() {
  if (!form.name.trim()) {
    ElMessage.warning('请填写卡种名称')
    return
  }
  if (form.is_active && form.access_point_ids.length === 0) {
    ElMessage.warning(noPoints.value ? '请先去「门禁设备」创建门禁点，再绑定后启用售卖' : '启用售卖时必须选择至少一个门禁点')
    return
  }
  creating.value = true
  try {
    const payload: Record<string, unknown> = { ...form, merchant_id: merchantId.value, name: form.name.trim() }
    if (form.promo_price && form.promo_days > 0) {
      const starts = new Date()
      const ends = new Date()
      ends.setDate(ends.getDate() + form.promo_days)
      payload.promo_price = form.promo_price
      payload.promo_starts_at = starts.toISOString()
      payload.promo_ends_at = ends.toISOString()
    } else {
      payload.promo_price = null
      payload.promo_starts_at = null
      payload.promo_ends_at = null
    }
    delete payload.promo_days
    await http.post('/membership-products', payload)
    ElMessage.success('卡种已创建')
    form.name = ''
    form.access_point_ids = points.value.length === 1 ? [points.value[0].id] : []
    await loadProducts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    creating.value = false
  }
}

async function deactivate(id: number) {
  try {
    await http.post(`/membership-products/${id}/deactivate`)
    ElMessage.success('已停用')
    await loadProducts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '停用失败')
  }
}

function goAccess() {
  router.push('/access')
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

    <el-alert
      v-if="noPoints"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <template #title>当前商户还没有可用门禁点</template>
      <p style="margin: 4px 0 10px">
        启用售卖的卡种必须绑定门禁点。请先在「综合经营 → 门禁设备」创建门禁点，或关闭「启用售卖」以草稿保存。
      </p>
      <el-button size="small" type="warning" @click="goAccess">去创建门禁点</el-button>
    </el-alert>

    <h3>新建卡种</h3>
    <el-form label-width="100px" style="max-width: 560px">
      <el-form-item label="名称" required>
        <el-input v-model="form.name" placeholder="必填" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="form.product_type">
          <el-option label="期限卡" value="term" />
          <el-option label="次卡" value="count" />
          <el-option label="储值卡" value="value" />
        </el-select>
      </el-form-item>
      <el-form-item label="价格"><el-input v-model="form.price" /></el-form-item>
      <el-form-item v-if="form.product_type === 'term'" label="天数">
        <el-input-number v-model="form.duration_days" :min="1" />
      </el-form-item>
      <el-form-item v-if="form.product_type === 'count'" label="次数">
        <el-input-number v-model="form.session_count" :min="1" />
      </el-form-item>
      <el-form-item v-if="form.product_type === 'value'" label="储值">
        <el-input v-model="form.stored_value" />
      </el-form-item>
      <el-form-item label="门禁点" :required="form.is_active">
        <el-select
          v-model="form.access_point_ids"
          multiple
          style="width: 100%"
          :placeholder="noPoints ? '暂无门禁点，请先创建' : '请选择门禁点（可多选）'"
        >
          <el-option v-for="p in points" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="体验卡"><el-switch v-model="form.is_trial" /></el-form-item>
      <el-form-item label="活动价"><el-input v-model="form.promo_price" placeholder="可选" /></el-form-item>
      <el-form-item label="活动天数">
        <el-input-number v-model="form.promo_days" :min="0" />
      </el-form-item>
      <el-form-item label="启用售卖"><el-switch v-model="form.is_active" /></el-form-item>
      <el-button type="primary" :loading="creating" @click="create">创建</el-button>
    </el-form>

    <h3 style="margin-top: 24px">卡种列表</h3>
    <el-table :data="products">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="product_type" label="类型" />
      <el-table-column label="体验" width="70">
        <template #default="{ row }">{{ row.is_trial ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column prop="price" label="价格" />
      <el-table-column prop="is_active" label="在售" />
      <el-table-column label="门禁">
        <template #default="{ row }">{{ row.access_point_ids.join(', ') || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" :disabled="!row.is_active" @click="deactivate(row.id)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
