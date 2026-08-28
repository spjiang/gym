<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'
import { pathForMerchant, useAuthStore } from '../stores/auth'
import BrandMark from '../components/BrandMark.vue'
import { copyrightLine, COPYRIGHT_OWNER } from '../copyright'

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
const promoterName = ref('')

const merchantId = computed(() => {
  const raw = route.query.merchant_id
  const n = Number(Array.isArray(raw) ? raw[0] : raw)
  return n && !Number.isNaN(n) ? n : undefined
})

/** 推广码来自扫码链接，仅首次注册时绑定推荐关系 */
const referralCode = computed(() => {
  const raw = route.query.promoter ?? route.query.referral_code
  const value = Array.isArray(raw) ? raw[0] : raw
  return typeof value === 'string' && value.trim() ? value.trim().toUpperCase() : undefined
})

onMounted(async () => {
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
          })
        : await http.post('/member/auth/otp/verify', {
            phone: phone.value.trim(),
            code: code.value.trim(),
            merchant_id: merchantId.value ?? null,
            referral_code: referralCode.value ?? null,
          })
    auth.setToken(data.access_token)
    const me = await auth.fetchMe()
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
      <BrandMark variant="space" show-tagline />
      <h1 class="login__title">会员中心</h1>
      <p class="login__desc">
        <template v-if="merchantId">扫码加入门店 · 登录后自动关联本店</template>
        <template v-else>验证码可自动开通；已设密码的会员也可直接登录</template>
      </p>
      <p class="login__owner">由{{ COPYRIGHT_OWNER }}运营</p>
      <p v-if="promoterName" class="login__promoter">
        来自「{{ promoterName }}」推荐 · 验证码注册后自动绑定
      </p>
    </header>

    <form class="login__form" @submit.prevent="login">
      <div class="login__modes" role="tablist">
        <button
          type="button"
          class="login__mode"
          :class="{ 'is-active': mode === 'otp' }"
          @click="mode = 'otp'"
        >
          验证码登录
        </button>
        <button
          type="button"
          class="login__mode"
          :class="{ 'is-active': mode === 'password' }"
          @click="mode = 'password'"
        >
          密码登录
        </button>
      </div>
      <div class="mw-field">
        <label class="mw-field__label" for="phone">手机号</label>
        <input
          id="phone"
          v-model="phone"
          class="mw-input"
          type="tel"
          inputmode="numeric"
          autocomplete="tel"
          maxlength="20"
          placeholder="请输入手机号"
        />
      </div>

      <div v-if="mode === 'otp'" class="mw-field">
        <label class="mw-field__label" for="code">验证码</label>
        <div class="login__code-row">
          <input
            id="code"
            v-model="code"
            class="mw-input"
            type="text"
            inputmode="numeric"
            autocomplete="one-time-code"
            maxlength="8"
            placeholder="请输入验证码"
          />
          <button class="mw-btn mw-btn--ghost" type="button" :disabled="sending" @click="send">
            {{ sending ? '发送中' : '获取验证码' }}
          </button>
        </div>
      </div>

      <div v-else class="mw-field">
        <label class="mw-field__label" for="password">登录密码</label>
        <input
          id="password"
          v-model="password"
          class="mw-input"
          type="password"
          autocomplete="current-password"
          maxlength="64"
          placeholder="由门店或平台超管设置"
        />
      </div>

      <p v-if="tip" class="mw-msg mw-msg--ok">{{ tip }}</p>
      <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

      <button class="mw-btn mw-btn--block" type="submit" :disabled="logging">
        {{ logging ? '登录中…' : '登录' }}
      </button>
    </form>
    <p class="login__copy">{{ copyrightLine() }}</p>
  </div>
</template>

<style scoped>
.login {
  max-width: var(--mw-shell-max);
  margin: 0 auto;
  min-height: 100vh;
  padding: 48px var(--mw-space-4) var(--mw-space-6);
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.login__brand {
  margin-bottom: var(--mw-space-8);
}

.login__title {
  font-size: 22px;
  line-height: 1.2;
  margin: var(--mw-space-5) 0 var(--mw-space-3);
}

.login__desc {
  margin: 0;
  font-size: 14px;
  color: var(--mw-text-secondary);
  max-width: 28em;
}

.login__owner,
.login__copy {
  margin: var(--mw-space-2) 0 0;
  font-size: 12px;
  color: var(--mw-text-tertiary);
}

.login__copy {
  margin-top: var(--mw-space-6);
  text-align: center;
}

.login__promoter {
  margin: var(--mw-space-2) 0 0;
  font-size: 13px;
  color: var(--mw-brand);
}

.login__form {
  padding: var(--mw-space-5);
  background: var(--mw-surface);
  border: 1px solid var(--mw-border);
  border-radius: var(--mw-radius-lg);
}

.login__modes {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
  margin-bottom: var(--mw-space-4);
}

.login__mode {
  height: 36px;
  border: 1px solid var(--mw-border);
  border-radius: var(--mw-radius-sm);
  background: transparent;
  color: var(--mw-text-secondary);
  font: inherit;
  cursor: pointer;
}

.login__mode.is-active {
  border-color: var(--mw-brand);
  color: var(--mw-text);
  background: var(--mw-brand-muted);
}

.login__code-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--mw-space-2);
}
</style>
