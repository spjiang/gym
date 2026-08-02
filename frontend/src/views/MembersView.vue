<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox, type FormInstance, type FormRules } from 'element-plus'
import http from '../api/http'

type Member = {
  id: number
  phone: string
  name: string
  face_status: string
  merchant_ids: number[]
}
type Merchant = { id: number; name: string }

const members = ref<Member[]>([])
const merchants = ref<Merchant[]>([])
const formRef = ref<FormInstance>()
const form = reactive({ phone: '', name: '', merchant_id: undefined as number | undefined })
const linkMerchantId = ref<number | undefined>()
const creating = ref(false)

const rules: FormRules = {
  phone: [
    { required: true, message: '请填写手机号', trigger: 'blur' },
    { min: 1, message: '手机号不能为空', trigger: 'blur' },
  ],
  name: [
    { required: true, message: '请填写姓名', trigger: 'blur' },
    { min: 1, message: '姓名不能为空', trigger: 'blur' },
  ],
  merchant_id: [{ required: true, message: '请选择商户', trigger: 'change' }],
}

function merchantName(id: number) {
  return merchants.value.find((m) => m.id === id)?.name || `#${id}`
}

async function load() {
  const [m, ms] = await Promise.all([http.get('/members'), http.get('/merchants')])
  members.value = m.data
  merchants.value = ms.data
  if (!form.merchant_id && merchants.value[0]) form.merchant_id = merchants.value[0].id
  if (!linkMerchantId.value && merchants.value[0]) linkMerchantId.value = merchants.value[0].id
}

async function create() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  creating.value = true
  try {
    await http.post('/members', {
      phone: form.phone.trim(),
      name: form.name.trim(),
      merchant_id: form.merchant_id,
    })
    ElMessage.success('会员已创建')
    form.phone = ''
    form.name = ''
    formRef.value?.clearValidate()
    await load()
  } finally {
    creating.value = false
  }
}

async function link(row: Member) {
  if (!linkMerchantId.value) {
    ElMessage.warning('请先选择上方的「关联目标商户」')
    return
  }
  if (row.merchant_ids.includes(linkMerchantId.value)) {
    ElMessage.info('该会员已关联此商户')
    return
  }
  await http.post(`/members/${row.id}/merchants`, { merchant_id: linkMerchantId.value })
  ElMessage.success(`已关联到「${merchantName(linkMerchantId.value)}」`)
  await load()
}

async function remove(row: Member) {
  try {
    await ElMessageBox.confirm(
      `确认删除会员「${row.name || row.phone || `#${row.id}`}」？删除后不可恢复。`,
      '删除会员',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' },
    )
  } catch {
    return
  }
  try {
    await http.delete(`/members/${row.id}`)
    ElMessage.success('已删除')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '删除失败')
  }
}

onMounted(load)
</script>

<template>
  <div>
    <h3>创建会员</h3>
    <el-form ref="formRef" :model="form" :rules="rules" inline>
      <el-form-item label="手机号" prop="phone">
        <el-input v-model="form.phone" placeholder="必填" maxlength="32" />
      </el-form-item>
      <el-form-item label="姓名" prop="name">
        <el-input v-model="form.name" placeholder="必填" maxlength="128" />
      </el-form-item>
      <el-form-item label="商户" prop="merchant_id">
        <el-select v-model="form.merchant_id" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-button type="primary" :loading="creating" @click="create">创建</el-button>
    </el-form>

    <div class="link-bar">
      <span class="label">关联目标商户</span>
      <el-select
        v-model="linkMerchantId"
        placeholder="请选择要关联到的商户"
        style="width: 240px"
        clearable
      >
        <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <span class="hint">先选商户，再点表格中的「关联」</span>
    </div>

    <el-table :data="members" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="phone" label="手机号" />
      <el-table-column prop="name" label="姓名" />
      <el-table-column prop="face_status" label="人脸状态" />
      <el-table-column label="关联商户">
        <template #default="{ row }">
          {{ row.merchant_ids.map(merchantName).join('、') || '—' }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="link(row)">关联</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.link-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin: 18px 0 14px;
  padding: 12px 14px;
  border-radius: 12px;
  background: rgba(61, 107, 92, 0.06);
  border: 1px solid rgba(61, 107, 92, 0.12);
}
.label {
  font-weight: 600;
  color: var(--admin-ink);
  white-space: nowrap;
}
.hint {
  font-size: 0.82rem;
  color: var(--admin-ink-muted);
}
</style>
