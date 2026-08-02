Page({
  data: { title: '商城', items: [] },
  async onShow() {
    const { request } = require('../../utils/api')
    const app = getApp()
    const mid = app.globalData.merchantId
    const items = await request({ url: `/member/catalog/membership-products?merchant_id=${mid}` })
    this.setData({
      items: (items || []).map((p) => ({
        ...p,
        name: `${p.name} ¥${p.effective_price || p.price}${p.is_trial ? '（体验）' : ''}`,
      })),
    })
  },
})
