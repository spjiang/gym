<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'
import { pathForMerchant, useAuthStore } from '../stores/auth'
import BrandMark from '../components/BrandMark.vue'
import LegalSheet from '../components/LegalSheet.vue'
import { copyrightLine } from '../copyright'
import type { LegalDoc } from '../legal'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const phone = ref('')
const code = ref('')
const password = ref('')
const mode = ref<'otp' | 'password'>('otp')
const tip = ref('')
const err = ref('')
const sending = ref(false)
const logging = ref(false)
const wechatBusy = ref(false)
const promoterName = ref('')
const oaAppId = ref('')
const legalDoc = ref<LegalDoc | null>(null)
const wechatTicket = ref(sessionStorage.getItem('gym_wechat_oa_ticket') || '')
const insideWechat = /MicroMessenger/i.test(navigator.userAgent)

function inWechat() {
  return insideWechat
}

const merchantId = computed(() => {
  const raw = route.query.merchant_id
  const n = Number(Array.isArray(raw) ? raw[0] : raw)
  return n && !Number.isNaN(n) ? n : undefined
})

const referralCode = computed(() => {
  const raw = route.query.promoter ?? route.query.referral_code
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value.trim() ? value.trim().toUpperCase() : undefined
})

function rememberTicket(ticket: string) {
  wechatTicket.value = ticket
  sessionStorage.setItem('gym_wechat_oa_ticket', ticket)
}

function clearTicket() {
  wechatTicket.value = ''
  sessionStorage.removeItem('gym_wechat_oa_ticket')
}

function goAfterLogin(me: Awaited<ReturnType<typeof auth.fetchMe>>) {
  const redirect = (route.query.redirect as string) || ''
  if (redirect.startsWith('/m/') || redirect === '/stores' || redirect === '/me') {
    router.replace(redirect)
    return
  }
  if (merchantId.value) {
    const m = me.merchants.find((x) => x.id === merchantId.value)
    if (m) {
      auth.setMerchantId(m.id)
      router.replace(pathForMerchant(m))
      return
    }
  }
  router.replace('/stores')
}

async function finishWithToken(token: string) {
  clearTicket()
  auth.setToken(token)
  const me = await auth.fetchMe()
  goAfterLogin(me)
}

function stripWechatQuery() {
  const next: Record<string, string> = {}
  for (const [key, value] of Object.entries(route.query)) {
    if (key === 'code' || key === 'state' || key === 'wechat') continue
    const raw = Array.isArray(value) ? value[0] : value
    if (typeof raw === 'string' && raw) next[key] = raw
  }
  void router.replace({ path: '/login', query: next })
}

function loginPageUrl(extra: Record<string, string> = {}) {
  const url = new URL(`${window.location.origin}/login`)
  if (merchantId.value) url.searchParams.set('merchant_id', String(merchantId.value))
  if (referralCode.value) url.searchParams.set('promoter', referralCode.value)
  const redirect = (route.query.redirect as string) || ''
  if (redirect) url.searchParams.set('redirect', redirect)
  for (const [key, value] of Object.entries(extra)) url.searchParams.set(key, value)
  return url
}

async function loginByWechatCode(wxCode: string) {
  wechatBusy.value = true
  err.value = ''
  try {
    const { data } = await http.post('/member/auth/wechat/oa', {
      code: wxCode,
      merchant_id: merchantId.value ?? null,
    })
    if (data.access_token) {
      await finishWithToken(data.access_token)
      return
    }
    if (data.need_bind && data.ticket) {
      rememberTicket(data.ticket)
      tip.value = data.message || '请用手机号验证一次，验证后自动绑定微信'
    }
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '微信登录失败'
  } finally {
    wechatBusy.value = false
    stripWechatQuery()
  }
}

function startWechat() {
  err.value = ''
  if (!inWechat()) {
    err.value = '请在微信中打开本页后再使用微信登录'
    return
  }
  if (!oaAppId.value) {
    err.value = '尚未开通微信网页授权，请先用手机号登录'
    return
  }
  const authorize = new URL('https://open.weixin.qq.com/connect/oauth2/authorize')
  authorize.searchParams.set('appid', oaAppId.value)
  authorize.searchParams.set('redirect_uri', loginPageUrl().toString())
  authorize.searchParams.set('response_type', 'code')
  authorize.searchParams.set('scope', 'snsapi_base')
  authorize.searchParams.set('state', 'login')
  window.location.href = `${authorize.toString()}#wechat_redirect`
}

