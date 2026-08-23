const {
  membershipStatusLabel,
  membershipTypeLabel,
  membershipStatusClass,
  fmtDate,
} = require('../../utils/labels')

Page({
  data: {
    loading: true,
    err: '',
    item: null,
    statusText: '',
    statusClass: '',
    typeText: '',
    startsText: '—',
    endsText: '—',
    remainText: '—',
    balanceText: '—',
  },
  onLoad(options) {
    this._id = Number(options.id)
  },
  async onShow() {
    const { requireLogin } = require('../../utils/session')
    if (!requireLogin()) return
    const { request } = require('../../utils/api')
    const mid = getApp().globalData.merchantId
    if (!this._id) {
      this.setData({ loading: false, err: '参数无效' })
      return
    }
    this.setData({ loading: true, err: '', item: null })
    try {
      const item = await request({ url: `/member/memberships/${this._id}` })
      if (item.merchant_id !== mid) {
        this.setData({ loading: false, err: '该会籍不属于当前门店' })
        return
      }
      this.setData({
        loading: false,
        item,
        statusText: membershipStatusLabel(item.status),
        statusClass: membershipStatusClass(item.status),
        typeText: membershipTypeLabel(item.product_type),
        startsText: fmtDate(item.starts_at),
        endsText: fmtDate(item.ends_at),
        remainText: item.remaining_sessions != null ? String(item.remaining_sessions) : '—',
        balanceText: item.balance != null ? `¥${item.balance}` : '—',
      })
    } catch (e) {
      this.setData({ loading: false, err: (e && e.message) || '加载失败' })
    }
  },
  back() {
    wx.navigateBack()
  },
})
