const { goStores } = require('../../utils/merchant')

Component({
  properties: {
    show: { type: Boolean, value: true },
  },
  data: {
    merchantName: '门店',
    systemLabel: '观野FIT',
    userName: '',
    initial: '会',
    avatarUrl: '',
  },
  lifetimes: {
    attached() {
      this.refresh()
    },
  },
  pageLifetimes: {
    show() {
      this.refresh()
    },
  },
  methods: {
    refresh() {
      const app = getApp()
      const m = app.globalData.currentMerchant
      const me = app.globalData.memberMe
      const mode = app.globalData.systemMode || 'gym'
      this.setData({
        merchantName: (m && m.name) || '门店',
        systemLabel: mode === 'catering' ? '观野BAR' : '观野FIT',
        userName: (me && me.name) || '',
        initial: ((me && me.name) || '会').slice(0, 1),
        avatarUrl: me && me.avatar_url ? require('../../utils/api').fileUrl(me.avatar_url) : '',
      })
    },
    switchStore() {
      goStores()
    },
    goMe() {
      wx.reLaunch({ url: '/pages/me/index' })
    },
  },
})