onMounted(async () => {
  try {
    const { data } = await http.get('/member/auth/wechat/oa/config')
    oaAppId.value = data.oa_app_id || ''
  } catch {
    oaAppId.value = ''
  }
  const wxCode = route.query.code
  if (typeof wxCode === 'string' && wxCode) {
    await loginByWechatCode(wxCode)
  } else if (inWechat() && route.query.wechat === '1' && oaAppId.value) {
    startWechat()
  }
  if (!referralCode.value) return
  try {
    const { data } = await http.get(`/promotions/${referralCode.value}`)
    promoterName.value = data.name
  } catch {
    promoterName.value = ''
  }
})

async function send() {
  err.value = ''
  tip.value = ''
  if (!phone.value.trim()) {
    err.value = '请填写手机号'
    return
  }
  sending.value = true
  try {
    await http.post('/member/auth/otp/send', {
      phone: phone.value.trim(),
      merchant_id: merchantId.value ?? null,
      scene: 'login',
    })
    tip.value = '验证码已发送，请查收短信'
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '发送失败'
  } finally {
    sending.value = false
  }
}

async function login() {
  err.value = ''
  if (!phone.value.trim()) {
    err.value = '请填写手机号'
    return
  }
  if (mode.value === 'otp' && !code.value.trim()) {
    err.value = '请填写验证码'
    return
  }
  if (mode.value === 'password' && !password.value) {
    err.value = '请填写登录密码'
    return
  }
  logging.value = true
  try {
    const { data } =
      mode.value === 'password'
        ? await http.post('/member/auth/password', {
            phone: phone.value.trim(),
            password: password.value,
            merchant_id: merchantId.value ?? null,
            wechat_ticket: wechatTicket.value || null,
          })
        : await http.post('/member/auth/otp/verify', {
            phone: phone.value.trim(),
            code: code.value.trim(),
            merchant_id: merchantId.value ?? null,
            referral_code: referralCode.value ?? null,
            wechat_ticket: wechatTicket.value || null,
          })
    await finishWithToken(data.access_token)
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '登录失败'
  } finally {
    logging.value = false
  }
}
</script>

<template>
  <div class="login">
    <header class="login__brand">
      <BrandMark variant="space" compact />
      <span class="login__badge">会员中心</span>
    </header>

    <p v-if="promoterName" class="login__promoter">来自「{{ promoterName }}」推荐</p>

    <div class="login__board">
      <form class="login__form" @submit.prevent="login">
        <div v-if="mode === 'otp'" class="pill">
          <span class="pill__prefix">+86</span>
          <input
            id="phone"
            v-model="phone"
            type="tel"
            inputmode="numeric"
            autocomplete="tel"
            maxlength="20"
            placeholder="请输入手机号"
          />
        </div>
        <div v-else class="pill">
          <input
            id="phone-pw"
            v-model="phone"
            type="tel"
            inputmode="numeric"
            autocomplete="tel"
            maxlength="20"
            placeholder="请输入手机号"
          />
        </div>

        <div v-if="mode === 'otp'" class="pill">
          <input
            id="code"
            v-model="code"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            maxlength="8"
            placeholder="请输入验证码"
          />
          <button class="pill__action" type="button" :disabled="sending" @click="send">
            {{ sending ? '发送中' : '发送验证码' }}
          </button>
        </div>
        <div v-else class="pill">
          <input
            id="password"
            v-model="password"
            type="password"
            autocomplete="current-password"
            maxlength="64"
            placeholder="请输入登录密码"
          />
        </div>

        <p class="login__legal">
          注册登录即代表已阅读并同意我们的
          <button class="login__legal-link" type="button" @click="legalDoc = 'terms'">平台协议</button>
          与
          <button class="login__legal-link" type="button" @click="legalDoc = 'privacy'">隐私政策</button>
          ，未注册的手机号将自动注册。
          <template v-if="merchantId">进入后会自动关联本店。</template>
        </p>

        <p v-if="tip" class="login__msg is-ok">{{ tip }}</p>
        <p v-if="err" class="login__msg is-err">{{ err }}</p>

        <button class="login__submit" type="submit" :disabled="logging">
          {{ logging ? '登录中…' : '登录' }}
        </button>
        <button
          v-if="insideWechat"
          class="login__wechat"
          type="button"
          :disabled="wechatBusy"
          @click="startWechat"
        >
          {{ wechatBusy ? '正在打开微信…' : '微信一键登录' }}
        </button>
        <button class="login__alt" type="button" @click="mode = mode === 'otp' ? 'password' : 'otp'">
          {{ mode === 'otp' ? '密码登录' : '验证码登录' }}
        </button>
      </form>
    </div>

    <p class="login__copy">{{ copyrightLine() }}</p>
    <LegalSheet :doc="legalDoc" @close="legalDoc = null" />
  </div>
