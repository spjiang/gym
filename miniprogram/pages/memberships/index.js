Page({
  data: { title: '我的会籍', items: [] },
  async onShow() {
    const { request } = require('../../utils/api')
    const app = getApp()
    const mid = app.globalData.merchantId
    const items = await request({ url: `/member/memberships?merchant_id=${mid}` })
    this.setData({ items })
  },
})
