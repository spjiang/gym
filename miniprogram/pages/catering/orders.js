Page({
  data: { orders: [], err: '' },
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
    const { request } = require('../../utils/api')
    const { diningOrderLabel } = require('../../utils/labels')
    const mid = app.globalData.merchantId
    if (!mid) {
      this.setData({ err: '请先选择门店' })
      return
    }
    try {
      const rows = (await request({ url: `/member/catering/orders?merchant_id=${mid}` })) || []
      const orders = rows.map((item) => ({ ...item, statusText: diningOrderLabel(item) }))
      this.setData({ orders, err: '' })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败' })
    }
  },
  goDetail(e) {
    wx.navigateTo({ url: `/pages/catering/detail?id=${e.currentTarget.dataset.id}` })
  },
})
