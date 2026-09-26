Page({
  data: {
    title: '商城',
    cards: [],
    pts: [],
    agreeShow: false,
    agreeLoading: false,
    agreeError: '',
    agreeSummary: '',
    agreeTitle: '',
    agreeContent: '',
  },
  async onShow() {
    const { requireLogin, refreshMemberSession } = require('../../utils/session')
    const { goStores } = require('../../utils/merchant')
    if (!requireLogin()) return
    if (!getApp().globalData.merchantId) {
      goStores()
      return
    }
    await refreshMemberSession()
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
        cards: (cards || []).map((item) => this.presentCard(item)),
        pts: (pts || []).map((item) => this.presentPt(item)),
      })
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '加载失败', icon: 'none' })
    }
  },
  money(raw) {
    if (raw == null || raw === '') return ''
    const n = Number(raw)
    if (Number.isNaN(n)) return String(raw)
    return Number.isInteger(n) ? String(n) : n.toFixed(2)
  },
  specOf(item, fallback) {
    if (item.session_count) return { num: String(item.session_count), unit: '次' }
    if (item.duration_days) return { num: String(item.duration_days), unit: '天' }
    return { num: fallback, unit: '' }
  },
  priceOf(item) {
    const current = item.effective_price != null && item.effective_price !== '' ? item.effective_price : item.price
    const priceText = this.money(current)
    const origin = this.money(item.price)
    return {
      priceText,
      originText: origin && origin !== priceText ? origin : '',
    }
  },
  presentCard(item) {
    const { membershipTypeLabel } = require('../../utils/labels')
    const spec = this.specOf(item, '会籍')
    return {
      ...item,
      ...spec,
      ...this.priceOf(item),
      typeText: membershipTypeLabel(item.product_type),
    }
  },
  presentPt(item) {
    const spec = this.specOf(item, '课包')
    return {
      ...item,
      ...spec,
      ...this.priceOf(item),
      typeText: item.valid_days ? `有效 ${item.valid_days} 天` : '私教课包',
    }
  },
  async buyCard(e) {
    const { id, name, price } = e.currentTarget.dataset
    this._agreeNext = () => this._buy('/member/orders/membership', id)
    const { openAgreement } = require('../../utils/agreement')
    const ok = await openAgreement(this, {
      merchantId: getApp().globalData.merchantId,
      scene: 'membership',
      summary: `${name || ''}  ¥${price || ''}`,
    })
    if (!ok) this._agreeNext = null
  },
  async buyPt(e) {
    const { id, name, price } = e.currentTarget.dataset
    this._agreeNext = () => this._buy('/member/orders/pt-package', id)
    const { openAgreement } = require('../../utils/agreement')
    const ok = await openAgreement(this, {
      merchantId: getApp().globalData.merchantId,
      scene: 'pt_package',
      summary: `${name || ''}  ¥${price || ''}`,
    })
    if (!ok) this._agreeNext = null
  },
  onAgreeClose() {
    this._agreeNext = null
    this.setData({ agreeShow: false })
  },
  async onAgreeConfirm() {
    const next = this._agreeNext
    this._agreeNext = null
    this.setData({ agreeShow: false })
    if (next) await next()
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
