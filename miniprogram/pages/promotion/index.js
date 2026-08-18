Page({
  data: {
    me: null,
    downlines: [],
    ledgers: [],
    payouts: [],
    tab: 'downline',
    amount: '',
    kindMap: {
      earn: '入账',
      reverse: '冲回',
      withdraw_freeze: '冻结',
      withdraw_paid: '打款',
      withdraw_revert: '退回',
      adjust: '调整',
    },
    statusMap: {
      requested: '待审核',
      approved: '待打款',
      paid: '已打款',
      rejected: '已驳回',
    },
  },
  onShow() {
    this.load()
  },
  pct(v) {
    const n = Number(v || 0)
    return `${(n * 100).toFixed(1).replace(/\.0$/, '')}%`
  },
  async load() {
    const { request } = require('../../utils/api')
    try {
      const [me, down, ledgers, payouts] = await Promise.all([
        request({ url: '/member/promotion' }),
        request({ url: '/member/promotion/downline?page=1&page_size=20' }),
        request({ url: '/member/promotion/ledgers?page=1&page_size=20' }),
        request({ url: '/member/promotion/withdrawals?page=1&page_size=20' }),
      ])
      this.setData({
        me,
        rebateText: this.pct(me.rebate_rate),
        discountText: this.pct(me.downline_discount_rate),
        myDiscountText: this.pct(me.my_discount_rate),
        downlines: down.items || [],
        ledgers: ledgers.items || [],
        payouts: payouts.items || [],
      })
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '加载失败', icon: 'none' })
    }
  },
  switchTab(e) {
    this.setData({ tab: e.currentTarget.dataset.tab })
  },
  onAmount(e) {
    this.setData({ amount: e.detail.value })
  },
  copyLink() {
    const link = this.data.me && this.data.me.link
    if (!link) {
      wx.showToast({ title: '暂无推广链接', icon: 'none' })
      return
    }
    wx.setClipboardData({ data: link })
  },
  async withdraw() {
    const { request } = require('../../utils/api')
    const amount = this.data.amount
    if (!amount || Number(amount) <= 0) {
      wx.showToast({ title: '请填写提现金额', icon: 'none' })
      return
    }
    try {
      await request({ url: '/member/promotion/withdrawals', method: 'POST', data: { amount } })
      wx.showToast({ title: '已提交申请', icon: 'success' })
      this.setData({ amount: '' })
      this.load()
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '申请失败', icon: 'none' })
    }
  },
})
