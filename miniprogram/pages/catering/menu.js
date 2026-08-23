/** 会员点餐菜单。扫码可带 table 点餐码。 */
Page({
  data: {
    items: [],
    groups: [],
    cartCount: 0,
    subtotal: '0.00',
    tableNo: '',
    tableLocked: false,
    err: '',
    loading: true,
  },
  onLoad(options) {
    this._tableCode = (options && options.table) || ''
    if (options && options.merchant_id) {
      const mid = Number(options.merchant_id)
      const app = getApp()
      app.globalData.merchantId = mid
      app.globalData.systemMode = 'catering'
      wx.setStorageSync('merchant_id', mid)
      wx.setStorageSync('system_mode', 'catering')
    }
  },
  async onShow() {
    const { requireLogin, refreshMemberSession } = require('../../utils/session')
    const { goStores } = require('../../utils/merchant')
    if (!requireLogin()) return
    const app = getApp()
    if (!app.globalData.merchantId) {
      goStores()
      return
    }
    app.globalData.systemMode = 'catering'
    wx.setStorageSync('system_mode', 'catering')
    await refreshMemberSession()
    const { request, fileUrl } = require('../../utils/api')
    const cart = require('../../utils/cateringCart')
    const mid = app.globalData.merchantId
    if (!mid) {
      this.setData({ loading: false, err: '请先选择门店' })
      return
    }
    if (!app.globalData.token) {
      this.goLogin()
      return
    }
    this.setData({ loading: true, err: '' })
    try {
      if (this._tableCode) {
        try {
          const table = await request({
            url: `/member/catering/table?merchant_id=${mid}&code=${encodeURIComponent(this._tableCode)}`,
          })
          cart.lockTable(mid, table.name)
        } catch (e) {
          /* 无效桌码仍可点餐 */
        }
      }
      const items = (await request({ url: `/member/catering/menu?merchant_id=${mid}` })) || []
      const withImg = items.map((i) => ({ ...i, imageUrl: fileUrl(i.image_url) }))
      this._items = withImg
      this.refreshCart()
    } catch (e) {
      if ((e && (e.status_code || e.statusCode)) === 401) {
        this.goLogin()
        return
      }
      this.setData({ loading: false, err: (e && e.message) || '菜单加载失败' })
    }
  },
  goLogin() {
    const mid = getApp().globalData.merchantId || ''
    const table = this._tableCode || ''
    const redirect = encodeURIComponent(
      `/pages/catering/menu?merchant_id=${mid}${table ? `&table=${encodeURIComponent(table)}` : ''}`,
    )
    wx.redirectTo({
      url: `/pages/login/index?merchant_id=${mid}&table=${encodeURIComponent(table)}&redirect=${redirect}`,
    })
  },
  refreshCart() {
    const cart = require('../../utils/cateringCart')
    const app = getApp()
    const mid = app.globalData.merchantId
    const items = this._items || []
    const qty = cart.qtyMap(mid)
    const groupsMap = {}
    const groups = []
    for (const item of items) {
      const cat = item.category || '其他'
      if (!groupsMap[cat]) {
        groupsMap[cat] = []
        groups.push({ category: cat, items: groupsMap[cat] })
      }
      groupsMap[cat].push({ ...item, quantity: qty[item.id] || 0 })
    }
    const lines = cart.linesOf(mid, items)
    const subtotal = lines.reduce((sum, i) => sum + Number(i.price) * i.quantity, 0)
    this.setData({
      loading: false,
      items,
      groups,
      cartCount: cart.count(mid),
      subtotal: subtotal.toFixed(2),
      tableNo: cart.tableNoOf(mid),
      tableLocked: cart.tableLockedOf(mid),
    })
  },
  add(e) {
    const cart = require('../../utils/cateringCart')
    cart.add(getApp().globalData.merchantId, e.currentTarget.dataset.id)
    this.refreshCart()
  },
  sub(e) {
    const cart = require('../../utils/cateringCart')
    cart.sub(getApp().globalData.merchantId, e.currentTarget.dataset.id)
    this.refreshCart()
  },
  goCheckout() {
    if (!this.data.cartCount) {
      wx.showToast({ title: '请先选菜', icon: 'none' })
      return
    }
    const q = this._tableCode ? `?table=${encodeURIComponent(this._tableCode)}` : ''
    wx.navigateTo({ url: `/pages/catering/checkout${q}` })
  },
  goOrders() {
    wx.navigateTo({ url: '/pages/catering/orders' })
  },
})
