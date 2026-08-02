<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import http from '../api/http'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const phone = ref('')
const code = ref('123456')
const tip = ref('')
const err = ref('')

async function send() {
  err.value = ''
  try {
    await http.post('/member/auth/otp/send', { phone: phone.value })
    tip.value = '验证码已发送（开发环境默认 123456）'
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '发送失败'
  }
}

async function login() {
  err.value = ''
  try {
    const { data } = await http.post('/member/auth/otp/verify', {
      phone: phone.value,
      code: code.value,
    })
    auth.setToken(data.access_token)
    await auth.fetchMe()
    router.replace((route.query.redirect as string) || '/')
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '登录失败'
  }
}
</script>

<template>
  <div class="login">
    <h1>会员中心</h1>
    <p class="muted">手机号验证码登录</p>
    <div class="card">
      <label>手机号</label>
      <input v-model="phone" placeholder="已建档手机号" />
      <div class="row">
        <input v-model="code" placeholder="验证码" />
        <button class="ghost" type="button" @click="send">获取验证码</button>
      </div>
      <p v-if="tip" class="muted">{{ tip }}</p>
      <p v-if="err" class="err">{{ err }}</p>
      <button style="width: 100%; margin-top: 0.75rem" @click="login">登录</button>
    </div>
  </div>
</template>

<style scoped>
.login {
  max-width: 420px;
  margin: 0 auto;
  padding: 2.5rem 1rem;
}
h1 {
  margin: 0 0 0.25rem;
  font-size: 1.75rem;
}
label {
  display: block;
  margin: 0.5rem 0 0.35rem;
  font-size: 0.875rem;
}
.row {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
</style>
