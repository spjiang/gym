<script setup lang="ts">
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'

const username = ref('admin')
const password = ref('Admin@123456')
const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

async function onSubmit() {
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    ElMessage.success('登录成功')
    const redirect = (route.query.redirect as string) || '/'
    await router.replace(redirect)
  } catch (e) {
    ElMessage.error((e as Error).message)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="atmosphere" aria-hidden="true" />
    <div class="login-shell">
      <section class="hero-copy">
        <div class="mark" />
        <p class="eyebrow">Huilongguan Venue Ops</p>
        <h1>回龙观综合场地<br />经营管理系统</h1>
        <p class="lead">会籍、课程、门禁与商户运营统一后台。</p>
      </section>
      <section class="form-panel">
        <h2>员工登录</h2>
        <p class="sub">使用分配的账号进入运营工作台</p>
        <el-form label-position="top" @submit.prevent="onSubmit">
          <el-form-item label="用户名">
            <el-input v-model="username" autocomplete="username" size="large" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input
              v-model="password"
              type="password"
              autocomplete="current-password"
              show-password
              size="large"
            />
          </el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            size="large"
            class="submit"
          >
            进入系统
          </el-button>
        </el-form>
      </section>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 32px 20px;
  position: relative;
  overflow: hidden;
}

.atmosphere {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(900px 520px at 18% 20%, rgba(166, 124, 82, 0.28), transparent 60%),
    radial-gradient(700px 480px at 82% 15%, rgba(61, 107, 92, 0.35), transparent 55%),
    linear-gradient(145deg, #101412 0%, #1a221e 42%, #24302a 100%);
}

.atmosphere::after {
  content: '';
  position: absolute;
  inset: 0;
  background-image: linear-gradient(rgba(255, 255, 255, 0.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.03) 1px, transparent 1px);
  background-size: 48px 48px;
  mask-image: radial-gradient(circle at 50% 40%, black, transparent 75%);
  opacity: 0.45;
}

.login-shell {
  position: relative;
  z-index: 1;
  width: min(920px, 100%);
  display: grid;
  grid-template-columns: 1.1fr 0.9fr;
  gap: 0;
  border-radius: 28px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(15, 18, 16, 0.55);
  box-shadow: 0 40px 80px -40px rgba(0, 0, 0, 0.7);
  backdrop-filter: blur(18px);
  animation: rise 0.55s ease both;
}

.hero-copy {
  padding: 48px 40px;
  color: #f5f0e8;
  background:
    linear-gradient(160deg, rgba(61, 107, 92, 0.28), transparent 55%),
    linear-gradient(20deg, rgba(166, 124, 82, 0.12), transparent 40%);
}

.mark {
  width: 42px;
  height: 42px;
  border-radius: 14px;
  margin-bottom: 28px;
  background: linear-gradient(145deg, #a67c52, #3d6b5c);
  box-shadow: 0 12px 28px -14px rgba(166, 124, 82, 0.9);
}

.eyebrow {
  margin: 0 0 12px;
  font-size: 0.75rem;
  letter-spacing: 0.16em;
  text-transform: uppercase;
  color: #a67c52;
  font-weight: 600;
}

.hero-copy h1 {
  margin: 0;
  font-size: clamp(1.8rem, 3vw, 2.35rem);
  line-height: 1.2;
  letter-spacing: -0.03em;
  font-weight: 700;
  color: #f7f3ec;
}

.lead {
  margin-top: 16px;
  max-width: 28ch;
  color: rgba(245, 240, 232, 0.72);
  font-size: 0.98rem;
  line-height: 1.55;
}

.form-panel {
  padding: 44px 36px;
  background: linear-gradient(180deg, #fffcf8 0%, #f4efe6 100%);
}

.form-panel h2 {
  margin: 0;
  font-size: 1.35rem;
  color: #1c1917;
  letter-spacing: -0.02em;
}

.sub {
  margin: 6px 0 24px;
  color: #78716c;
  font-size: 0.9rem;
}

.submit {
  width: 100%;
  margin-top: 8px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.form-panel :deep(.el-form-item__label) {
  color: #78716c;
  font-weight: 500;
}

.form-panel :deep(.el-input__wrapper) {
  border-radius: 12px;
  background: #fff;
  box-shadow: 0 0 0 1px #e7e0d6 inset;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(14px) scale(0.985);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@media (max-width: 820px) {
  .login-shell {
    grid-template-columns: 1fr;
  }
  .hero-copy {
    padding: 32px 28px 20px;
  }
  .form-panel {
    padding: 28px;
  }
}
</style>
