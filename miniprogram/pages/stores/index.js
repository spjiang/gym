Page({
  data: { merchants: [], currentId: null },
  async onShow() {
    const { request } = require('../../utils/api')
    const app = getApp()
    try {
      const me = await request({ url: '/member/me' })
      const merchants = me.merchants || []
      this.setData({
        merchants,
        currentId: app.globalData.merchantId,
      })
      if (!app.globalData.merchantId && merchants.length) {
        app.globalData.merchantId = merchants[0].id
        this.setData({ currentId: merchants[0].id })
      }
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '加载失败', icon: 'none' })
    }
  },
  select(e) {
    const id = Number(e.currentTarget.dataset.id)
    getApp().globalData.merchantId = id
    wx.setStorageSync('merchant_id', id)
    this.setData({ currentId: id })
    wx.showToast({ title: '已切换门店', icon: 'success' })
  },
})
