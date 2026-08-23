/** 商户业态与路由，与 member-web stores/auth 对齐。 */

function systemOf(m) {
  if (!m) return 'other'
  return m.primary_system || (m.subsystem_codes && m.subsystem_codes[0]) || 'other'
}

function pathForMerchant(m) {
  if (systemOf(m) === 'catering') return '/pages/catering/menu'
  return '/pages/home/index'
}

function setMerchantContext(m) {
  const app = getApp()
  const mode = systemOf(m) === 'catering' ? 'catering' : 'gym'
  app.globalData.merchantId = m.id
  app.globalData.systemMode = mode
  app.globalData.currentMerchant = m
  wx.setStorageSync('merchant_id', m.id)
  wx.setStorageSync('system_mode', mode)
}

function enterMerchant(m) {
  setMerchantContext(m)
  wx.reLaunch({ url: pathForMerchant(m) })
}

function goStores() {
  wx.reLaunch({ url: '/pages/stores/index' })
}

function currentMerchantFrom(me) {
  const app = getApp()
  const mid = app.globalData.merchantId
  const list = (me && me.merchants) || []
  if (!mid) return null
  return list.find((x) => x.id === mid) || null
}

const GYM_TABS = [
  { path: '/pages/home/index', label: '首页' },
  { path: '/pages/memberships/index', label: '会籍' },
  { path: '/pages/classes/index', label: '团课' },
  { path: '/pages/shop/index', label: '商城' },
  { path: '/pages/coupons/index', label: '卡券' },
  { path: '/pages/me/index', label: '我的' },
]

const CATERING_TABS = [
  { path: '/pages/catering/menu', label: '点餐' },
  { path: '/pages/catering/orders', label: '订单' },
  { path: '/pages/coupons/index', label: '卡券' },
  { path: '/pages/me/index', label: '我的' },
]

function tabsForMode(mode) {
  return mode === 'catering' ? CATERING_TABS : GYM_TABS
}

module.exports = {
  systemOf,
  pathForMerchant,
  setMerchantContext,
  enterMerchant,
  goStores,
  currentMerchantFrom,
  GYM_TABS,
  CATERING_TABS,
  tabsForMode,
}
