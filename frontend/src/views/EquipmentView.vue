<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../api/http'
import { merchantsWithSystem } from '../nav/systems'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Asset = {
  id: number
  name: string
  asset_code: string
  category: string
  area: string
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
const loading = ref(false)

const assetDialog = ref(false)
const repairDialog = ref(false)
const submitting = ref(false)
const assetFormRef = ref<FormInstance>()
const repairFormRef = ref<FormInstance>()

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

const CATEGORY_OPTIONS = [
  { label: '有氧', value: 'cardio' },
  { label: '力量', value: 'strength' },
  { label: '其他', value: 'other' },
]

const assetRules: FormRules = {
  name: [{ required: true, message: '请填写器材名称', trigger: 'blur' }],
  asset_code: [{ required: true, message: '请填写资产编号', trigger: 'blur' }],
}

const repairRules: FormRules = {
  asset_id: [{ required: true, message: '请选择器材', trigger: 'change' }],
  description: [{ required: true, message: '请填写故障描述', trigger: 'blur' }],
}

function assetLabel(a: Asset) {
  return `${a.asset_code} ${a.name}`
}

function assetName(id: number) {
  const a = assets.value.find((x) => x.id === id)
  return a ? assetLabel(a) : `#${id}`
}

function statusLabel(s: string) {
  return { in_use: '在用', repair: '维修', disabled: '停用', scrapped: '报废' }[s] || s
}

async function refresh() {
  loading.value = true
  try {
    const { data: m } = await http.get('/merchants')
    merchants.value = merchantsWithSystem(m, 'gym')
    if (!merchantId.value && merchants.value[0]) merchantId.value = merchants.value[0].id
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = merchants.value[0]?.id
    }
    if (!merchantId.value) return
    const [a, r] = await Promise.all([
      http.get('/equipment/assets', {
        params: { merchant_id: merchantId.value, status: statusFilter.value || undefined },
      }),
      http.get('/equipment/repairs', { params: { merchant_id: merchantId.value } }),
    ])
    assets.value = a.data
    repairs.value = r.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openAssetDialog() {
  form.name = ''
  form.category = 'cardio'
  form.asset_code = ''
  form.area = ''
  assetFormRef.value?.clearValidate()
  assetDialog.value = true
}

async function createAsset() {
  const ok = await assetFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/equipment/assets', {
      merchant_id: merchantId.value,
      name: form.name.trim(),
      category: form.category,
      asset_code: form.asset_code.trim(),
      area: form.area,
    })
    ElMessage.success('器材已创建')
    assetDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openRepairDialog() {
  repairForm.asset_id = assets.value[0]?.id
  repairForm.description = ''
  repairFormRef.value?.clearValidate()
  repairDialog.value = true
}

async function createRepair() {
  const ok = await repairFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/equipment/repairs', {
      merchant_id: merchantId.value,
      asset_id: repairForm.asset_id,
      description: repairForm.description.trim(),
    })
    ElMessage.success('已报修')
    repairDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '报修失败')
  } finally {
    submitting.value = false
  }
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
    <div class="toolbar">
      <h3>器材台账</h3>
      <div class="toolbar-actions">
        <el-button type="primary" plain @click="openAssetDialog">新建器材</el-button>
        <el-button type="warning" plain @click="openRepairDialog">提交报修</el-button>
      </div>
    </div>

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

    <h3 class="section-title">器材列表</h3>
    <el-table :data="assets" v-loading="loading" stripe style="margin-bottom: 28px">
      <el-table-column prop="asset_code" label="编号" width="140" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="分类" width="100">
        <template #default="{ row }">
          {{ CATEGORY_OPTIONS.find((c) => c.value === row.category)?.label || row.category }}
        </template>
      </el-table-column>
      <el-table-column prop="area" label="区域" width="130" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'in_use' ? 'success' : row.status === 'repair' ? 'warning' : 'info'" size="small">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
    </el-table>

    <h3 class="section-title">报修单</h3>
    <el-table :data="repairs" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="器材" width="220">
        <template #default="{ row }">{{ assetName(row.asset_id) }}</template>
      </el-table-column>
      <el-table-column prop="description" label="描述" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'completed' ? 'success' : 'warning'" size="small">
            {{ row.status === 'completed' ? '已完成' : '处理中' }}
          </el-tag>
        </template>
      </el-table-column>
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

    <!-- 新建器材弹窗 -->
    <el-dialog v-model="assetDialog" title="新建器材" width="480px" destroy-on-close>
      <el-form ref="assetFormRef" :model="form" :rules="assetRules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：跑步机 03 号" maxlength="128" />
        </el-form-item>
        <el-form-item label="资产编号" prop="asset_code">
          <el-input v-model="form.asset_code" placeholder="唯一资产编号" maxlength="64" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width: 100%">
            <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="区域">
          <el-input v-model="form.area" placeholder="如：有氧区 / 力量区" maxlength="64" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assetDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="createAsset">创建</el-button>
      </template>
    </el-dialog>

    <!-- 报修弹窗 -->
    <el-dialog v-model="repairDialog" title="提交报修" width="480px" destroy-on-close>
      <el-form ref="repairFormRef" :model="repairForm" :rules="repairRules" label-width="90px">
        <el-form-item label="器材" prop="asset_id">
          <el-select v-model="repairForm.asset_id" filterable style="width: 100%">
            <el-option v-for="a in assets" :key="a.id" :label="assetLabel(a)" :value="a.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="故障描述" prop="description">
          <el-input
            v-model="repairForm.description"
            type="textarea"
            :rows="3"
            placeholder="描述故障现象，便于维修处理"
            maxlength="500"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="repairDialog = false">取消</el-button>
        <el-button type="warning" :loading="submitting" @click="createRepair">提交报修</el-button>
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
