<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'

type Check = { ok: boolean; detail: string | null }
type Health = {
  status: string
  postgres: Check
  minio: Check
  error_count_24h: number
}

const loading = ref(false)
const data = ref<Health | null>(null)

const statusType = computed(() => {
  const s = data.value?.status
  if (s === 'ok') return 'success'
  if (s === 'degraded') return 'warning'
  return 'danger'
})

const statusLabel = computed(() => {
  const s = data.value?.status
  if (s === 'ok') return '正常'
  if (s === 'degraded') return '降级（对象存储异常）'
  if (s === 'fail') return '不可用'
  return '未知'
})

async function refresh() {
  loading.value = true
  try {
    const { data: body } = await http.get<Health>('/ops/health-status')
    data.value = body
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <div>
        <h3>服务状态</h3>
        <p class="hint">探查 Postgres 与 MinIO。进程探活仍走公开 /health，Docker 不会因存储抖动反复重启。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="refresh">刷新</el-button>
    </div>

    <el-alert
      v-if="data"
      class="banner"
      :type="statusType"
      :title="`总体：${statusLabel}`"
      :closable="false"
      show-icon
    />

    <el-row :gutter="16">
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="never">
          <template #header>PostgreSQL</template>
          <el-tag :type="data?.postgres.ok ? 'success' : 'danger'" size="large">
            {{ data?.postgres.ok ? '就绪' : '异常' }}
          </el-tag>
          <p v-if="data?.postgres.detail" class="detail">{{ data.postgres.detail }}</p>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="never">
          <template #header>MinIO 对象存储</template>
          <el-tag :type="data?.minio.ok ? 'success' : 'warning'" size="large">
            {{ data?.minio.ok ? '就绪' : '降级' }}
          </el-tag>
          <p v-if="data?.minio.detail" class="detail">{{ data.minio.detail }}</p>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card shadow="never">
          <template #header>近 24 小时错误</template>
          <div class="count">{{ data?.error_count_24h ?? '—' }}</div>
          <p class="detail">条系统错误事件</p>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0 0 4px;
}
.hint {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
}
.banner {
  margin-bottom: 16px;
}
.detail {
  margin: 12px 0 0;
  color: var(--el-text-color-secondary);
  font-size: 13px;
  word-break: break-all;
}
.count {
  font-size: 28px;
  font-weight: 600;
}
</style>
