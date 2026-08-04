<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import http from '../api/http'
import { merchantsWithSystem } from '../nav/systems'

type Merchant = { id: number; name: string; subsystem_codes?: string[] }
type Point = { id: number; name: string; merchant_id: number | null }
type Product = {
  id: number
  name: string
  product_type: string
  price: string
  duration_days: number | null
  is_active: boolean
  is_trial: boolean
  access_point_ids: number[]
}

type CardGuide = {
  key: string
  title: string
  summary: string
  points: string[]
  tip: string
}

const TYPE_GUIDES: CardGuide[] = [
  {
    key: 'term',
    title: '期限卡',
    summary: '按有效天数计时，到期后自动失效。适合月卡、季卡、年卡等固定周期产品。',
    points: ['必填「天数」：从开通日起算的有效期', '有效期内通常不限次入场（以门禁授权为准）', '续费可延长有效期，需在办卡会籍中操作'],
    tip: '示例：标准月卡 30 天 / ¥299；季卡 90 天 / ¥799。',
  },
  {
    key: 'count',
    title: '次卡',
    summary: '按剩余次数扣减，适合低频到店或体验式消费。',
    points: ['必填「次数」：办卡后写入剩余次数', '每次核销/通行策略由后续履约与门禁规则决定', '次数用尽后不可继续作为有效会籍售卖权益'],
    tip: '示例：次卡 10 次 / ¥399，适合不固定出勤的会员。',
  },
  {
    key: 'value',
    title: '储值卡',
    summary: '预存金额到会籍余额，后续可按消费扣减（零售/课程等场景扩展）。',
    points: ['必填「储值」额度：开通后写入余额', '售价可与储值面额一致，也可另设优惠售价', '余额为 0 后需续充或重新办卡'],
    tip: '示例：储值卡面额 ¥500，售价可设为 ¥500 或活动价。',
  },
]

const router = useRouter()
const merchants = ref<Merchant[]>([])
const points = ref<Point[]>([])
const products = ref<Product[]>([])
const merchantId = ref<number | undefined>()
const loading = ref(false)

const dialogVisible = ref(false)
const creating = ref(false)
const formRef = ref<FormInstance>()

const form = reactive({
  name: '',
  product_type: 'term',
  price: '299.00',
  duration_days: 30 as number | null,
  session_count: null as number | null,
  stored_value: null as string | null,
  access_point_ids: [] as number[],
  is_active: true,
  is_trial: false,
  promo_price: '' as string,
  promo_days: 0,
})

const noPoints = computed(() => points.value.length === 0)
const activeGuide = computed(() => TYPE_GUIDES.find((g) => g.key === form.product_type) || TYPE_GUIDES[0])

const typeLabel: Record<string, string> = {
  term: '期限卡',
  count: '次卡',
  value: '储值卡',
}

const rules: FormRules = {
  name: [{ required: true, message: '请填写卡种名称', trigger: 'blur' }],
  price: [
    { required: true, message: '请填写价格', trigger: 'blur' },
    {
      validator: (_r, v: string, cb) => {
        const n = Number(v)
        if (!Number.isFinite(n) || n <= 0) cb(new Error('价格必须大于 0'))
        else cb()
      },
      trigger: 'blur',
    },
  ],
}

watch(
  () => form.product_type,
  (t) => {
    if (t === 'term' && !form.duration_days) form.duration_days = 30
    if (t === 'count' && !form.session_count) form.session_count = 10
    if (t === 'value' && !form.stored_value) form.stored_value = form.price || '500.00'
  },
)

async function loadMerchants() {
  const { data } = await http.get('/merchants')
  merchants.value = merchantsWithSystem(data, 'gym')
  if (!merchantId.value && merchants.value[0]) merchantId.value = merchants.value[0].id
  if (merchantId.value && !merchants.value.some((m) => m.id === merchantId.value)) {
    merchantId.value = merchants.value[0]?.id
  }
}

async function loadPoints() {
  if (!merchantId.value) return
  const { data } = await http.get('/access-points')
  points.value = data.filter(
    (p: Point) => p.merchant_id === merchantId.value || p.merchant_id == null,
  )
}

async function loadProducts() {
  if (!merchantId.value) return
  const { data } = await http.get('/membership-products', { params: { merchant_id: merchantId.value } })
  products.value = data
}

