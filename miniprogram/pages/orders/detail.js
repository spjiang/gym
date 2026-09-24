/** 会员订单详情：展示平台订单号，待支付可继续付款。 */
Page({
  data: {
    order: null,
    statusText: '',
    amountText: '',
    dateText: '',
    err: '',
    paying: false,
  },
  onLoad(options) {
    this._id = Number(options && options.id)
  },
  onShow() {
    this.load()
  },
  async load() {
    const { request } = require('../../utils/api')
    const { orderStatusLabel, diningOrderLabel } = require('../../utils/labels')
    if (!this._id) {
      this.setData({ err: '订单不存在' })
      return
    }
    try {
      const order = await request({ url: `/member/orders/${this._id}` })
      this.setData({
        order,
        err: '',
        statusText: order.dining_status ? diningOrderLabel(order) : orderStatusLabel(order.status),
        amountText: this.moneyText(order.amount),
        dateText: this.fmtTime(order.created_at),
      })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败', order: null })
    }
  },
  fmtTime(iso) {
    if (!iso) return '—'
    return String(iso).slice(0, 16).replace('T', ' ')
  },
  moneyText(amount) {
    const value = Number(amount || 0)
    if (!Number.isFinite(value)) return '0.00'
    return value.toFixed(2)
  },
  copyNo() {
    const no = this.data.order && this.data.order.order_no
    if (!no) return
    wx.setClipboardData({ data: no })
  },
  async pay() {
    if (this.data.paying || !this._id) return
    const { payOrder } = require('../../utils/pay')
    this.setData({ paying: true })
    try {
      await payOrder(this._id)
      wx.showToast({ title: '支付成功', icon: 'success' })
      await this.load()
    } catch (err) {
      const message = (err && (err.errMsg || err.message)) || '支付失败'
      const cancelled = /cancel/i.test(message)
      wx.showToast({ title: cancelled ? '已取消支付' : message, icon: 'none' })
    } finally {
      this.setData({ paying: false })
    }
  },
})
