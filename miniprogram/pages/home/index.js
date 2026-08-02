Page({
  data: { name: '', phone: '' },
  async onShow() {
    const { request } = require('../../utils/api')
    try {
      const me = await request({ url: '/member/me' })
      this.setData({ name: me.name, phone: me.phone })
    } catch (e) {
      wx.reLaunch({ url: '/pages/login/index' })
    }
  },
  go(e) {
    wx.navigateTo({ url: e.currentTarget.dataset.url })
  },
})
