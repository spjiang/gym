<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Merchant = { id: number; name: string }
type Asset = {
  id: number
  name: string
  category: string
  asset_code: string
  area: string | null
  status: string
}
type Repair = {
  id: number
  asset_id: number
  description: string
  status: string
}

const merchants = ref<Merchant[]>([])
const assets = ref<Asset[]>([])
const repairs = ref<Repair[]>([])
const merchantId = ref<number | undefined>()
const statusFilter = ref<string | undefined>()

const form = reactive({
  name: '',
  category: 'cardio',
  asset_code: '',
  area: '',
})
const repairForm = reactive({
  asset_id: undefined as number | undefined,
  description: '',
})

async function refresh() {
  const { data: m } = await http.get('/merchants')
  merchants.value = m
  if (!merchantId.value && m[0]) merchantId.value = m[0].id
  if (!merchantId.value) return
  const [a, r] = await Promise.all([
    http.get('/equipment/assets', {
      params: { merchant_id: merchantId.value, status: statusFilter.value || undefined },
    }),
    http.get('/equipment/repairs', { params: { merchant_id: merchantId.value } }),
  ])
  assets.value = a.data
  repairs.value = r.data
}

async function createAsset() {
  await http.post('/equipment/assets', { merchant_id: merchantId.value, ...form })
  ElMessage.success('器材已创建')
  form.name = ''
  form.asset_code = ''
  await refresh()
}

async function createRepair() {
  await http.post('/equipment/repairs', {
    merchant_id: merchantId.value,
    asset_id: repairForm.asset_id,
    description: repairForm.description,
  })
  ElMessage.success('已报修')
  repairForm.description = ''
  await refresh()
}

async function completeRepair(id: number) {
  await http.post(`/equipment/repairs/${id}/complete`, {
    resolution: '已处理',
    asset_status: 'in_use',
  })
  ElMessage.success('报修已完成')
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
      <el-form-item label="状态">
        <el-select v-model="statusFilter" clearable style="width: 140px" @change="refresh">
          <el-option label="在用" value="in_use" />
          <el-option label="维修" value="repair" />
          <el-option label="停用" value="disabled" />
          <el-option label="报废" value="scrapped" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-card header="新建器材" style="margin-bottom: 12px">
      <el-form inline>
        <el-input v-model="form.name" placeholder="名称" style="width: 140px; margin-right: 8px" />
        <el-input v-model="form.asset_code" placeholder="资产编号" style="width: 120px; margin-right: 8px" />
        <el-select v-model="form.category" style="width: 120px; margin-right: 8px">
          <el-option label="有氧" value="cardio" />
          <el-option label="力量" value="strength" />
          <el-option label="其他" value="other" />
        </el-select>
        <el-input v-model="form.area" placeholder="区域" style="width: 120px; margin-right: 8px" />
        <el-button type="primary" @click="createAsset">创建</el-button>
      </el-form>
    </el-card>

    <el-card header="报修" style="margin-bottom: 12px">
      <el-form inline>
        <el-select v-model="repairForm.asset_id" placeholder="器材" filterable style="width: 200px; margin-right: 8px">
          <el-option
            v-for="a in assets"
            :key="a.id"
            :label="`${a.asset_code} ${a.name}`"
            :value="a.id"
          />
        </el-select>
        <el-input v-model="repairForm.description" placeholder="故障描述" style="width: 220px; margin-right: 8px" />
        <el-button type="warning" @click="createRepair">提交报修</el-button>
      </el-form>
    </el-card>

    <h3>器材列表</h3>
    <el-table :data="assets" stripe style="margin-bottom: 16px">
      <el-table-column prop="asset_code" label="编号" width="120" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="category" label="分类" width="100" />
      <el-table-column prop="area" label="区域" width="120" />
      <el-table-column prop="status" label="状态" width="100" />
    </el-table>

    <h3>报修单</h3>
    <el-table :data="repairs" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="asset_id" label="器材" width="80" />
      <el-table-column prop="description" label="描述" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'open' || row.status === 'in_progress'"
            link
            type="primary"
            @click="completeRepair(row.id)"
          >
            完成
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
