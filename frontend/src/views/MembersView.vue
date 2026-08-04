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
const loading = ref(false)

const createDialog = ref(false)
const linkDialog = ref(false)
const submitting = ref(false)
const formRef = ref<FormInstance>()
const linkFormRef = ref<FormInstance>()

const form = reactive({ phone: '', name: '', merchant_id: undefined as number | undefined })
const linkForm = reactive({ merchant_id: undefined as number | undefined })
const linkTarget = ref<Member | null>(null)

const rules: FormRules = {
  phone: [{ required: true, message: '请填写手机号', trigger: 'blur' }],
  name: [{ required: true, message: '请填写姓名', trigger: 'blur' }],
  merchant_id: [{ required: true, message: '请选择商户', trigger: 'change' }],
}

const linkRules: FormRules = {
  merchant_id: [{ required: true, message: '请选择目标商户', trigger: 'change' }],
}

function merchantName(id: number) {
  return merchants.value.find((m) => m.id === id)?.name || `#${id}`
}

function faceLabel(status: string) {
  return { enrolled: '已录入', not_enrolled: '未录入', pending: '待审核' }[status] || status
}

async function load() {
  loading.value = true
  try {
    const [m, ms] = await Promise.all([http.get('/members'), http.get('/merchants')])
    members.value = m.data
    merchants.value = ms.data
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openCreate() {
  form.phone = ''
  form.name = ''
  form.merchant_id = merchants.value[0]?.id
  formRef.value?.clearValidate()
  createDialog.value = true
}

async function create() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post('/members', {
      phone: form.phone.trim(),
      name: form.name.trim(),
      merchant_id: form.merchant_id,
    })
    ElMessage.success('会员已创建')
    createDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    submitting.value = false
  }
}

function openLink(row: Member) {
  linkTarget.value = row
  linkForm.merchant_id = merchants.value.find((m) => !row.merchant_ids.includes(m.id))?.id
  linkFormRef.value?.clearValidate()
  linkDialog.value = true
}

async function link() {
  if (!linkTarget.value) return
  const ok = await linkFormRef.value?.validate().catch(() => false)
  if (!ok) return
  submitting.value = true
  try {
    await http.post(`/members/${linkTarget.value.id}/merchants`, { merchant_id: linkForm.merchant_id })
    ElMessage.success(`已关联到「${merchantName(linkForm.merchant_id!)}」`)
    linkDialog.value = false
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '关联失败')
  } finally {
    submitting.value = false
  }
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
    <div class="toolbar">
      <h3>会员主档</h3>
      <el-button type="primary" @click="openCreate">创建会员</el-button>
    </div>

    <el-table :data="members" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="phone" label="手机号" />
      <el-table-column prop="name" label="姓名" />
      <el-table-column label="人脸状态" width="120">
        <template #default="{ row }">
          <el-tag
            size="small"
            :type="row.face_status === 'enrolled' ? 'success' : row.face_status === 'pending' ? 'warning' : 'info'"
          >
            {{ faceLabel(row.face_status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="关联商户">
        <template #default="{ row }">
          <el-tag
            v-for="id in row.merchant_ids"
            :key="id"
            size="small"
            effect="plain"
            style="margin-right: 6px"
          >
            {{ merchantName(id) }}
          </el-tag>
          <span v-if="!row.merchant_ids.length">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-button link type="primary" @click="openLink(row)">关联商户</el-button>
          <el-button link type="danger" @click="remove(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 创建会员弹窗 -->
    <el-dialog v-model="createDialog" title="创建会员" width="480px" destroy-on-close>
      <el-form ref="formRef" :model="form" :rules="rules" label-width="80px">
        <el-form-item label="手机号" prop="phone">
          <el-input v-model="form.phone" placeholder="会员手机号，必填" maxlength="32" />
        </el-form-item>
        <el-form-item label="姓名" prop="name">
          <el-input v-model="form.name" placeholder="会员姓名，必填" maxlength="128" />
        </el-form-item>
        <el-form-item label="商户" prop="merchant_id">
          <el-select v-model="form.merchant_id" style="width: 100%">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <!-- 关联商户弹窗 -->
    <el-dialog
      v-model="linkDialog"
      :title="`关联商户 · ${linkTarget ? linkTarget.name || linkTarget.phone : ''}`"
      width="460px"
      destroy-on-close
    >
      <el-alert
        v-if="linkTarget"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 14px"
        title="关联后该会员可访问对应商户的权益与门禁授权"
      />
      <el-form ref="linkFormRef" :model="linkForm" :rules="linkRules" label-width="80px">
        <el-form-item label="目标商户" prop="merchant_id">
          <el-select v-model="linkForm.merchant_id" style="width: 100%" placeholder="请选择要关联到的商户">
            <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="linkDialog = false">取消</el-button>
        <el-button type="primary" :loading="submitting" @click="link">确认关联</el-button>
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
</style>