async function refresh() {
  loading.value = true
  try {
    await loadMerchants()
    await loadPoints()
    await loadProducts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function openDialog() {
  form.name = ''
  form.product_type = 'term'
  form.price = '299.00'
  form.duration_days = 30
  form.session_count = null
  form.stored_value = null
  form.access_point_ids = []
  form.is_active = true
  form.is_trial = false
  form.promo_price = ''
  form.promo_days = 0
  // 默认勾选本商户门禁点，公共门可选
  const own = points.value.filter((p) => p.merchant_id === merchantId.value)
  form.access_point_ids = own.length
    ? own.map((p) => p.id)
    : points.value.length
      ? [points.value[0].id]
      : []
  formRef.value?.clearValidate()
  dialogVisible.value = true
}

async function create() {
  const ok = await formRef.value?.validate().catch(() => false)
  if (!ok) return
  if (form.is_active && form.access_point_ids.length === 0) {
    ElMessage.warning(
      noPoints.value
        ? '请先去「门禁设备」创建门禁点，再绑定后启用售卖'
        : '启用售卖时必须选择至少一个门禁点',
    )
    return
  }
  creating.value = true
  try {
    const payload: Record<string, unknown> = {
      ...form,
      merchant_id: merchantId.value,
      name: form.name.trim(),
    }
    if (form.promo_price && form.promo_days > 0) {
      const starts = new Date()
      const ends = new Date()
      ends.setDate(ends.getDate() + form.promo_days)
      payload.promo_price = form.promo_price
      payload.promo_starts_at = starts.toISOString()
      payload.promo_ends_at = ends.toISOString()
    } else {
      payload.promo_price = null
      payload.promo_starts_at = null
      payload.promo_ends_at = null
    }
    delete payload.promo_days
    await http.post('/membership-products', payload)
    ElMessage.success('卡种已创建')
    dialogVisible.value = false
    await loadProducts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '创建失败')
  } finally {
    creating.value = false
  }
}

async function deactivate(id: number) {
  try {
    await http.post(`/membership-products/${id}/deactivate`)
    ElMessage.success('已停用')
    await loadProducts()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '停用失败')
  }
}

function goAccess() {
  dialogVisible.value = false
  router.push('/access')
}

function selectGuide(key: string) {
  form.product_type = key
}

onMounted(refresh)
</script>

<template>
  <div>
    <div class="toolbar">
      <h3>会籍卡种</h3>
      <el-button type="primary" @click="openDialog">新建卡种</el-button>
    </div>

    <el-form inline>
      <el-form-item label="商户">
        <el-select v-model="merchantId" style="width: 200px" @change="refresh">
          <el-option v-for="m in merchants" :key="m.id" :label="m.name" :value="m.id" />
        </el-select>
      </el-form-item>
    </el-form>

    <el-alert
      v-if="noPoints"
      type="warning"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <template #title>当前商户还没有可用门禁点</template>
      <p style="margin: 4px 0 10px">
        启用售卖的卡种必须绑定门禁点。请先在「综合经营 → 门禁设备」创建门禁点，或关闭「启用售卖」以草稿保存。
      </p>
      <el-button size="small" type="warning" @click="goAccess">去创建门禁点</el-button>
    </el-alert>

    <el-table :data="products" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="70" />
      <el-table-column prop="name" label="名称" />
      <el-table-column label="类型" width="100">
        <template #default="{ row }">{{ typeLabel[row.product_type] || row.product_type }}</template>
      </el-table-column>
      <el-table-column label="体验" width="70">
        <template #default="{ row }">{{ row.is_trial ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column prop="price" label="价格" width="120" />
      <el-table-column label="在售" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? '在售' : '草稿' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="门禁" min-width="140">
        <template #default="{ row }">
          <el-tag
            v-for="id in row.access_point_ids"
            :key="id"
            size="small"
            effect="plain"
            style="margin-right: 6px"
          >
            {{ points.find((p) => p.id === id)?.name || `#${id}` }}
          </el-tag>
          <span v-if="!row.access_point_ids.length">—</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="110">
        <template #default="{ row }">
          <el-button size="small" :disabled="!row.is_active" @click="deactivate(row.id)">停用</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新建卡种弹窗 -->
    <el-dialog v-model="dialogVisible" title="新建卡种" width="820px" destroy-on-close>
      <div class="create-layout">
        <section class="create-form">
          <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
            <el-form-item label="名称" prop="name">
              <el-input v-model="form.name" placeholder="必填，如：标准月卡" maxlength="64" />
            </el-form-item>
            <el-form-item label="类型">
              <el-select v-model="form.product_type" style="width: 100%">
                <el-option label="期限卡" value="term" />
                <el-option label="次卡" value="count" />
                <el-option label="储值卡" value="value" />
              </el-select>
            </el-form-item>
            <el-form-item label="价格" prop="price">
              <el-input v-model="form.price" />
            </el-form-item>
            <el-form-item v-if="form.product_type === 'term'" label="天数">
              <el-input-number v-model="form.duration_days" :min="1" style="width: 100%" />
            </el-form-item>
            <el-form-item v-if="form.product_type === 'count'" label="次数">
              <el-input-number v-model="form.session_count" :min="1" style="width: 100%" />
            </el-form-item>
            <el-form-item v-if="form.product_type === 'value'" label="储值">
              <el-input v-model="form.stored_value" />
            </el-form-item>
            <el-form-item label="门禁点" :required="form.is_active">
              <el-select
                v-model="form.access_point_ids"
                multiple
                style="width: 100%"
                :placeholder="noPoints ? '暂无门禁点，请先创建' : '请选择门禁点（可多选）'"
              >
                <el-option v-for="p in points" :key="p.id" :label="p.name" :value="p.id" />
              </el-select>
            </el-form-item>
            <el-form-item label="体验卡">
              <el-switch v-model="form.is_trial" />
            </el-form-item>
            <el-form-item label="活动价">
              <el-input v-model="form.promo_price" placeholder="可选" />
            </el-form-item>
            <el-form-item label="活动天数">
              <el-input-number v-model="form.promo_days" :min="0" style="width: 100%" />
            </el-form-item>
            <el-form-item label="启用售卖">
              <el-switch v-model="form.is_active" />
            </el-form-item>
          </el-form>
        </section>

        <aside class="type-guide" aria-label="卡种类型说明">
          <header class="guide-header">
            <p class="eyebrow">卡种说明</p>
            <h3>给管理员的配置指引</h3>
            <p class="lead">切换类型时右侧高亮对应说明，也可直接点卡片切换。</p>
          </header>

          <div class="guide-list">
            <button
              v-for="g in TYPE_GUIDES"
              :key="g.key"
              type="button"
              class="guide-card"
              :class="{ active: form.product_type === g.key }"
              @click="selectGuide(g.key)"
            >
              <div class="guide-card-top">
                <span class="badge">{{ g.title }}</span>
                <span v-if="form.product_type === g.key" class="current">当前</span>
              </div>
              <p class="summary">{{ g.summary }}</p>
              <ul>
                <li v-for="(p, i) in g.points" :key="i">{{ p }}</li>
              </ul>
              <p class="tip">{{ g.tip }}</p>
            </button>
          </div>
        </aside>
      </div>
      <template #footer>
        <div class="dialog-footer">
          <span class="focus-line">
            当前编辑：<strong>{{ activeGuide.title }}</strong>
            <span v-if="form.is_trial"> · 体验卡</span>
          </span>
          <div>
            <el-button @click="dialogVisible = false">取消</el-button>
            <el-button type="primary" :loading="creating" @click="create">创建</el-button>
          </div>
        </div>
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

