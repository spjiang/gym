/** 小程序点餐购物车：按商户隔离，本地持久化。 */

const KEY = 'mp_catering_cart'

function empty() {
  return { qty: {}, note: '', tableNo: '', tableLocked: false, couponId: null }
}

function readAll() {
  try {
    return wx.getStorageSync(KEY) || {}
  } catch (e) {
    return {}
  }
}

function writeAll(all) {
  wx.setStorageSync(KEY, all)
}

function ensure(merchantId) {
  const all = readAll()
  const key = String(merchantId)
  if (!all[key]) all[key] = empty()
  return { all, key, cart: all[key] }
}

function qtyMap(merchantId) {
  return ensure(merchantId).cart.qty
}

function setQty(merchantId, itemId, quantity) {
  const { all, key, cart } = ensure(merchantId)
  const next = Math.min(99, Math.max(0, Math.floor(quantity)))
  if (next <= 0) delete cart.qty[itemId]
  else cart.qty[itemId] = next
  all[key] = cart
  writeAll(all)
}

function add(merchantId, itemId) {
  setQty(merchantId, itemId, (qtyMap(merchantId)[itemId] || 0) + 1)
}

function sub(merchantId, itemId) {
  setQty(merchantId, itemId, (qtyMap(merchantId)[itemId] || 0) - 1)
}

function count(merchantId) {
  return Object.values(qtyMap(merchantId)).reduce((sum, n) => sum + n, 0)
}

function linesOf(merchantId, items) {
  const qty = qtyMap(merchantId)
  return (items || [])
    .filter((i) => (qty[i.id] || 0) > 0)
    .map((i) => ({ ...i, quantity: qty[i.id] }))
}

function noteOf(merchantId) {
  return ensure(merchantId).cart.note || ''
}

function setNote(merchantId, note) {
  const { all, key, cart } = ensure(merchantId)
  cart.note = note || ''
  all[key] = cart
  writeAll(all)
}

function tableNoOf(merchantId) {
  return ensure(merchantId).cart.tableNo || ''
}

function tableLockedOf(merchantId) {
  return Boolean(ensure(merchantId).cart.tableLocked)
}

function setTableNo(merchantId, tableNo) {
  const { all, key, cart } = ensure(merchantId)
  cart.tableNo = tableNo || ''
  cart.tableLocked = false
  all[key] = cart
  writeAll(all)
}

function lockTable(merchantId, tableNo) {
  const { all, key, cart } = ensure(merchantId)
  cart.tableNo = tableNo || ''
  cart.tableLocked = true
  all[key] = cart
  writeAll(all)
}

function couponOf(merchantId) {
  const id = ensure(merchantId).cart.couponId
  return id ? Number(id) : null
}

function setCoupon(merchantId, couponId) {
  const { all, key, cart } = ensure(merchantId)
  cart.couponId = couponId || null
  all[key] = cart
  writeAll(all)
}

function clear(merchantId) {
  const { all, key, cart } = ensure(merchantId)
  all[key] = {
    ...empty(),
    tableNo: cart.tableLocked ? cart.tableNo : '',
    tableLocked: Boolean(cart.tableLocked),
  }
  writeAll(all)
}

module.exports = {
  qtyMap,
  setQty,
  add,
  sub,
  count,
  linesOf,
  noteOf,
  setNote,
  tableNoOf,
  tableLockedOf,
  setTableNo,
  lockTable,
  couponOf,
  setCoupon,
  clear,
}
