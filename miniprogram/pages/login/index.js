Page({
  data: { phone: '', code: '' },
  onPhone(e) {
    this.setData({ phone: e.detail.value })
  },
  onCode(e) {
    this.setData({ code: e.detail.value })
  },
  async send() {
    const { request } = require('../../utils/api')
    try {
      await request({ url: '/member/auth/otp/send', method: 'POST', data: { phone: this.data.phone } })
      wx.showToast({ title: '已发送', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '发送失败', icon: 'none' })
    }
  },
  async login() {
    const { request } = require('../../utils/api')
    const app = getApp()
    try {
      const data = await request({
        url: '/member/auth/otp/verify',
        method: 'POST',
        data: { phone: this.data.phone, code: this.data.code },
      })
      app.globalData.token = data.access_token
      wx.setStorageSync('member_token', data.access_token)
      const me = await request({ url: '/member/me' })
      if (me.merchant_ids && me.merchant_ids.length) {
        app.globalData.merchantId = me.merchant_ids[0]
      }
      wx.reLaunch({ url: '/pages/home/index' })
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '登录失败', icon: 'none' })
    }
  },
})