.create-layout {
  display: grid;
  grid-template-columns: minmax(320px, 1fr) minmax(260px, 340px);
  gap: 20px;
  align-items: start;
}

.type-guide {
  position: sticky;
  top: 0;
  padding: 16px;
  border-radius: 14px;
  background: linear-gradient(160deg, rgba(61, 107, 92, 0.08), transparent 42%), var(--admin-surface-elevated);
  border: 1px solid var(--admin-line);
  max-height: 520px;
  overflow: auto;
}

.guide-header .eyebrow {
  margin: 0 0 4px;
  font-size: 0.72rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--admin-copper);
  font-weight: 600;
}

.guide-header h3 {
  margin: 0 0 6px;
  font-size: 1.05rem;
}

.guide-header .lead {
  margin: 0 0 12px;
  color: var(--admin-ink-muted);
  font-size: 0.82rem;
  line-height: 1.5;
}

.guide-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.guide-card {
  text-align: left;
  width: 100%;
  padding: 10px 12px;
  border-radius: 12px;
  border: 1px solid rgba(28, 25, 23, 0.08);
  background: rgba(255, 255, 255, 0.72);
  cursor: pointer;
  transition: border-color 0.18s ease, box-shadow 0.18s ease, transform 0.18s ease;
  font: inherit;
  color: inherit;
}

.guide-card:hover {
  border-color: rgba(61, 107, 92, 0.35);
  transform: translateY(-1px);
}

.guide-card.active {
  border-color: var(--admin-accent);
  box-shadow: 0 0 0 1px rgba(61, 107, 92, 0.2), 0 10px 24px -18px rgba(47, 85, 73, 0.55);
  background: #fff;
}

.guide-card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 999px;
  background: var(--admin-accent-soft);
  color: var(--admin-accent-strong);
  font-size: 0.76rem;
  font-weight: 600;
}

.current {
  font-size: 0.72rem;
  color: var(--admin-accent);
  font-weight: 600;
}

.summary {
  margin: 0 0 6px;
  font-size: 0.84rem;
  line-height: 1.45;
}

.guide-card ul {
  margin: 0;
  padding-left: 1.05rem;
  color: var(--admin-ink-muted);
  font-size: 0.78rem;
  line-height: 1.55;
}

.tip {
  margin: 6px 0 0;
  font-size: 0.76rem;
  color: var(--admin-copper);
}

.focus-line {
  font-size: 0.82rem;
  color: var(--admin-ink-muted);
}

.focus-line strong {
  color: var(--admin-ink);
}

.dialog-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  width: 100%;
}

@media (max-width: 640px) {
  .create-layout {
    grid-template-columns: 1fr;
  }

  .type-guide {
    position: static;
    max-height: none;
  }
}
</style>
