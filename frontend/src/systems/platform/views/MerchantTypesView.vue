<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../../../core/api/http'

type MerchantType = { id: number; code: string; name: string; description: string | null }

const types = ref<MerchantType[]>([])
const loading = ref(false)
const page = ref(1)
const pageSize = ref(20)
const query = reactive({ q: '' })
const filteredTypes = computed(() => {
  const kw = query.q.trim()
  if (!kw) return types.value
  return types.value.filter(
    (row) => row.code.includes(kw) || row.name.includes(kw) || (row.description || '').includes(kw) || String(row.id).includes(kw),
  )
})
const pagedTypes = computed(() => {
  const start = (page.value - 1) * pageSize.value
  return filteredTypes.value.slice(start, start + pageSize.value)
})
const dialogVisible = ref(false)
const submitting = ref(false)
const editingId = ref<number | null>(null)
const formRef = ref<FormInstance>()
const form = reactive({ code: '', name: '', description: '' })

const rules: FormRules = {
  code: [{ required: true, message: '请填写类型编码', trigger: 'blur' }],
  name: [{ required: true, message: '请填写类型名称', trigger: 'blur' }],
}

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<MerchantType[]>('/merchant-types')
    types.value = data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openDialog(row?: MerchantType) {
  editingId.value = row?.id ?? null
  form.code = row?.code || ''
  form.name = row?.name || ''
  form.description = row?.description || ''
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function save() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    const payload = {
      code: form.code.trim(),
      name: form.name.trim(),
      description: form.description.trim() || null,
    }
    if (editingId.value) await http.patch(`/merchant-types/${editingId.value}`, payload)
    else await http.post('/merchant-types', payload)
    ElMessage.success(editingId.value ? '已保存' : '已创建商户类型')
    dialogVisible.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    submitting.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>商户类型</h3>
      <el-button type="primary" @click="openDialog()">新增类型</el-button>
    </div>

    <el-form inline class="filters">
      <el-form-item label="关键词">
        <el-input
          v-model="query.q"
          clearable
          placeholder="编码 / 名称 / 说明"
          style="width: 220px"
          @input="page = 1"
        />
      </el-form-item>
      <el-form-item>
        <el-button @click="query.q = ''; page = 1">重置</el-button>
      </el-form-item>
    </el-form>

    <el-table :data="pagedTypes" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="code" label="编码" width="160" />
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="description" label="说明" min-width="200">
        <template #default="{ row }">{{ row.description || '—' }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openDialog(row)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pager">
      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="filteredTypes.length"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        background
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑商户类型' : '新增商户类型'" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="90px">
        <el-form-item label="编码" prop="code">
          <el-input v-model="form.code" placeholder="如 gym / bar" />
        </el-form-item>
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="说明">
          <el-input v-model="form.description" type="textarea" :rows="3" placeholder="可选" />
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
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0;
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
