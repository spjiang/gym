<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '../../../core/api/http'
import { useOpsMerchant } from '../../../core/stores/useOpsMerchant'
import CateringDeskSwitch from '../components/CateringDeskSwitch.vue'

type Merchant = { id: number; name: string; subsystem_codes: string[] }
type MenuItem = {
  id: number
  name: string
  category: string
  category_id: number | null
  price: string
  image_url?: string | null
  description?: string | null
  is_active: boolean
}
type Category = { id: number; name: string; sort_order: number; is_active: boolean }
type DeskTable = { id: number; name: string; is_active: boolean }
type Member = { id: number; name: string; phone: string }

const merchants = ref<Merchant[]>([])
const menu = ref<MenuItem[]>([])
const catalog = ref<Category[]>([])
const tables = ref<DeskTable[]>([])
const memberOptions = ref<Member[]>([])
const memberLoading = ref(false)
const { merchantId, requireMerchant } = useOpsMerchant(() => void refresh())
const router = useRouter()
const loading = ref(false)
const paying = ref(false)
const cart = reactive<Record<number, number>>({})
const activeCat = ref<number | ''>('')
const tableNo = ref('')
const note = ref('')
const memberId = ref<number | undefined>()

type Page<T> = { items: T[]; total: number }

async function fetchAllPages<T>(url: string, params: Record<string, unknown>): Promise<T[]> {
  const items: T[] = []
  let page = 1
  const pageSize = 200
  for (;;) {
    const { data } = await http.get<Page<T>>(url, {
      params: { ...params, page, page_size: pageSize },
    })
    items.push(...(data.items || []))
    if (items.length >= (data.total || 0) || !(data.items || []).length) break
    page += 1
    if (page > 20) break
  }
  return items
}

const cateringMerchants = () =>
  merchants.value.filter((m) => (m.subsystem_codes || []).includes('catering'))

const categories = computed(() => {
  const used = new Set(
    menu.value.map((m) => m.category_id).filter((id): id is number => id != null),
  )
  const fromCatalog = catalog.value.filter((c) => c.is_active && used.has(c.id))
  if (fromCatalog.length) return fromCatalog
  const seen: Category[] = []
  for (const item of menu.value) {
    const name = item.category?.trim() || '其他'
    if (!seen.some((c) => c.name === name)) {
      seen.push({ id: item.category_id || 0, name, sort_order: seen.length, is_active: true })
    }
  }
  return seen
})

const visibleMenu = computed(() => {
  if (activeCat.value === '') return menu.value
  return menu.value.filter((m) => m.category_id === activeCat.value)
})

const cartLines = computed(() =>
  menu.value
    .filter((m) => (cart[m.id] || 0) > 0)
    .map((m) => ({
      item: m,
      qty: cart[m.id],
      amount: Number(m.price) * cart[m.id],
    })),
)

const cartCount = computed(() => cartLines.value.reduce((s, l) => s + l.qty, 0))
const cartTotal = computed(() => cartLines.value.reduce((s, l) => s + l.amount, 0))

watch(merchantId, () => {
  activeCat.value = ''
  tableNo.value = ''
  memberId.value = undefined
  memberOptions.value = []
  for (const key of Object.keys(cart)) delete cart[Number(key)]
})

async function searchMembers(keyword: string) {
  const q = keyword.trim()
  if (!q) {
    memberOptions.value = []
    return
  }
  memberLoading.value = true
  try {
    const { data } = await http.get<{ items: Member[] }>('/members', {
      params: { page: 1, page_size: 20, q, merchant_id: merchantId.value },
    })
    memberOptions.value = data.items || []
  } catch {
    memberOptions.value = []
  } finally {
    memberLoading.value = false
  }
}

