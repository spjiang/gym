<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const phone = ref('')
const code = ref('')
const tip = ref('')
const err = ref('')
const sending = ref(false)
const logging = ref(false)

async function send() {
  err.value = ''
  tip.value = ''
  if (!phone.value.trim()) {
    err.value = '请填写手机号'
    return
  }
  sending.value = true
  try {
    await http.post('/member/auth/otp/send', { phone: phone.value.trim() })
    tip.value = '验证码已发送，请查收短信'
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '发送失败'
  } finally {
    sending.value = false
  }
}

async function login() {
  err.value = ''
  if (!phone.value.trim() || !code.value.trim()) {
    err.value = '请填写手机号与验证码'
    return
  }
  logging.value = true
  try {
    const { data } = await http.post('/member/auth/otp/verify', {
      phone: phone.value.trim(),
      code: code.value.trim(),
    })
    auth.setToken(data.access_token)
    await auth.fetchMe()
    router.replace((route.query.redirect as string) || '/')
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
      <p class="login__site">回龙观公园综合场地</p>
      <h1 class="login__title">会员中心</h1>
      <p class="login__desc">使用建档手机号登录，查看会籍、预约团课与在线购卡。</p>
    </header>

    <form class="login__form" @submit.prevent="login">
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

      <div class="mw-field">
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

      <p v-if="tip" class="mw-msg mw-msg--ok">{{ tip }}</p>
      <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>

      <button class="mw-btn mw-btn--block" type="submit" :disabled="logging">
        {{ logging ? '登录中…' : '登录' }}
      </button>
    </form>
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

.login__site {
  margin: 0 0 var(--mw-space-2);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--mw-text-secondary);
}

.login__title {
  font-size: 28px;
  line-height: 1.2;
  margin-bottom: var(--mw-space-3);
}

.login__desc {
  margin: 0;
  font-size: 14px;
  color: var(--mw-text-secondary);
  max-width: 28em;
}

.login__form {
  padding: var(--mw-space-5);
  background: var(--mw-surface);
  border: 1px solid var(--mw-border);
  border-radius: var(--mw-radius-lg);
}

.login__code-row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--mw-space-2);
}
</style>
