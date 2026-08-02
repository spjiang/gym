<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Point = { id: number; name: string; merchant_id: number | null }
type Device = { id: number; device_code: string; access_point_id: number; is_online: boolean }
type Grant = { id: number; member_id: number; access_point_id: number; revoked: boolean }
type Member = { id: number; name: string; phone: string }
type Merchant = { id: number; name: string }

const points = ref<Point[]>([])
const devices = ref<Device[]>([])
const grants = ref<Grant[]>([])
const members = ref<Member[]>([])
const merchants = ref<Merchant[]>([])

const pointForm = reactive({ name: '', merchant_id: undefined as number | undefined })
const deviceForm = reactive({ access_point_id: undefined as number | undefined, device_code: '', api_key: '' })
const grantForm = reactive({
  member_id: undefined as number | undefined,
  access_point_id: undefined as number | undefined,
  merchant_id: undefined as number | undefined,
  days: 30,
})

async function load() {
  const [p, d, g, m, ms] = await Promise.all([
    http.get('/access-points'),
    http.get('/devices'),
    http.get('/grants'),
    http.get('/members'),
    http.get('/merchants'),
  ])
  points.value = p.data
  devices.value = d.data
  grants.value = g.data
  members.value = m.data
  merchants.value = ms.data
  if (!pointForm.merchant_id && merchants.value[0]) pointForm.merchant_id = merchants.value[0].id
}

async function createPoint() {
  await http.post('/access-points', pointForm)
  ElMessage.success('门禁点已创建')
  await load()
}

async function registerDevice() {
  await http.post('/devices', deviceForm)
  ElMessage.success('设备已注册')
  deviceForm.device_code = ''
  deviceForm.api_key = ''
  await load()
}

async function createGrant() {
  const now = new Date()
  const until = new Date(now.getTime() + grantForm.days * 86400000)
  await http.post('/grants', {
    member_id: grantForm.member_id,
    access_point_id: grantForm.access_point_id,
    merchant_id: grantForm.merchant_id || pointForm.merchant_id,
    valid_from: now.toISOString(),
    valid_until: until.toISOString(),
  })
  ElMessage.success('授权已发放')
  await load()
}

async function revoke(id: number) {
  await http.post(`/grants/${id}/revoke`)
  ElMessage.success('已撤销')
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <h3>门禁点</h3>
    <el-form inline>
      <el-form-item label="名称"><el-input v-model="pointForm.name" /></el-form-item>
      <el-form-item label="商户">
        <el-select v-model="pointForm.merchant_id" style="width: 180px">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-button type="primary" @click="createPoint">创建</el-button>
    </el-form>
    <el-table :data="points" style="margin-bottom: 20px">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column prop="merchant_id" label="商户ID" />
    </el-table>

    <h3>设备注册</h3>
    <el-form inline>
      <el-form-item label="门禁点">
        <el-select v-model="deviceForm.access_point_id" style="width: 160px">
          <el-option v-for="p in points" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="设备码"><el-input v-model="deviceForm.device_code" /></el-form-item>
      <el-form-item label="API Key"><el-input v-model="deviceForm.api_key" /></el-form-item>
      <el-button type="primary" @click="registerDevice">注册</el-button>
    </el-form>
    <el-table :data="devices" style="margin-bottom: 20px">
      <el-table-column prop="device_code" label="设备码" />
      <el-table-column prop="access_point_id" label="门禁点" />
      <el-table-column prop="is_online" label="在线" />
    </el-table>

    <h3>通行授权</h3>
    <el-form inline>
      <el-form-item label="会员">
        <el-select v-model="grantForm.member_id" style="width: 180px">
          <el-option v-for="m in members" :key="m.id" :label="`${m.name}(${m.phone})`" :value="m.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="门禁点">
        <el-select v-model="grantForm.access_point_id" style="width: 160px">
          <el-option v-for="p in points" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="天数"><el-input-number v-model="grantForm.days" :min="1" /></el-form-item>
      <el-button type="primary" @click="createGrant">发放</el-button>
    </el-form>
    <el-table :data="grants">
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="member_id" label="会员" />
      <el-table-column prop="access_point_id" label="门禁点" />
      <el-table-column prop="revoked" label="已撤销" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button size="small" :disabled="row.revoked" @click="revoke(row.id)">撤销</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