async function refresh() {
  loading.value = true
  try {
    const { data: ms } = await http.get('/merchants')
    merchants.value = ms
    const list = cateringMerchants()
    if (merchantId.value && !list.some((m) => m.id === merchantId.value)) merchantId.value = undefined
    if (!merchantId.value) {
      menu.value = []
      catalog.value = []
      tables.value = []
      return
    }
    const [menuItems, cats, deskTables] = await Promise.all([
      fetchAllPages<MenuItem>('/catering/menu-items', {
        merchant_id: merchantId.value,
        active_only: true,
      }),
      fetchAllPages<Category>('/catering/categories', {
        merchant_id: merchantId.value,
        is_active: true,
      }),
      fetchAllPages<DeskTable>('/catering/tables', {
        merchant_id: merchantId.value,
        active_only: true,
      }),
    ])
    menu.value = menuItems
    catalog.value = cats
    tables.value = deskTables
    if (activeCat.value !== '' && !categories.value.some((c) => c.id === activeCat.value)) activeCat.value = ''
    if (tableNo.value && !tables.value.some((t) => t.name === tableNo.value)) tableNo.value = ''
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

function add(id: number) {
  cart[id] = (cart[id] || 0) + 1
}

function dec(id: number) {
  const n = (cart[id] || 0) - 1
  if (n <= 0) delete cart[id]
  else cart[id] = n
}

async function checkout() {
  const mid = requireMerchant('吧台点单请先选择餐饮商户')
  if (!mid || !cartLines.value.length) {
    if (mid && !cartLines.value.length) ElMessage.warning('请先选择菜品')
    return
  }
  try {
    await ElMessageBox.confirm(
      `确认收款 ¥${cartTotal.value.toFixed(2)}？共 ${cartCount.value} 件`,
      '吧台收款',
      { type: 'warning', confirmButtonText: '确认收款', cancelButtonText: '返回修改' },
    )
  } catch {
    return
  }
  paying.value = true
  try {
    const { data: order } = await http.post('/catering/checkout', {
      merchant_id: mid,
      items: cartLines.value.map((l) => ({ menu_item_id: l.item.id, quantity: l.qty })),
      table_no: tableNo.value.trim() || null,
      note: note.value.trim() || null,
      member_id: memberId.value || null,
    })
    const { data: paid } = await http.post(`/orders/${order.id}/pay/offline`, { channel: 'offline_cash' })
    const pickup = paid.pickup_code ? `取餐号 ${paid.pickup_code}` : `订单 #${paid.id || order.id}`
    ElMessage.success(`收款成功 ¥${paid.amount ?? order.amount}，${pickup} 已送出餐看板`)
    for (const key of Object.keys(cart)) delete cart[Number(key)]
    tableNo.value = ''
    note.value = ''
    memberId.value = undefined
    await router.replace({ name: 'catering-kitchen', query: { ticket: String(paid.id || order.id) } })
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '点单失败')
  } finally {
    paying.value = false
  }
}

onMounted(refresh)
</script>

<template>
  <div v-loading="loading">
    <CateringDeskSwitch />
    <div class="toolbar">
      <el-form inline>
        <el-form-item label="餐饮商户">
          <el-select v-model="merchantId" clearable placeholder="请选择商户" style="width: 220px">
            <el-option v-for="m in cateringMerchants()" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
      </el-form>
    </div>

    <el-alert
      v-if="!cateringMerchants().length"
      type="warning"
      :closable="false"
      title="没有餐饮商户"
      style="margin-bottom: 16px"
    />
    <el-alert
      v-else-if="!merchantId"
      type="info"
      :closable="false"
      title="请先选择餐饮商户后再点单"
      style="margin-bottom: 16px"
    />

    <div v-if="cateringMerchants().length && merchantId" class="layout">
      <section class="menu">
        <nav v-if="categories.length" class="cats" aria-label="菜品分类">
          <button
            type="button"
            class="cats__item"
            :class="{ 'is-on': activeCat === '' }"
            @click="activeCat = ''"
          >
            全部
          </button>
          <button
            v-for="cat in categories"
            :key="cat.id"
            type="button"
            class="cats__item"
            :class="{ 'is-on': activeCat === cat.id }"
            @click="activeCat = cat.id"
          >
            {{ cat.name }}
          </button>
        </nav>

        <div v-if="visibleMenu.length" class="grid">
          <article
            v-for="m in visibleMenu"
            :key="m.id"
            class="dish"
            :class="{ 'is-on': (cart[m.id] || 0) > 0 }"
            @click="add(m.id)"
          >
            <div class="dish__media">
              <img v-if="m.image_url" :src="m.image_url" :alt="m.name" />
              <span v-else>{{ m.name.slice(0, 1) }}</span>
              <em v-if="(cart[m.id] || 0) > 0" class="dish__badge">{{ cart[m.id] }}</em>
            </div>
            <div class="dish__body">
              <strong class="dish__name">{{ m.name }}</strong>
              <p v-if="m.description" class="dish__desc">{{ m.description }}</p>
              <div class="dish__foot">
                <span class="dish__price">¥{{ m.price }}</span>
                <div class="qty" @click.stop>
                  <button type="button" :disabled="!(cart[m.id] > 0)" aria-label="减少" @click="dec(m.id)">−</button>
                  <span>{{ cart[m.id] || 0 }}</span>
                  <button type="button" class="plus" aria-label="增加" @click="add(m.id)">+</button>
                </div>
              </div>
            </div>
          </article>
        </div>
        <div v-else class="empty">{{ menu.length ? '该分类暂无菜品' : '暂无在售菜品，请先维护菜单' }}</div>
      </section>

      <aside class="cart">
        <h4>当前点单 <span v-if="cartCount">{{ cartCount }} 份</span></h4>
        <div v-for="l in cartLines" :key="l.item.id" class="cart-line">
          <div class="cart-line__info">
            <strong>{{ l.item.name }}</strong>
            <span>¥{{ Number(l.item.price).toFixed(2) }}</span>
          </div>
          <div class="qty" @click.stop>
            <button type="button" aria-label="减少" @click="dec(l.item.id)">−</button>
            <span>{{ l.qty }}</span>
            <button type="button" class="plus" aria-label="增加" @click="add(l.item.id)">+</button>
          </div>
          <span class="cart-line__amt">¥{{ l.amount.toFixed(2) }}</span>
        </div>
        <div v-if="!cartLines.length" class="empty">点卡片即可加购</div>
        <el-select v-model="tableNo" clearable filterable placeholder="散客 / 未选桌" style="width: 100%; margin-bottom: 8px">
          <el-option v-for="t in tables" :key="t.id" :label="t.name" :value="t.name" />
        </el-select>
        <el-input v-model="note" placeholder="备注（少冰 / 去冰）" clearable style="margin-bottom: 8px" />
        <el-select
          v-model="memberId"
          filterable
          remote
          clearable
          :remote-method="searchMembers"
          :loading="memberLoading"
          placeholder="搜索会员手机号 / 姓名"
          style="width: 100%; margin-bottom: 8px"
        >
          <el-option
            v-for="m in memberOptions"
            :key="m.id"
            :label="`${m.name} ${m.phone}`"
            :value="m.id"
          />
        </el-select>
        <div class="total">合计 <b>¥{{ cartTotal.toFixed(2) }}</b></div>
        <el-button type="primary" :loading="paying" :disabled="!cartLines.length" @click="checkout">
          下单并线下收款
        </el-button>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}
.layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 320px;
  gap: 20px;
  align-items: start;
}
.cats {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}
.cats__item {
  min-height: 34px;
  padding: 0 14px;
  border-radius: 999px;
  border: 1px solid rgba(28, 25, 23, 0.12);
  background: #fff;
  color: var(--admin-ink-muted, #78716c);
  font: inherit;
  font-size: 13px;
  font-weight: 650;
  cursor: pointer;
}
.cats__item.is-on {
  background: var(--admin-accent, #f36b21);
  border-color: var(--admin-accent, #f36b21);
  color: #fff;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(128px, 1fr));
  gap: 10px;
}
.dish {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  border: 1px solid rgba(28, 25, 23, 0.1);
  border-radius: 12px;
  background: #fff;
  cursor: pointer;
  text-align: left;
  box-shadow: 0 2px 10px rgba(28, 25, 23, 0.04);
  transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
}
.dish:hover {
  transform: translateY(-1px);
  border-color: rgba(243, 107, 33, 0.4);
}
.dish.is-on {
  border-color: var(--admin-accent, #f36b21);
  box-shadow: 0 6px 16px rgba(243, 107, 33, 0.12);
}
.dish__media {
  position: relative;
  aspect-ratio: 1;
  display: grid;
  place-items: center;
  background: linear-gradient(160deg, #fde7d4, #f7efe2);
  color: var(--admin-accent-strong, #d85a16);
  font-size: 1.45rem;
  font-weight: 800;
  overflow: hidden;
}
.dish__media img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.dish__badge {
  position: absolute;
  top: 6px;
  right: 6px;
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  border-radius: 999px;
  background: var(--admin-accent, #f36b21);
  color: #fff;
  font-size: 11px;
  font-style: normal;
  font-weight: 800;
  line-height: 20px;
  text-align: center;
}
.dish__body {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 8px 9px;
  min-height: 72px;
}
.dish__name {
  font-size: 13px;
  line-height: 1.3;
}
.dish__desc {
  margin: 0;
  font-size: 11px;
  color: var(--admin-ink-muted, #78716c);
  display: -webkit-box;
  -webkit-line-clamp: 1;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.dish__foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  margin-top: auto;
}
.dish__price {
  color: var(--admin-accent-strong, #d85a16);
  font-size: 13px;
  font-weight: 800;
}
.qty {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
}
.qty span {
  min-width: 1em;
  text-align: center;
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
}
.qty button {
  width: 22px;
  height: 22px;
  padding: 0;
  border-radius: 50%;
  border: 1px solid rgba(28, 25, 23, 0.14);
  background: #fff;
  color: inherit;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
}
.qty button:disabled {
  opacity: 0.35;
  cursor: default;
}
.qty .plus {
  background: var(--admin-accent, #f36b21);
  border-color: var(--admin-accent, #f36b21);
  color: #fff;
}
.cart {
  position: sticky;
  top: 16px;
  padding: 16px;
  border: 1px solid rgba(28, 25, 23, 0.08);
  border-radius: 16px;
  background: #fffcf8;
}
.cart h4 {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
  margin: 0 0 8px;
}
.cart h4 span {
  font-size: 13px;
  font-weight: 600;
  color: var(--admin-ink-muted, #78716c);
}
.cart-line {
  display: grid;
  grid-template-columns: 1fr auto auto;
  align-items: center;
  gap: 8px;
  padding: 10px 0;
  border-bottom: 1px solid rgba(28, 25, 23, 0.08);
}
.cart-line__info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.cart-line__info strong {
  font-size: 13px;
}
.cart-line__info span,
.cart-line__amt {
  font-size: 12px;
  color: var(--admin-ink-muted, #78716c);
}
.cart-line__amt {
  font-weight: 700;
  color: var(--admin-ink, #1c1917);
}
.total {
  margin: 14px 0;
  font-size: 16px;
}
.empty {
  color: var(--admin-ink-muted);
  font-size: 13px;
  padding: 12px 0;
}
@media (max-width: 980px) {
  .layout {
    grid-template-columns: 1fr;
  }
  .cart {
    position: static;
  }
}
</style>
