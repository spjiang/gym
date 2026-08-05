/** 小程序支付：绑定 openid → 预下单 → 调起 / dry-run 确认 */

const { request } = require('./api')

function ensureMpOpenid() {
  return new Promise((resolve, reject) => {
    wx.login({
      success: async (res) => {
        if (!res.code) {
          reject(new Error('wx.login 无 code'))
          return
        }
        try {
          await request({
            url: '/member/auth/wechat/mini/bind',
            method: 'POST',
            data: { code: res.code },
          })
          resolve(true)
        } catch (e) {
          reject(e)
        }
      },
      fail: reject,
    })
  })
}

function requestPayment(jsapiParams) {
  return new Promise((resolve, reject) => {
    wx.requestPayment({
      timeStamp: String(jsapiParams.timeStamp),
      nonceStr: jsapiParams.nonceStr,
      package: jsapiParams.package,
      signType: jsapiParams.signType || 'RSA',
      paySign: jsapiParams.paySign,
      success: resolve,
      fail: (err) => reject(err || new Error('支付取消或失败')),
    })
  })
}

/**
 * 支付会员订单。mock 立即成功；微信 dry_run 自动确认；真实模式调起收银台。
 */
async function payOrder(orderId) {
  await ensureMpOpenid()
  const data = await request({
    url: `/member/orders/${orderId}/pay/online`,
    method: 'POST',
    data: { pay_scene: 'miniprogram' },
  })
  if (data.immediate_capture || data.status === 'paid') {
    return data
  }
  if (data.dry_run) {
    return request({
      url: `/member/orders/${orderId}/pay/dry-run-confirm`,
      method: 'POST',
      data: { out_trade_no: data.out_trade_no },
    })
  }
  if (data.jsapi_params) {
    await requestPayment(data.jsapi_params)
    return data
  }
  throw new Error('无法调起支付')
}

module.exports = { payOrder, ensureMpOpenid }
