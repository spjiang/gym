<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'
import { merchantsWithSystem } from '../../../core/nav/systems'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Category = { id: number; name: string; sort_order: number; is_active?: boolean }

const merchants = ref<Merchant[]>([])
const categories = ref<Category[]>([])
const { merchantId, requireMerchant } = useOpsMerchant(() => {
  page.value = 1
  void refresh()
})
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)
const query = reactive({ q: '', status: '' as '' | 'active' | 'inactive' })
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ name: '', sort_order: 0 })
const rules: FormRules = { name: [{ required: true, message: '请填写分类名称', trigger: 'blur' }] }

async function refresh() {
  loading.value = true
  try {
    const { data } = await http.get('/merchants')
    merchants.value = merchantsWithSystem(data, 'gym')
    if (merchantId.value && !merchants.value.some((m) => m.id === merchantId.value)) {
      merchantId.value = undefined
    }
    const { data: rows } = await http.get('/retail/categories', {
      params: {
        merchant_id: merchantId.value,
        q: query.q.trim() || undefined,
        is_active: query.status === 'active' ? true : query.status === 'inactive' ? false : undefined,
        page: page.value,
        page_size: pageSize.value,
      },
    })
    categories.value = rows.items
    total.value = rows.total
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
  page.value = 1
  void refresh()
}

function openCreate() {
  editingId.value = null
  form.name = ''
  form.sort_order = 0
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

function openEdit(row: Category) {
  editingId.value = row.id
  form.name = row.name
  form.sort_order = row.sort_order
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  const mid = requireMerchant()
  if (!ok || !mid) return
  submitting.value = true
  try {
    const payload = { merchant_id: mid, name: form.name.trim(), sort_order: form.sort_order }
    if (editingId.value) await http.patch(`/retail/categories/${editingId.value}`, payload)
    else await http.post('/retail/categories', payload)
    ElMessage.success(editingId.value ? '分类已更新' : '分类已创建')
    dialogVisible.value = false
    await refresh()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
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
        <h3>商品分类</h3>
        <p class="lead">维护零售分类。商品档案请到「零售管理 → 商品管理」，收银请到「库存收银」。</p>
      </div>
      <el-button type="primary" @click="openCreate">新建分类</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="商户">
        <el-select v-model="merchantId" clearable placeholder="全部商户" style="width: 180px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="关键词">
        <el-input v-model="query.q" clearable placeholder="分类名称 / ID" style="width: 180px" @keyup.enter="search" />
      </el-form-item>
      <el-form-item label="状态">
        <el-select v-model="query.status" clearable placeholder="全部" style="width: 110px">
          <el-option label="启用" value="active" />
          <el-option label="停用" value="inactive" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="search">查询</el-button>
        <el-button @click="resetSearch">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="categories" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="分类" min-width="200" />
      <el-table-column prop="sort_order" label="排序" width="100" />
      <el-table-column label="状态" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">{{ row.is_active ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEdit(row)">编辑</el-button>
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

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑分类' : '新建分类'" width="420px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：补给 / 饮品" maxlength="64" />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="0" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="save">保存</el-button>
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
  margin-bottom: 16px;
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
  margin-bottom: 8px;
}
.pager {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}
</style>
