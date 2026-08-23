/** 会员会话：缓存 /member/me 供顶栏与各页使用。 */
async function refreshMemberSession() {
  const { request } = require('./api')
  const { currentMerchantFrom } = require('./merchant')
  const app = getApp()
  const me = await request({ url: '/member/me' })
  app.globalData.memberMe = me
  const m = currentMerchantFrom(me)
  if (m) app.globalData.currentMerchant = m
  return me
}

function requireLogin() {
  const app = getApp()
  if (!app.globalData.token) {
    wx.reLaunch({ url: '/pages/login/index' })
    return false
  }
  return true
}

module.exports = { refreshMemberSession, requireLogin }
