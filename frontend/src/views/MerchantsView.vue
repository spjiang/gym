<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type MerchantType = { id: number; code: string; name: string }
type Merchant = { id: number; name: string; status: string; merchant_type_id: number }

const types = ref<MerchantType[]>([])
const merchants = ref<Merchant[]>([])
const typeForm = reactive({ code: '', name: '' })
const merchantForm = reactive({ merchant_type_id: undefined as number | undefined, name: '', status: 'active' })

async function load() {
  const [t, m] = await Promise.all([http.get('/merchant-types'), http.get('/merchants')])
  types.value = t.data
  merchants.value = m.data
}

async function createType() {
  await http.post('/merchant-types', typeForm)
  ElMessage.success('已创建商户类型')
  typeForm.code = ''
  typeForm.name = ''
  await load()
}

async function createMerchant() {
  await http.post('/merchants', merchantForm)
  ElMessage.success('已创建商户')
  merchantForm.name = ''
  await load()
}

async function setStatus(row: Merchant, status: string) {
  await http.patch(`/merchants/${row.id}?status=${status}`)
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <h3>商户类型</h3>
    <el-form inline @submit.prevent="createType">
      <el-form-item label="编码"><el-input v-model="typeForm.code" /></el-form-item>
      <el-form-item label="名称"><el-input v-model="typeForm.name" /></el-form-item>
      <el-button type="primary" @click="createType">新增类型</el-button>
    </el-form>
    <el-table :data="types" style="margin-bottom: 24px">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="code" label="编码" />
      <el-table-column prop="name" label="名称" />
    </el-table>

    <h3>商户</h3>
    <el-form inline>
      <el-form-item label="类型">
        <el-select v-model="merchantForm.merchant_type_id" style="width: 160px">
          <el-option v-for="t in types" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="名称"><el-input v-model="merchantForm.name" /></el-form-item>
      <el-button type="primary" @click="createMerchant">新增商户</el-button>
    </el-form>
    <el-table :data="merchants">
      <el-table-column prop="id" label="ID" width="80" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="status" label="状态" />
      <el-table-column label="操作" width="220">
        <template #default="{ row }">
          <el-button size="small" @click="setStatus(row, 'active')">营业</el-button>
          <el-button size="small" @click="setStatus(row, 'disabled')">停用</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
