/** 团课：我的预约在上，仅展示仍可预约的场次。 */
Page({
  data: {
    bookings: [],
    sessions: [],
    err: '',
  },
  async onShow() {
    await this.load()
  },
  async load() {
    const { request } = require('../../utils/api')
    const app = getApp()
    const mid = app.globalData.merchantId
    if (!mid) {
      this.setData({ err: '请先选择门店', bookings: [], sessions: [] })
      return
    }
    try {
      const [sessions, bookings] = await Promise.all([
        request({ url: `/member/group-sessions?merchant_id=${mid}` }),
        request({ url: `/member/group-bookings?merchant_id=${mid}` }),
      ])
      this.setData({
        err: '',
        sessions: (sessions || []).map((s) => ({
          ...s,
          timeText: this.fmt(s.starts_at),
        })),
        bookings: (bookings || []).map((b) => ({
          ...b,
          timeText: this.fmt(b.starts_at),
          statusText: this.statusText(b.status),
        })),
      })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败' })
    }
  },
  fmt(iso) {
    if (!iso) return '—'
    return String(iso).slice(0, 16).replace('T', ' ')
  },
  statusText(status) {
    return { booked: '已预约', cancelled: '已取消', attended: '已出勤', no_show: '未到' }[status] || status
  },
  goDetail(e) {
    const id = e.currentTarget.dataset.id
    wx.navigateTo({ url: `/pages/classes/detail?id=${id}` })
  },
  async book(e) {
    const { request } = require('../../utils/api')
    const id = Number(e.currentTarget.dataset.id)
    const mid = getApp().globalData.merchantId
    try {
      await request({
        url: '/member/group-bookings',
        method: 'POST',
        data: { merchant_id: mid, session_id: id },
      })
      wx.showToast({ title: '预约成功', icon: 'success' })
      await this.load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '预约失败', icon: 'none' })
    }
  },
  async cancel(e) {
    const { request } = require('../../utils/api')
    const id = Number(e.currentTarget.dataset.id)
    try {
      await request({ url: `/member/group-bookings/${id}`, method: 'DELETE' })
      wx.showToast({ title: '已取消', icon: 'success' })
      await this.load()
    } catch (err) {
      wx.showToast({ title: (err && err.message) || '取消失败', icon: 'none' })
    }
  },
})
