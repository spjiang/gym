<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { canAny, merchantsWithSystem } from '../../../core/nav/systems'
import { useAuthStore } from '../../../core/stores/auth'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Asset = {
  id: number
  name: string
  asset_code: string
  category: string
  area: string
  status: string
}

const auth = useAuthStore()
const perms = computed(() => auth.me?.permissions || [])
const canManage = computed(() => canAny(perms.value, ['equipment:manage', '*']))

const merchants = ref<Merchant[]>([])
const assets = ref<Asset[]>([])
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const query = reactive({
  q: '',
  category: '' as string,
  area: '',
  status: '' as string,
})
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const assetDialog = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const assetFormRef = ref<FormInstance>()

const form = reactive({
  name: '',
  category: 'cardio',
  asset_code: '',
  area: '',
  status: 'in_use',
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

function statusLabel(s: string) {
  return { in_use: '在用', repair: '维修', disabled: '停用', scrapped: '报废' }[s] || s
}

async function refresh() {
  loading.value = true
  try {
    const { data: m } = await http.get('/merchants')
    merchants.value = merchantsWithSystem(m, 'gym')
    if (merchantId.value && !merchants.value.some((x) => x.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const { data } = await http.get('/equipment/assets', {
      params: {
        merchant_id: merchantId.value,
        status: query.status || undefined,
        category: query.category || undefined,
        area: query.area.trim() || undefined,
        q: query.q.trim() || undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    assets.value = data.items
    total.value = data.total
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
  query.category = ''
  query.area = ''
  query.status = ''
  page.value = 1
  void refresh()
}

function openAssetDialog() {
  editingId.value = null
  form.name = ''
  form.category = 'cardio'
  form.asset_code = ''
  form.area = ''
  form.status = 'in_use'
  assetFormRef.value?.clearValidate()
  assetDialog.value = true
}

function openEditAsset(row: Asset) {
  editingId.value = row.id
  form.name = row.name
  form.category = row.category
  form.asset_code = row.asset_code
  form.area = row.area
  form.status = row.status
  assetFormRef.value?.clearValidate()
  assetDialog.value = true
}

async function saveAsset() {
  const ok = await assetFormRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    if (editingId.value) {
      await http.patch(`/equipment/assets/${editingId.value}`, {
        name: form.name.trim(),
        category: form.category,
        area: form.area,
        status: form.status,
      })
      ElMessage.success('器材已更新')
    } else {
      await http.post('/equipment/assets', {
        merchant_id: mid,
        name: form.name.trim(),
        category: form.category,
        asset_code: form.asset_code.trim(),
        area: form.area,
      })
      ElMessage.success('器材已创建')
    }
    assetDialog.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : editingId.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

onMounted(refresh)
</script>
<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>器材台账</h3>
        <p class="lead">维护器材档案。报修请到「器材管理 → 报修单」。</p>
      </div>
      <el-button v-if="canManage" type="primary" @click="openAssetDialog">新建器材</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="search">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="名称 / 编号 / 区域" style="width: 180px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="分类">
        <el-select v-model="query.category" clearable placeholder="全部" style="width: 120px">
          <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
        </el-select>
      </el-form-item>
      <el-form-item label="区域">
        <el-input v-model="query.area" clearable placeholder="如：有氧区" style="width: 140px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 120px">
          <el-option label="在用" value="in_use" />
          <el-option label="维修" value="repair" />
          <el-option label="停用" value="disabled" />
          <el-option label="报废" value="scrapped" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="assets" v-loading="loading" stripe>
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
      <el-table-column v-if="canManage" label="操作" width="90">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEditAsset(row)">编辑</el-button>
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

    <el-dialog v-model="assetDialog" :title="editingId ? '编辑器材' : '新建器材'" width="480px" destroy-on-close>
      <el-form ref="assetFormRef" :model="form" :rules="assetRules" label-width="90px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：跑步机 03 号" maxlength="128" />
        </el-form-item>
        <el-form-item label="资产编号" prop="asset_code">
          <el-input v-model="form.asset_code" :disabled="!!editingId" placeholder="唯一资产编号" maxlength="64" />
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width: 100%">
            <el-option v-for="c in CATEGORY_OPTIONS" :key="c.value" :label="c.label" :value="c.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="区域">
          <el-input v-model="form.area" placeholder="如：有氧区 / 力量区" maxlength="64" />
        </el-form-item>
        <el-form-item v-if="editingId" label="状态">
          <el-select v-model="form.status" style="width: 100%">
            <el-option label="在用" value="in_use" />
            <el-option label="维修" value="repair" />
            <el-option label="停用" value="disabled" />
            <el-option label="报废" value="scrapped" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="assetDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="saveAsset">{{ editingId ? '保存' : '创建' }}</el-button>
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
