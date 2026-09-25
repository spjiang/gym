Page({
  data: {
    phone: '',
    code: '',
    password: '',
    password2: '',
    mode: 'otp',
    scene: 'login',
    referralCode: '',
    merchantId: null,
    table: '',
    redirect: '',
    icpBeian: '',
  },
  onLoad(options) {
    const app = getApp()
    const fromPage = app.resolveReferralCode((options && options.query) || options)
    if (fromPage) {
      app.globalData.referralCode = fromPage
      wx.setStorageSync('referral_code', fromPage)
    }
    const merchantId = options && options.merchant_id ? Number(options.merchant_id) : null
    const table = (options && options.table) || ''
    let redirect = ''
    if (options && options.redirect) {
      try {
        redirect = decodeURIComponent(options.redirect)
      } catch (e) {
        redirect = options.redirect
      }
    }
    if (merchantId) {
      app.globalData.merchantId = merchantId
      wx.setStorageSync('merchant_id', merchantId)
    }
    this.setData({
      referralCode: app.globalData.referralCode || '',
      merchantId: merchantId || app.globalData.merchantId || null,
      table,
      redirect,
      icpBeian: app.globalData.icpBeian || '',
    })
  },
  onShow() {
    const app = getApp()
    if (app.globalData.token) {
      wx.reLaunch({ url: '/pages/stores/index' })
    }
  },
  setMode(e) {
    this.setData({ mode: e.currentTarget.dataset.mode })
  },
  onPhone(e) {
    this.setData({ phone: e.detail.value })
  },
  onCode(e) {
    this.setData({ code: e.detail.value })
  },
  onPassword(e) {
    this.setData({ password: e.detail.value })
  },
  onPassword2(e) {
    this.setData({ password2: e.detail.value })
  },
  openScene(e) {
    this.setData({ scene: e.currentTarget.dataset.scene, code: '', password: '', password2: '' })
  },
  async send() {
    const { request } = require('../../utils/api')
    try {
      await request({
        url: '/member/auth/otp/send',
        method: 'POST',
        data: { phone: this.data.phone, merchant_id: this.data.merchantId || null },
      })
      wx.showToast({ title: '已发送', icon: 'success' })
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '发送失败', icon: 'none' })
    }
  },
  async submit() {
    if (this.data.scene !== 'login') {
      if ((this.data.password || '').length < 6) {
        wx.showToast({ title: '密码至少 6 位', icon: 'none' })
        return
      }
      if (this.data.password !== this.data.password2) {
        wx.showToast({ title: '两次密码不一致', icon: 'none' })
        return
      }
    }
    const { request } = require('../../utils/api')
    const cart = require('../../utils/cateringCart')
    const app = getApp()
    try {
      let data
      if (this.data.scene === 'register') {
        data = await request({
          url: '/member/auth/register',
          method: 'POST',
          data: {
            phone: this.data.phone,
            code: this.data.code,
            password: this.data.password,
            merchant_id: this.data.merchantId || null,
            referral_code: this.data.referralCode || null,
          },
        })
      } else if (this.data.scene === 'reset') {
        data = await request({
          url: '/member/auth/password/reset',
          method: 'POST',
          data: {
            phone: this.data.phone,
            code: this.data.code,
            password: this.data.password,
            merchant_id: this.data.merchantId || null,
          },
        })
      } else if (this.data.mode === 'password') {
        data = await request({
          url: '/member/auth/password',
          method: 'POST',
          data: { phone: this.data.phone, password: this.data.password, merchant_id: this.data.merchantId || null },
        })
      } else {
        data = await request({
          url: '/member/auth/otp/verify',
          method: 'POST',
          data: {
            phone: this.data.phone,
            code: this.data.code,
            merchant_id: this.data.merchantId || null,
            referral_code: this.data.referralCode || null,
          },
        })
      }
      app.globalData.token = data.access_token
      wx.setStorageSync('member_token', data.access_token)
      try {
        const { ensureMpOpenid } = require('../../utils/pay')
        await ensureMpOpenid()
      } catch (bindErr) {
        console.warn('openid bind skipped', bindErr)
      }
      const { enterMerchant } = require('../../utils/merchant')
      const me = await request({ url: '/member/me' })
      app.globalData.memberMe = me
      if (this.data.table && app.globalData.merchantId) {
        try {
          const table = await request({
            url: `/member/catering/table?merchant_id=${app.globalData.merchantId}&code=${encodeURIComponent(this.data.table)}`,
          })
          cart.lockTable(app.globalData.merchantId, table.name)
        } catch (e) {
          /* 桌码无效时仍回跳点餐 */
        }
      }
      const redirect = this.data.redirect
      if (redirect && redirect.startsWith('/pages/')) {
        wx.reLaunch({ url: redirect })
        return
      }
      const keptMerchantId = this.data.merchantId || app.globalData.merchantId
      if (keptMerchantId) {
        const m = (me.merchants || []).find((x) => x.id === Number(keptMerchantId))
        if (m) {
          enterMerchant(m)
          return
        }
      }
      wx.reLaunch({ url: '/pages/stores/index' })
    } catch (e) {
      wx.showToast({ title: (e && e.message) || '登录失败', icon: 'none' })
    }
  },
})
