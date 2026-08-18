/** 团课场次详情。 */
Page({
  data: {
    item: null,
    err: '',
    busy: false,
    timeText: '',
    endText: '',
    bookRule: '',
    cancelRule: '',
  },
  onLoad(query) {
    this.sessionId = Number(query.id)
    this.load()
  },
  ruleText(minutes, kind) {
    const n = Number(minutes || 0)
    if (n <= 0) return `开课前均可${kind}`
    if (n % 60 === 0) return `需提前 ${n / 60} 小时${kind}`
    return `需提前 ${n} 分钟${kind}`
  },
  fmt(iso) {
    if (!iso) return '—'
    return String(iso).slice(0, 16).replace('T', ' ')
  },
  async load() {
    const { request } = require('../../utils/api')
    try {
      const item = await request({ url: `/member/group-sessions/${this.sessionId}` })
      this.setData({
        err: '',
        item,
        timeText: this.fmt(item.starts_at),
        endText: this.fmt(item.ends_at).slice(11),
        bookRule: this.ruleText(item.book_ahead_minutes, '预约'),
        cancelRule: this.ruleText(item.cancel_ahead_minutes, '取消'),
      })
    } catch (e) {
      this.setData({ err: (e && e.message) || '加载失败', item: null })
    }
  },
  async book() {
    if (this.data.busy || !this.data.item) return
    const { request } = require('../../utils/api')
    const mid = getApp().globalData.merchantId
    this.setData({ busy: true })
    try {
      await request({
        url: '/member/group-bookings',
        method: 'POST',
        data: { merchant_id: mid, session_id: this.data.item.id },
      })
      wx.showToast({ title: '预约成功', icon: 'success' })
      await this.load()
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '预约失败', icon: 'none' })
    } finally {
      this.setData({ busy: false })
    }
  },
  goCoach() {
    const item = this.data.item
    if (!item || !item.coach_id) return
    wx.navigateTo({ url: `/pages/coaches/detail?id=${item.coach_id}` })
  },
})
