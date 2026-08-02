<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../api/http'

type Merchant = { id: number; name: string }
type Member = { id: number; name: string; phone: string }
type AccessPoint = { id: number; name: string }
type Visit = {
  id: number
  member_id: number
  access_point_id: number
  hours: number
  status: string
  created_at: string
}

const merchants = ref<Merchant[]>([])
const members = ref<Member[]>([])
const points = ref<AccessPoint[]>([])
const visits = ref<Visit[]>([])
const merchantId = ref<number | undefined>()

const form = reactive({
  member_id: undefined as number | undefined,
  access_point_id: undefined as number | undefined,
  hours: 2,
})

async function refresh() {
  const { data: m } = await http.get('/merchants')
  merchants.value = m
  if (!merchantId.value && m[0]) merchantId.value = m[0].id
  if (!merchantId.value) return
  const [mem, pts, vs] = await Promise.all([
    http.get('/members', { params: { merchant_id: merchantId.value } }),
    http.get('/access-points', { params: { merchant_id: merchantId.value } }),
    http.get('/visits', { params: { merchant_id: merchantId.value } }),
  ])
  members.value = mem.data
  points.value = pts.data
  visits.value = vs.data
}

async function createVisit() {
  await http.post('/visits', { merchant_id: merchantId.value, ...form })
  ElMessage.success('临访已登记')
  form.hours = 2
  await refresh()
}

async function revokeVisit(id: number) {
  await http.post(`/visits/${id}/revoke`)
  ElMessage.success('已撤销')
  await refresh()
}

onMounted(refresh)
</script>

<template>
  <div>
    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-card header="登记临访" style="margin-bottom: 12px">
      <el-form inline>
        <el-select
          v-model="form.member_id"
          placeholder="会员"
          filterable
          style="width: 200px; margin-right: 8px"
        >
          <el-option
            v-for="m in members"
            :key="m.id"
            :label="`${m.name} (${m.phone})`"
            :value="m.id"
          />
        </el-select>
        <el-select
          v-model="form.access_point_id"
          placeholder="门禁点"
          style="width: 160px; margin-right: 8px"
        >
          <el-option v-for="p in points" :key="p.id" :label="p.name" :value="p.id" />
        </el-select>
        <el-input-number v-model="form.hours" :min="1" :max="72" style="margin-right: 8px" />
        <el-button type="primary" @click="createVisit">登记</el-button>
      </el-form>
    </el-card>

    <el-table :data="visits" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="member_id" label="会员" width="90" />
      <el-table-column prop="access_point_id" label="门禁点" width="90" />
      <el-table-column prop="hours" label="小时" width="80" />
      <el-table-column prop="status" label="状态" width="100" />
      <el-table-column prop="created_at" label="创建时间" />
      <el-table-column label="操作" width="120">
        <template #default="{ row }">
          <el-button
            v-if="row.status === 'active'"
            link
            type="danger"
            @click="revokeVisit(row.id)"
          >
            撤销
          </el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>
