<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes: string[] }
type DiningTable = {
  id: number
  merchant_id: number
  name: string
  code: string
  sort_order: number
  is_active: boolean
  order_url: string
}

const merchants = ref<Merchant[]>([])
const tables = ref<DiningTable[]>([])
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const query = reactive({
  q: '',
  status: '' as '' | 'active' | 'inactive',
})
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const editingMerchantId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({
  name: '',
  sort_order: 10,
  is_active: true,
})
const rules: FormRules = {
  name: [{ required: true, message: '请填写桌号', trigger: 'blur' }],
}

const qrDialog = ref(false)
const qrTable = ref<DiningTable | null>(null)
const qrDataUrl = ref('')
const qrLoading = ref(false)

const cateringMerchants = () =>
  merchants.value.filter((m) => (m.subsystem_codes || []).includes('catering'))

function merchantName(id: number) {
  return merchants.value.find((m) => m.id === id)?.name || `#${id}`
}

async function loadMerchants() {
  const { data } = await http.get('/merchants')
  merchants.value = data
  const list = cateringMerchants()
  if (merchantId.value && !list.some((m) => m.id === merchantId.value)) merchantId.value = undefined
}

async function loadTables() {
  loading.value = true
  try {
    const { data } = await http.get('/catering/tables', {
      params: {
        merchant_id: merchantId.value,
        q: query.q.trim() || undefined,
        is_active: query.status === 'active' ? true : query.status === 'inactive' ? false : undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    tables.value = data.items
    total.value = data.total
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
    tables.value = []
    total.value = 0
  } finally {
    loading.value = false
  }
}

async function refresh() {
  await loadMerchants()
  await loadTables()
}

function search() {
  page.value = 1
  void loadTables()
}

function resetSearch() {
  query.q = ''
  query.status = ''
  page.value = 1
  void loadTables()
}

function openCreate() {
  const mid = requireMerchant('请先选择餐饮商户后再新建桌号')
  if (!mid) return
  editingId.value = null
  editingMerchantId.value = mid
  form.name = ''
  form.sort_order = (total.value + 1) * 10
  form.is_active = true
  dialogVisible.value = true
}

function openEdit(row: DiningTable) {
  editingId.value = row.id
  editingMerchantId.value = row.merchant_id
  form.name = row.name
  form.sort_order = row.sort_order
  form.is_active = row.is_active
  dialogVisible.value = true
}

async function save() {
  await formRef.value?.validate()
  const mid = editingMerchantId.value ?? requireMerchant()
  if (!mid) return
  submitting.value = true
  try {
    if (editingId.value) {
      await http.patch(`/catering/tables/${editingId.value}`, {
        name: form.name.trim(),
        sort_order: form.sort_order,
        is_active: form.is_active,
      }, { params: { merchant_id: mid } })
      ElMessage.success('已保存')
    } else {
      await http.post('/catering/tables', {
        merchant_id: mid,
        name: form.name.trim(),
        sort_order: form.sort_order,
        is_active: true,
      })
      ElMessage.success('已创建，可下载点餐二维码贴到桌上')
    }
    dialogVisible.value = false
    await loadTables()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

async function toggleActive(row: DiningTable) {
  try {
    await http.patch(`/catering/tables/${row.id}`, { is_active: !row.is_active }, { params: { merchant_id: row.merchant_id } })
    ElMessage.success(row.is_active ? '已停用，原二维码将无法点餐' : '已启用')
    await loadTables()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '操作失败')
  }
}

async function openQr(row: DiningTable) {
  qrTable.value = row
  qrDataUrl.value = ''
  qrDialog.value = true
  qrLoading.value = true
  try {
    const QRCode = (await import('qrcode')).default
    qrDataUrl.value = await QRCode.toDataURL(row.order_url, { width: 280, margin: 2 })
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '二维码生成失败')
    qrDialog.value = false
  } finally {
    qrLoading.value = false
  }
}

async function copyQrUrl() {
  if (!qrTable.value) return
  try {
    await navigator.clipboard.writeText(qrTable.value.order_url)
    ElMessage.success('点餐链接已复制')
  } catch {
    ElMessage.error('复制失败，请手动选择链接')
  }
}

function downloadQr() {
  if (!qrDataUrl.value || !qrTable.value) return
  const a = document.createElement('a')
  a.href = qrDataUrl.value
  a.download = `点餐码-${qrTable.value.name}.png`
  a.click()
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>桌号管理</h3>
        <p class="hint">每张桌子一个点餐二维码。客人扫码登录后自动带入桌号，厨房按桌出餐。</p>
      </div>
      <el-button type="primary" @click="openCreate">新建桌号</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="餐饮商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="search">
          <el-option v-for="m in cateringMerchants()" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="桌号 / 点餐码 / ID" style="width: 180px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 110px" @change="search">
          <el-option label="启用" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="!cateringMerchants().length"
      type="warning"
      :closable="false"
      title="当前没有关联「观野BAR」的商户"
      style="margin-bottom: 16px"
    />

    <el-table :data="tables" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column label="商户" width="140">
        <template #default="{ row }">{{ merchantName(row.merchant_id) }}</template>
      </el-table-column>
      <el-table-column prop="name" label="桌号" min-width="120" />
      <el-table-column prop="sort_order" label="排序" width="80" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '启用' : '停用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="点餐码" min-width="140">
        <template #default="{ row }">
          <span class="mono">{{ row.code }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openQr(row)">二维码</el-button>
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
          <el-button link :type="row.is_active ? 'warning' : 'success'" @click="toggleActive(row)">
            {{ row.is_active ? '停用' : '启用' }}
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
        @current-change="loadTables"
        @size-change="
          () => {
            page = 1
            loadTables()
          }
        "
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑桌号' : '新建桌号'" width="420px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="桌号" prop="name">
          <el-input v-model="form.name" maxlength="32" placeholder="如：A3 / 吧台 / 卡座1" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" :max="9999" />
        </el-form-item>
        <el-form-item v-if="editingId" label="状态">
          <el-switch v-model="form.is_active" active-text="启用" inactive-text="停用" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">{{ editingId ? '保存' : '创建' }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="qrDialog" :title="qrTable ? `点餐码 · ${qrTable.name}` : '点餐码'" width="420px" destroy-on-close>
      <div v-loading="qrLoading" class="qr-box">
        <img v-if="qrDataUrl" :src="qrDataUrl" alt="点餐二维码" class="qr-img" />
        <p class="qr-hint">打印后贴在桌上。客人微信扫码 → 登录 → 自动带入本桌，结算时无需再填桌号。</p>
        <el-input :model-value="qrTable?.order_url" readonly type="textarea" :rows="3" />
      </div>
      <template #footer>
        <el-button @click="copyQrUrl" :disabled="!qrTable">复制链接</el-button>
        <el-button type="primary" @click="downloadQr" :disabled="!qrDataUrl">下载二维码</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}
.toolbar h3 {
  margin: 0;
}
.hint {
  margin: 6px 0 0;
  color: var(--admin-ink-muted, var(--el-text-color-secondary));
  font-size: 13px;
}
.filters {
  margin-bottom: 4px;
}
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}
.mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  letter-spacing: 0.04em;
}
.qr-box {
  text-align: center;
  min-height: 160px;
}
.qr-img {
  width: 240px;
  height: 240px;
  margin: 0 auto 12px;
  display: block;
}
.qr-hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  text-align: left;
}
</style>
