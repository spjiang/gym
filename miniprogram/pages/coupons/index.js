Page({
  data: { title: '优惠卡券', claimable: [], mine: [], msg: '', err: '' },
  async onShow() {
    const { requireLogin, refreshMemberSession } = require('../../utils/session')
    const { goStores } = require('../../utils/merchant')
    if (!requireLogin()) return
    if (!getApp().globalData.merchantId) {
      goStores()
      return
    }
    await refreshMemberSession()
    await this.load()
  },
  async load() {
    const { request } = require('../../utils/api')
    const app = getApp()
    const mid = app.globalData.merchantId
    if (!mid) {
      this.setData({ err: '请先选择门店', claimable: [], mine: [] })
      return
    }
    try {
      const [claimable, mine] = await Promise.all([
        request({ url: `/member/coupons/claimable?merchant_id=${mid}` }),
        request({ url: `/member/coupons?merchant_id=${mid}` }),
      ])
      this.setData({
        claimable: claimable || [],
        mine: mine || [],
        err: '',
      })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败' })
    }
  },
  async claim(e) {
    const { request } = require('../../utils/api')
    const app = getApp()
    const id = e.currentTarget.dataset.id
    try {
      await request({
        url: '/member/coupons/claim',
        method: 'POST',
        data: { merchant_id: app.globalData.merchantId, template_id: id },
      })
      wx.showToast({ title: '领取成功', icon: 'success' })
      await this.load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '领取失败', icon: 'none' })
    }
  },
})
