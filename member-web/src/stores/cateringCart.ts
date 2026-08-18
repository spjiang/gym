import { defineStore } from 'pinia'
import { reactive, watch } from 'vue'

const STORAGE_KEY = 'mw-catering-cart-v1'

type MerchantCart = {
  qty: Record<number, number>
  note: string
  couponId: number | null
  tableNo: string
  tableLocked: boolean
}

function emptyCart(): MerchantCart {
  return { qty: {}, note: '', couponId: null, tableNo: '', tableLocked: false }
}

function parseStored(): Record<number, MerchantCart> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw) as Record<string, Partial<MerchantCart>>
    const out: Record<number, MerchantCart> = {}
    for (const [key, value] of Object.entries(parsed || {})) {
      const merchantId = Number(key)
      if (!merchantId) continue
      const qty: Record<number, number> = {}
      for (const [itemKey, n] of Object.entries(value.qty || {})) {
        const itemId = Number(itemKey)
        const count = Number(n)
        if (itemId && count > 0) qty[itemId] = Math.min(99, Math.floor(count))
      }
      out[merchantId] = {
        qty,
        note: String(value.note || ''),
        couponId: value.couponId ? Number(value.couponId) : null,
        tableNo: String(value.tableNo || ''),
        tableLocked: Boolean(value.tableLocked),
      }
    }
    return out
  } catch {
    return {}
  }
}

/** 点餐购物车：列表 / 详情 / 结算共用，按商户隔离并本地持久化。 */
export const useCateringCart = defineStore('catering-cart', () => {
  const carts = reactive<Record<number, MerchantCart>>(parseStored())

  watch(
    carts,
    (value) => {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
    },
    { deep: true },
  )

  function ensure(merchantId: number): MerchantCart {
    if (!carts[merchantId]) carts[merchantId] = emptyCart()
    return carts[merchantId]
  }

  function qtyMap(merchantId: number) {
    return ensure(merchantId).qty
  }

  function qtyOf(merchantId: number, itemId: number) {
    return carts[merchantId]?.qty[itemId] || 0
  }

  function setQty(merchantId: number, itemId: number, quantity: number) {
    const cart = ensure(merchantId)
    const next = Math.min(99, Math.max(0, Math.floor(quantity)))
    if (next <= 0) delete cart.qty[itemId]
    else cart.qty[itemId] = next
  }

  function add(merchantId: number, itemId: number) {
    setQty(merchantId, itemId, qtyOf(merchantId, itemId) + 1)
  }

  function sub(merchantId: number, itemId: number) {
    setQty(merchantId, itemId, qtyOf(merchantId, itemId) - 1)
  }

  function count(merchantId: number) {
    return Object.values(ensure(merchantId).qty).reduce((sum, n) => sum + n, 0)
  }

  function noteOf(merchantId: number) {
    return ensure(merchantId).note
  }

  function setNote(merchantId: number, note: string) {
    ensure(merchantId).note = note
  }

  function couponOf(merchantId: number) {
    return ensure(merchantId).couponId
  }

  function setCoupon(merchantId: number, id: number | null) {
    ensure(merchantId).couponId = id
  }

  function tableNoOf(merchantId: number) {
    return ensure(merchantId).tableNo
  }

  function setTableNo(merchantId: number, tableNo: string) {
    const cart = ensure(merchantId)
    cart.tableNo = tableNo
    cart.tableLocked = false
  }

  function tableLockedOf(merchantId: number) {
    return ensure(merchantId).tableLocked
  }

  function lockTable(merchantId: number, tableNo: string) {
    const cart = ensure(merchantId)
    cart.tableNo = tableNo
    cart.tableLocked = true
  }

  function fill(merchantId: number, lines: { id: number; quantity: number }[]) {
    const cart = ensure(merchantId)
    for (const line of lines) {
      if (!line.id || line.quantity <= 0) continue
      cart.qty[line.id] = Math.min(99, (cart.qty[line.id] || 0) + line.quantity)
    }
  }

  function clear(merchantId: number) {
    const prev = carts[merchantId]
    carts[merchantId] = {
      ...emptyCart(),
      tableNo: prev?.tableLocked ? prev.tableNo : '',
      tableLocked: Boolean(prev?.tableLocked),
    }
  }

  return {
    carts,
    qtyMap,
    qtyOf,
    setQty,
    add,
    sub,
    count,
    noteOf,
    setNote,
    couponOf,
    setCoupon,
    tableNoOf,
    setTableNo,
    tableLockedOf,
    lockTable,
    fill,
    clear,
  }
})
