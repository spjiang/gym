const { membershipStatusLabel, membershipStatusClass, fmtDate } = require('../../utils/labels')

Page({
  data: {
    loading: true,
    err: '',
    item: null,
    statusText: '',
    statusClass: '',
    startsText: '—',
    endsText: '—',
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
      const item = await request({ url: `/member/pt-packages/${this._id}` })
      if (item.merchant_id !== mid) {
        this.setData({ loading: false, err: '该课包不属于当前门店' })
        return
      }
      this.setData({
        loading: false,
        item,
        statusText: membershipStatusLabel(item.status),
        statusClass: membershipStatusClass(item.status),
        startsText: fmtDate(item.starts_at),
        endsText: fmtDate(item.ends_at),
      })
    } catch (e) {
      this.setData({ loading: false, err: (e && e.message) || '加载失败' })
    }
  },
  back() {
    wx.navigateBack()
  },
})
