/** 会员全部订单，按页加载，新的在前。 */
const PAGE_SIZE = 20

Page({
  data: {
    orders: [],
    loading: true,
    loadingMore: false,
    finished: false,
    err: '',
    payingId: 0,
    status: '',
  },
  onLoad(options) {
    const status = (options && options.status) || ''
    this.setData({ status })
    const titles = { pending: '待付款', paid: '已支付' }
    if (titles[status]) wx.setNavigationBarTitle({ title: titles[status] })
  },
  onShow() {
    const { requireLogin } = require('../../utils/session')
    if (!requireLogin()) return
    this.load(true)
  },
  onReachBottom() {
    this.load(false)
  },
  async load(reset) {
    if (!reset && (this.data.finished || this.data.loadingMore || this.data.loading)) return
    const { request } = require('../../utils/api')
    const offset = reset ? 0 : this.data.orders.length
    this.setData(reset ? { loading: true, err: '' } : { loadingMore: true })
    try {
      const statusQuery = this.data.status ? `&status=${this.data.status}` : ''
      const rows = (await request({ url: `/member/orders?limit=${PAGE_SIZE}&offset=${offset}${statusQuery}` })) || []
      const mapped = rows.map((item) => this.mapOrder(item))
      this.setData({
        loading: false,
        loadingMore: false,
        orders: reset ? mapped : this.data.orders.concat(mapped),
        finished: rows.length < PAGE_SIZE,
        err: '',
      })
    } catch (e) {
      this.setData({
        loading: false,
        loadingMore: false,
        err: (e && e.message) || '加载失败',
      })
    }
  },
  mapOrder(item) {
    const { memberOrderView } = require('../../utils/labels')
    const view = memberOrderView(item)
    const refunded = Number(item.refunded_amount || 0)
    return {
      ...item,
      amountText: this.moneyText(item.amount),
      dateText: this.fmtDate(item.created_at),
      thumb: (item.title || '单').slice(0, 1),
      statusText: view.statusText,
      statusTone: view.statusTone,
      refundText: refunded > 0 ? `已退 ¥${this.moneyText(refunded)}` : '',
    }
  },
  fmtDate(iso) {
    if (!iso) return '—'
    return String(iso).slice(0, 10)
  },
  moneyText(amount) {
    const value = Number(amount || 0)
    if (!Number.isFinite(value)) return '0'
    return Number.isInteger(value) ? String(value) : value.toFixed(2)
  },
  openOrder(e) {
    const orderId = Number(e.currentTarget.dataset.id)
    if (!orderId) return
    wx.navigateTo({ url: `/pages/orders/detail?id=${orderId}` })
  },
  async payOrder(e) {
    if (this.data.payingId) return
    const orderId = Number(e.currentTarget.dataset.id)
    if (!orderId) return
    const { payOrder } = require('../../utils/pay')
    this.setData({ payingId: orderId })
    try {
      await payOrder(orderId)
      wx.showToast({ title: '支付成功', icon: 'success' })
      await this.load(true)
    } catch (err) {
      const message = (err && (err.errMsg || err.message)) || '支付失败'
      const cancelled = /cancel/i.test(message)
      wx.showToast({ title: cancelled ? '已取消支付' : message, icon: 'none' })
    } finally {
      this.setData({ payingId: 0 })
    }
  },
})
