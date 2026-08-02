<script setup lang="ts">
import { onMounted, ref } from 'vue'
import http from '../api/http'

type Merchant = { id: number; name: string }
type Note = {
  id: number
  merchant_id: number | null
  member_id: number | null
  event_type: string
  title: string
  body: string
  created_at: string
}

const merchants = ref<Merchant[]>([])
const notes = ref<Note[]>([])
const merchantId = ref<number | undefined>()

async function refresh() {
  const { data: m } = await http.get('/merchants')
  merchants.value = m
  if (!merchantId.value && m[0]) merchantId.value = m[0].id
  const { data } = await http.get('/notifications', {
    params: { merchant_id: merchantId.value || undefined },
  })
  notes.value = data
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
      <el-button @click="refresh">刷新</el-button>
    </el-form>

    <el-table :data="notes" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="event_type" label="事件" width="160" />
      <el-table-column prop="title" label="标题" width="160" />
      <el-table-column prop="body" label="内容" />
      <el-table-column prop="member_id" label="会员" width="90" />
      <el-table-column prop="created_at" label="时间" width="200" />
    </el-table>
  </div>
</template>