</template>

<style scoped>
.login {
  min-height: 100vh;
  background: var(--mw-bg);
  color: var(--mw-text);
  padding: 56px 24px 40px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.login :deep(.brand-mark) {
  padding: 0;
}

.login__brand {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-bottom: 56px;
}

.login__badge {
  display: inline-flex;
  align-items: center;
  height: 22px;
  padding: 0 8px;
  border-radius: 4px;
  background: var(--mw-brand);
  color: var(--mw-brand-ink);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.login__promoter {
  margin: -28px 0 28px;
  font-size: 13px;
  color: var(--mw-brand);
}

.login__board {
  width: min(400px, 100%);
}

.login__form {
  min-width: 0;
}

.login button {
  background: transparent;
  color: inherit;
  border: 0;
  border-radius: 0;
  min-height: 0;
  padding: 0;
  font-weight: inherit;
}

.login input {
  width: auto;
  min-height: 0;
  padding: 0;
  border: 0;
  border-radius: 0;
  background: transparent;
  color: var(--mw-text);
}

.pill {
  display: flex;
  align-items: center;
  height: 48px;
  margin-bottom: 14px;
  border: 1px solid var(--mw-border);
  border-radius: 999px;
  background: var(--mw-bg-elevated);
  overflow: hidden;
}

.pill:focus-within {
  border-color: var(--mw-border-strong);
}

.pill input {
  flex: 1;
  min-width: 0;
  height: 100%;
  border: 0;
  outline: none;
  background: transparent;
  padding: 0 18px;
  font: inherit;
  color: var(--mw-text);
}

.pill input::placeholder {
  color: var(--mw-text-tertiary);
}

.pill__prefix {
  flex-shrink: 0;
  padding: 0 0 0 18px;
  color: var(--mw-text);
  font-weight: 500;
}

.pill__prefix::after {
  content: '';
  display: inline-block;
  width: 1px;
  height: 16px;
  margin-left: 12px;
  background: var(--mw-border);
  vertical-align: middle;
}

.login button.pill__action {
  flex-shrink: 0;
  height: 100%;
  padding: 0 16px;
  border: 0;
  border-left: 1px solid var(--mw-border);
  background: transparent;
  color: var(--mw-text);
  font: inherit;
  font-weight: 500;
  white-space: nowrap;
  cursor: pointer;
}

.pill__action:disabled {
  color: var(--mw-text-secondary);
}

.login__legal {
  margin: 8px 2px 20px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--mw-text-secondary);
}

.login button.login__legal-link {
  display: inline;
  width: auto;
  height: auto;
  margin: 0;
  padding: 0;
  border: 0;
  background: none;
  color: var(--mw-text);
  font: inherit;
  font-weight: 400;
  text-decoration: underline;
  text-underline-offset: 2px;
  cursor: pointer;
  vertical-align: baseline;
}

.login__msg {
  margin: 0 0 12px;
  font-size: 13px;
}

.login__msg.is-ok {
  color: var(--mw-success);
}

.login__msg.is-err {
  color: var(--mw-danger);
}

.login button.login__submit {
  width: 100%;
  height: 48px;
  border: 0;
  border-radius: 999px;
  background: var(--mw-brand);
  color: var(--mw-brand-ink);
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.login button.login__submit:disabled {
  opacity: 0.45;
}

.login button.login__alt {
  display: block;
  width: auto;
  margin: 16px auto 0;
  border: 0;
  background: none;
  color: var(--mw-text);
  font: inherit;
  font-size: 14px;
  font-weight: 400;
  text-decoration: underline;
  text-underline-offset: 3px;
  cursor: pointer;
}

.login button.login__wechat {
  display: flex;
  margin-top: 12px;
  width: 100%;
  height: 48px;
  border: 0;
  border-radius: 999px;
  background: #07c160;
  color: #fff;
  font: inherit;
  font-weight: 600;
  cursor: pointer;
}

.login__copy {
  margin-top: auto;
  padding-top: 48px;
  font-size: 12px;
  color: var(--mw-text-tertiary);
}

@media (max-width: 800px) {
  .login {
    padding: 36px 20px 28px;
  }
}
</style>
