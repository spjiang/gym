/** 会员退款/售后记录，新的在前。 */
const PAGE_SIZE = 20

Page({
  data: {
    rows: [],
    loading: true,
    loadingMore: false,
    finished: false,
    err: '',
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
    const offset = reset ? 0 : this.data.rows.length
    this.setData(reset ? { loading: true, err: '' } : { loadingMore: true })
    try {
      const list = (await request({ url: `/member/refunds?limit=${PAGE_SIZE}&offset=${offset}` })) || []
      const mapped = list.map((item) => this.mapRow(item))
      this.setData({
        loading: false,
        loadingMore: false,
        rows: reset ? mapped : this.data.rows.concat(mapped),
        finished: list.length < PAGE_SIZE,
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
  mapRow(item) {
    const { refundChannelLabel, refundStatusLabel } = require('../../utils/labels')
    const succeeded = item.status === 'succeeded'
    return {
      ...item,
      amountText: this.moneyText(item.amount),
      statusText: refundStatusLabel(item.status),
      statusTone: succeeded ? 'refund' : item.status === 'failed' ? 'refund' : 'warn',
      channelText: refundChannelLabel(item.channel),
      timeLabel: succeeded ? '到账时间' : '发起时间',
      timeText: this.fmtTime(succeeded ? item.succeeded_at : item.created_at),
      thumb: (item.title || '退').slice(0, 1),
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
  openOrder(e) {
    const orderId = Number(e.currentTarget.dataset.id)
    if (!orderId) return
    wx.navigateTo({ url: `/pages/orders/detail?id=${orderId}` })
  },
})
