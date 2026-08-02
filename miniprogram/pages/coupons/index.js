Page({
  data: { title: '领券', items: [] },
  async onShow() {
    const { request } = require('../../utils/api')
    const app = getApp()
    const mid = app.globalData.merchantId
    const items = await request({ url: `/member/coupons/claimable?merchant_id=${mid}` })
    this.setData({ items })
  },
})
