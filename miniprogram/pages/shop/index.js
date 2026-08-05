Page({
  data: { title: '商城', cards: [], pts: [] },
  async onShow() {
    const { request } = require('../../utils/api')
    const app = getApp()
    const mid = app.globalData.merchantId
    if (!mid) {
      wx.showToast({ title: '请先选店', icon: 'none' })
      return
    }
    try {
      const [cards, pts] = await Promise.all([
        request({ url: `/member/catalog/membership-products?merchant_id=${mid}` }),
        request({ url: `/member/catalog/pt-products?merchant_id=${mid}` }),
      ])
      this.setData({
        cards: cards || [],
        pts: pts || [],
      })
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '加载失败', icon: 'none' })
    }
  },
  async buyCard(e) {
    await this._buy('/member/orders/membership', e.currentTarget.dataset.id)
  },
  async buyPt(e) {
    await this._buy('/member/orders/pt-package', e.currentTarget.dataset.id)
  },
  async _buy(path, productId) {
    const { request } = require('../../utils/api')
    const { payOrder } = require('../../utils/pay')
    const app = getApp()
    wx.showLoading({ title: '支付中' })
    try {
      const order = await request({
        url: path,
        method: 'POST',
        data: { merchant_id: app.globalData.merchantId, product_id: productId },
      })
      await payOrder(order.id)
      wx.showToast({ title: '支付成功', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '支付失败', icon: 'none' })
    } finally {
      wx.hideLoading()
    }
  },
})
