Page({
  data: { orders: [], err: '' },
  async onShow() {
    const { request } = require('../../utils/api')
    const app = getApp()
    const mid = app.globalData.merchantId
    if (!mid) {
      this.setData({ err: '请先选择门店' })
      return
    }
    try {
      const orders = (await request({ url: `/member/catering/orders?merchant_id=${mid}` })) || []
      this.setData({ orders, err: '' })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败' })
    }
  },
  goDetail(e) {
    wx.navigateTo({ url: `/pages/catering/detail?id=${e.currentTarget.dataset.id}` })
  },
})
