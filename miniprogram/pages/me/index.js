/** 会员个人中心：订单、来源标识、头像与推广入口。人脸通行暂时关闭。 */
const SHOW_FACE_ACCESS = false

Page({
  data: {
    name: '',
    phoneMasked: '',
    avatar: '会',
    avatarUrl: '',
    showFaceAccess: SHOW_FACE_ACCESS,
    faceText: '未知',
    faceOk: false,
    sourceText: '综合运营平台',
    orders: [],
    events: [],
    uploading: false,
    payingId: 0,
    icpBeian: '',
  },
  async onShow() {
    const { requireLogin, refreshMemberSession } = require('../../utils/session')
    if (!requireLogin()) return
    await refreshMemberSession()
    this.setData({ icpBeian: getApp().globalData.icpBeian || '' })
    await this.loadMe()
  },
  async loadMe() {
    const { request, fileUrl } = require('../../utils/api')
    try {
      const me = await request({ url: '/member/me' })
      const { orderStatusLabel, diningOrderLabel } = require('../../utils/labels')
      let orders = []
      try {
        const rows = (await request({ url: '/member/orders' })) || []
        orders = rows.map((item) => ({
          ...item,
          amountText: this.moneyText(item.amount),
          dateText: this.fmtDate(item.created_at),
          thumb: (item.title || '单').slice(0, 1),
          statusText: item.dining_status ? diningOrderLabel(item) : orderStatusLabel(item.status),
        }))
      } catch (err) {
        orders = []
      }
      let events = []
      if (SHOW_FACE_ACCESS) {
        try {
          const rows = await request({ url: '/member/access-events' })
          events = (rows || []).slice(0, 8).map((e) => ({
            ...e,
            timeText: this.fmtTime(e.created_at),
          }))
        } catch (err) {
          events = []
        }
      }
      this.setData({
        name: me.name || '—',
        phoneMasked: this.maskPhone(me.phone),
        avatar: (me.name || '会').slice(0, 1),
        avatarUrl: fileUrl(me.avatar_url),
        showFaceAccess: SHOW_FACE_ACCESS,
        faceText: me.face_status === 'enrolled' ? '已录入' : me.face_status === 'not_enrolled' ? '未录入' : me.face_status || '未知',
        faceOk: me.face_status === 'enrolled',
        sourceText: this.sourceText(me),
        orders,
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
  fmtDate(iso) {
    if (!iso) return '—'
    return String(iso).slice(0, 10)
  },
  moneyText(amount) {
    const value = Number(amount || 0)
    if (!Number.isFinite(value)) return '0'
    return Number.isInteger(value) ? String(value) : value.toFixed(2)
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
  async payOrder(e) {
    if (this.data.payingId) return
    const orderId = Number(e.currentTarget.dataset.id)
    if (!orderId) return
    const { payOrder } = require('../../utils/pay')
    this.setData({ payingId: orderId })
    try {
      await payOrder(orderId)
      wx.showToast({ title: '支付成功', icon: 'success' })
      await this.loadMe()
    } catch (err) {
      const message = (err && (err.errMsg || err.message)) || '支付失败'
      const cancelled = /cancel/i.test(message)
      wx.showToast({ title: cancelled ? '已取消支付' : message, icon: 'none' })
    } finally {
      this.setData({ payingId: 0 })
    }
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
