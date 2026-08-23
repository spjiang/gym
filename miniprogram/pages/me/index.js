/** 会员个人中心：人脸通行状态、可用门店、头像与推广入口。 */
Page({
  data: {
    name: '',
    phoneMasked: '',
    avatar: '会',
    avatarUrl: '',
    faceText: '未知',
    faceOk: false,
    sourceText: '综合运营平台',
    merchants: [],
    events: [],
    uploading: false,
  },
  async onShow() {
    const { requireLogin, refreshMemberSession } = require('../../utils/session')
    if (!requireLogin()) return
    await refreshMemberSession()
    await this.loadMe()
  },
  async loadMe() {
    const { request, fileUrl } = require('../../utils/api')
    try {
      const me = await request({ url: '/member/me' })
      const merchants = (me.merchants || []).map((m) => ({
        ...m,
        badge: this.systemLabel(m),
      }))
      let events = []
      try {
        const rows = await request({ url: '/member/access-events' })
        events = (rows || []).slice(0, 8).map((e) => ({
          ...e,
          timeText: this.fmtTime(e.created_at),
        }))
      } catch (err) {
        events = []
      }
      this.setData({
        name: me.name || '—',
        phoneMasked: this.maskPhone(me.phone),
        avatar: (me.name || '会').slice(0, 1),
        avatarUrl: fileUrl(me.avatar_url),
        faceText: me.face_status === 'enrolled' ? '已录入' : me.face_status === 'not_enrolled' ? '未录入' : me.face_status || '未知',
        faceOk: me.face_status === 'enrolled',
        sourceText: this.sourceText(me),
        merchants,
        events,
      })
    } catch (e) {
      wx.reLaunch({ url: '/pages/login/index' })
    }
  },
  maskPhone(phone) {
    if (!phone || phone.length < 7) return phone || ''
    return `${phone.slice(0, 3)}****${phone.slice(-4)}`
  },
  systemLabel(m) {
    const sys = m.primary_system || (m.subsystem_codes && m.subsystem_codes[0]) || ''
    if (sys === 'gym') return '健身'
    if (sys === 'catering') return '餐饮'
    return sys || '门店'
  },
  sourceText(me) {
    if (me.acquisition_source === 'merchant') {
      return me.first_merchant_name || (me.first_merchant_id ? `商户 #${me.first_merchant_id}` : '门店')
    }
    return '综合运营平台'
  },
  fmtTime(iso) {
    if (!iso) return '—'
    return String(iso).slice(0, 16).replace('T', ' ')
  },
  pickAvatar() {
    if (this.data.uploading) return
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
      success: (res) => {
        const file = res.tempFiles && res.tempFiles[0]
        if (!file || !file.tempFilePath) return
        this.uploadAvatar(file.tempFilePath)
      },
    })
  },
  async uploadAvatar(filePath) {
    const { upload } = require('../../utils/api')
    this.setData({ uploading: true })
    try {
      await upload({ url: '/member/avatar', filePath })
      wx.showToast({ title: '头像已更新', icon: 'success' })
      await this.loadMe()
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '上传失败', icon: 'none' })
    } finally {
      this.setData({ uploading: false })
    }
  },
  enterStore(e) {
    const id = Number(e.currentTarget.dataset.id)
    const me = getApp().globalData.memberMe
    const m = (me && me.merchants || []).find((x) => x.id === id)
    if (!m) return
    const { enterMerchant } = require('../../utils/merchant')
    enterMerchant(m)
  },
  goStores() {
    const { goStores } = require('../../utils/merchant')
    goStores()
  },
  goPromotion() {
    wx.navigateTo({ url: '/pages/promotion/index' })
  },
  goCatering() {
    wx.navigateTo({ url: '/pages/catering/menu' })
  },
  logout() {
    const app = getApp()
    app.globalData.token = ''
    app.globalData.merchantId = null
    app.globalData.memberMe = null
    app.globalData.currentMerchant = null
    app.globalData.systemMode = 'gym'
    wx.removeStorageSync('member_token')
    wx.removeStorageSync('merchant_id')
    wx.removeStorageSync('system_mode')
    wx.reLaunch({ url: '/pages/login/index' })
  },
})
