/** 会员端统一支付：按场景预下单并调起微信 / dry-run 确认。 */

import http from './http'

export type PayScene = 'miniprogram' | 'jsapi_h5' | 'mweb'

export type PrepayResult = {
  id: number
  order_id: number
  status: string
  amount?: string
  pay_scene: string
  dry_run: boolean
  immediate_capture: boolean
  jsapi_params?: Record<string, string> | null
  mweb_url?: string | null
  out_trade_no?: string
  pickup_code?: string | null
}

declare global {
  interface Window {
    WeixinJSBridge?: {
      invoke: (
        api: string,
        params: Record<string, string>,
        cb: (res: { err_msg?: string }) => void,
      ) => void
    }
  }
}

/** 是否在微信内置浏览器 */
export function isWechatBrowser(): boolean {
  return /MicroMessenger/i.test(navigator.userAgent || '')
}

export function detectPayScene(): PayScene {
  return isWechatBrowser() ? 'jsapi_h5' : 'mweb'
}

function invokeJsapi(params: Record<string, string>): Promise<void> {
  return new Promise((resolve, reject) => {
    const run = () => {
      if (!window.WeixinJSBridge) {
        reject(new Error('WeixinJSBridge 不可用'))
        return
      }
      window.WeixinJSBridge.invoke('getBrandWCPayRequest', params, (res) => {
        const msg = res.err_msg || ''
        if (msg.includes('ok')) resolve()
        else if (msg.includes('cancel')) reject(new Error('已取消支付'))
        else reject(new Error(msg || '支付失败'))
      })
    }
    if (window.WeixinJSBridge) run()
    else document.addEventListener('WeixinJSBridgeReady', run, { once: true })
  })
}

/**
 * 对已创建订单发起线上支付。
 * - mock：立即 paid
 * - wechat + dry_run：预下单后自动 dry-run-confirm（开发联调）
 * - wechat 真实：调起 JSAPI 或跳转 MWEB
 */
export async function payMemberOrder(orderId: number): Promise<PrepayResult> {
  const pay_scene = detectPayScene()

  // 微信内 JSAPI：开发环境用 mock code 绑定 openid（生产应走 OAuth 回调拿 code）
  if (pay_scene === 'jsapi_h5') {
    try {
      const code =
        new URLSearchParams(window.location.search).get('code') ||
        `h5_mock_${Date.now()}`
      await http.post('/member/auth/wechat/oa/bind', { code })
    } catch {
      // 已绑定或通道未配时忽略，后续预下单会明确报错
    }
  }

  const { data } = await http.post<PrepayResult>(`/member/orders/${orderId}/pay/online`, {
    pay_scene,
    client_ip: undefined,
    return_url: window.location.origin + window.location.pathname,
  })

  if (data.immediate_capture || data.status === 'paid') {
    return data
  }

  if (data.dry_run) {
    const { data: confirmed } = await http.post<PrepayResult>(
      `/member/orders/${orderId}/pay/dry-run-confirm`,
      { out_trade_no: data.out_trade_no },
    )
    return { ...data, ...confirmed, status: confirmed.status || 'paid' }
  }

  if (pay_scene === 'jsapi_h5' && data.jsapi_params) {
    await invokeJsapi(data.jsapi_params as Record<string, string>)
    // 真实支付：轮询查单确认
    for (let i = 0; i < 20; i++) {
      await new Promise((r) => setTimeout(r, 2000))
      const { data: q } = await http.post<{ status: string }>(`/member/orders/${orderId}/pay/query`)
      if (q.status === 'paid') return { ...data, ...q, status: 'paid' }
    }
    throw new Error('支付结果确认中，请稍后在订单查看')
  }

  if (pay_scene === 'mweb' && data.mweb_url) {
    window.location.href = data.mweb_url
    return data
  }

  throw new Error('无法调起支付，请检查支付配置')
}
