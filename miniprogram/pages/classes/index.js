Page({
  data: { title: '团课场次', items: [] },
  async onShow() {
    const { request } = require('../../utils/api')
    const app = getApp()
    const mid = app.globalData.merchantId
    const items = await request({ url: `/member/group-sessions?merchant_id=${mid}` })
    this.setData({ items: (items || []).map((s) => ({ ...s, name: `场次 #${s.id}` })) })
  },
})
