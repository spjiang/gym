<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { canAny, merchantsWithSystem } from '../../../core/nav/systems'
import { useAuthStore } from '../../../core/stores/auth'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Asset = { id: number; name: string; asset_code: string }
type Repair = {
  id: number
  asset_id: number
  description: string
  status: string
}

const auth = useAuthStore()
const perms = computed(() => auth.me?.permissions || [])
const canManage = computed(() => canAny(perms.value, ['equipment:manage', '*']))
const canRepair = computed(() => canAny(perms.value, ['equipment:repair', 'equipment:manage', '*']))

const merchants = ref<Merchant[]>([])
const repairs = ref<Repair[]>([])
const assetOptions = ref<Asset[]>([])
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const query = reactive({
  q: '',
  status: '' as string,
  asset_id: undefined as number | undefined,
})
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const repairDialog = ref(false)
const submitting = ref(false)
const repairFormRef = ref<FormInstance>()
const repairForm = reactive({
  asset_id: undefined as number | undefined,
  description: '',
})

const repairRules: FormRules = {
  asset_id: [{ required: true, message: '请选择器材', trigger: 'change' }],
  description: [{ required: true, message: '请填写故障描述', trigger: 'blur' }],
}

function assetLabel(a: Asset) {
  return `${a.asset_code} ${a.name}`
}

function assetName(id: number) {
  const a = assetOptions.value.find((x) => x.id === id)
  return a ? assetLabel(a) : `#${id}`
}

function repairStatusLabel(s: string) {
  return { open: '待处理', in_progress: '处理中', done: '已完成', closed: '已关闭' }[s] || s
}

async function refresh() {
  loading.value = true
  try {
    const { data: m } = await http.get('/merchants')
    merchants.value = merchantsWithSystem(m, 'gym')
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const [r, opts] = await Promise.all([
      http.get('/equipment/repairs', {
        params: {
          merchant_id: merchantId.value,
          status: query.status || undefined,
          q: query.q.trim() || undefined,
          asset_id: query.asset_id,
          page: page.value,
          page_size: pageSize.value,
        },
      }),
      http.get('/equipment/assets', {
        params: { merchant_id: merchantId.value, page: 1, page_size: 100 },
      }),
    ])
    repairs.value = r.data.items
    total.value = r.data.total
    assetOptions.value = opts.data.items
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
  query.status = ''
  query.asset_id = undefined
  page.value = 1
  void refresh()
}

function openRepairDialog() {
  repairForm.asset_id = query.asset_id ?? assetOptions.value[0]?.id
  repairForm.description = ''
  repairFormRef.value?.clearValidate()
  repairDialog.value = true
}

async function createRepair() {
  const ok = await repairFormRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    await http.post('/equipment/repairs', {
      merchant_id: mid,
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
      <div>
        <h3>报修单</h3>
        <p class="lead">提交与处理器材故障。器材档案请到「器材管理 → 器材台账」。</p>
      </div>
      <el-button v-if="canRepair" type="warning" @click="openRepairDialog">提交报修</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="search">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="器材">
        <el-select v-model="query.asset_id" clearable filterable placeholder="全部器材" style="width: 200px">
          <el-option v-for="a in assetOptions" :key="a.id" :label="assetLabel(a)" :value="a.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="故障描述" style="width: 180px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 130px">
          <el-option label="待处理" value="open" />
          <el-option label="处理中" value="in_progress" />
          <el-option label="已完成" value="done" />
          <el-option label="已关闭" value="closed" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="repairs" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="器材" width="220">
        <template #default="{ row }">{{ assetName(row.asset_id) }}</template>
      </el-table-column>
      <el-table-column prop="description" label="描述" />
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="row.status === 'done' || row.status === 'closed' ? 'success' : 'warning'" size="small">
            {{ repairStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column v-if="canManage" label="操作" width="120">
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

    <el-dialog v-model="repairDialog" title="提交报修" width="480px" destroy-on-close>
      <el-form ref="repairFormRef" :model="repairForm" :rules="repairRules" label-width="90px">
        <el-form-item label="器材" prop="asset_id">
          <el-select v-model="repairForm.asset_id" filterable style="width: 100%">
            <el-option v-for="a in assetOptions" :key="a.id" :label="assetLabel(a)" :value="a.id" />
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
.filters {
  margin-bottom: 4px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
