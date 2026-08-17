<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import http from '../../../core/api/http'
import { menusForSystemFromNav, merchantsWithSystem } from '../../../core/nav/systems'
import { useAuthStore } from '../../../core/stores/auth'
import { useOpsStore, type OpsSubsystem } from '../../../core/stores/ops'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }

const auth = useAuthStore()
const ops = useOpsStore()
const router = useRouter()
const merchants = ref<Merchant[]>([])

const scopedMerchants = computed(() => merchantsWithSystem(merchants.value, ops.subsystem))
const modules = computed(() => menusForSystemFromNav(auth, ops.subsystem))
const subsystemLabel = computed(() => (ops.subsystem === 'catering' ? '观野BAR' : '观野FIT'))

async function loadMerchants() {
  try {
    const { data } = await http.get<Merchant[]>('/merchants')
    merchants.value = data
    if (ops.merchantId && !scopedMerchants.value.some((m) => m.id === ops.merchantId)) {
      ops.setMerchantId(null)
    }
  } catch {
    merchants.value = []
  }
}

function setSubsystem(code: OpsSubsystem) {
  ops.setSubsystem(code)
  if (ops.merchantId && !merchantsWithSystem(merchants.value, code).some((m) => m.id === ops.merchantId)) {
    ops.setMerchantId(null)
  }
}

function openModule(path: string) {
  router.push(path)
}

onMounted(loadMerchants)
</script>

<template>
  <div>
    <div class="toolbar">
      <div>
        <h3>经营工作台</h3>
        <p class="hint">先选业务子系统，再进入对应功能。商户可留空，表示查看该子系统下全部商户数据。</p>
      </div>
    </div>

    <div class="filters">
      <el-radio-group :model-value="ops.subsystem" @change="setSubsystem">
        <el-radio-button value="gym">观野FIT</el-radio-button>
        <el-radio-button value="catering">观野BAR</el-radio-button>
      </el-radio-group>
      <el-select
        :model-value="ops.merchantId ?? undefined"
        clearable
        placeholder="全部商户"
        style="width: 220px"
        @change="(v: number | undefined) => ops.setMerchantId(v ?? null)"
      >
        <el-option v-for="m in scopedMerchants" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
    </div>

    <el-alert
      type="info"
      :closable="false"
      :title="`当前：${subsystemLabel}${ops.merchantId ? ' · 已选商户' : ' · 全部商户'}`"
      style="margin-bottom: 16px"
    />

    <div v-if="modules.length" class="cards">
      <button v-for="m in modules" :key="m.path" type="button" class="card" @click="openModule(m.path)">
        <div class="card-title">{{ m.label }}</div>
        <div class="card-sub">进入{{ subsystemLabel }}功能</div>
      </button>
    </div>
    <el-empty v-else description="当前账号在该子系统下暂无可用功能" />
  </div>
</template>

<style scoped>
.toolbar h3 {
  margin: 0 0 6px;
}
.hint {
  margin: 0 0 16px;
  font-size: 13px;
  color: var(--admin-ink-muted);
}
.filters {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}
.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}
.card {
  text-align: left;
  border: 1px solid rgba(28, 25, 23, 0.08);
  background: #fffcf8;
  border-radius: 14px;
  padding: 16px;
  cursor: pointer;
  font: inherit;
}
.card:hover {
  border-color: rgba(61, 107, 92, 0.35);
  box-shadow: 0 8px 20px -16px rgba(28, 25, 23, 0.45);
}
.card-title {
  font-weight: 700;
  color: var(--admin-ink);
}
.card-sub {
  margin-top: 6px;
  font-size: 12px;
  color: var(--admin-ink-muted);
}
</style>
