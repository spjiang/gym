<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import BrandMark from '../components/BrandMark.vue'

/** 按组织角色命名的演示身份（对应商户角色实例） */
const DEMO_GROUPS = [
  {
    title: 'SPACE',
    accounts: [
      { label: '场地管理员', username: 'admin', password: 'Admin@123456' },
      { label: '场地运营', username: 'site_ops', password: 'Demo@123456' },
    ],
  },
  {
    title: 'FIT',
    accounts: [
      { label: '管理员', username: 'gym_admin', password: 'Demo@123456' },
      { label: '运营', username: 'gym_ops', password: 'Demo@123456' },
      { label: '教练', username: 'coach01', password: 'Demo@123456' },
    ],
  },
  {
    title: 'BAR',
    accounts: [
      { label: '管理人员', username: 'bar_admin', password: 'Demo@123456' },
      { label: '运营', username: 'bar_ops', password: 'Demo@123456' },
      { label: '收银', username: 'bar_cashier', password: 'Demo@123456' },
    ],
  },
] as const

type DemoAccount = (typeof DEMO_GROUPS)[number]['accounts'][number]

const username = ref('admin')
const password = ref('Admin@123456')
const loading = ref(false)
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const activeLabel = computed(() => {
  for (const g of DEMO_GROUPS) {
    const hit = g.accounts.find((a) => a.username === username.value)
    if (hit) return `${g.title} · ${hit.label}`
  }
  return ''
})

function fillDemo(account: DemoAccount) {
  username.value = account.username
  password.value = account.password
}

async function onSubmit() {
  loading.value = true
  try {
    await auth.login(username.value, password.value)
    ElMessage.success('欢迎回来')
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
    <div class="atmosphere" aria-hidden="true">
      <span class="orb orb-a" />
      <span class="orb orb-b" />
      <span class="veil" />
    </div>

    <div class="login-shell">
      <section class="hero-copy">
        <BrandMark variant="space" show-tagline />
        <h1 class="system-name">综合管理平台</h1>
        <p class="lead">观野SPACE · 观野FIT · 观野BAR<br />会籍与门禁、课程与酒吧，同归一处。</p>
        <p class="hero-foot">以秩序承载运营，以权限守护边界</p>
      </section>

      <section class="form-panel">
        <p class="form-kicker">Staff Access</p>
        <h2>欢迎归来</h2>
        <p class="sub">凭所授之职，启今日之经营。</p>

        <div class="identity" aria-label="体验身份">
          <div class="identity-head">
            <span>择一身份入场</span>
            <em v-if="activeLabel">{{ activeLabel }}</em>
          </div>
          <div v-for="group in DEMO_GROUPS" :key="group.title" class="identity-group">
            <span class="group-title">{{ group.title }}</span>
            <div class="demo-list">
              <button
                v-for="acc in group.accounts"
                :key="acc.username"
                type="button"
                class="demo-chip"
                :class="{ active: username === acc.username }"
                @click="fillDemo(acc)"
              >
                {{ acc.label }}
              </button>
            </div>
          </div>
        </div>

        <el-form label-position="top" @submit.prevent="onSubmit">
          <el-form-item label="账号">
            <el-input v-model="username" autocomplete="username" size="large" placeholder="请输入账号" />
          </el-form-item>
          <el-form-item label="密钥">
            <el-input
              v-model="password"
              type="password"
              autocomplete="current-password"
              show-password
              size="large"
              placeholder="请输入密钥"
            />
          </el-form-item>
          <el-button
            type="primary"
            native-type="submit"
            :loading="loading"
            size="large"
            class="submit"
          >
            开启今日运营
          </el-button>
        </el-form>
      </section>
    </div>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=Noto+Serif+SC:wght@500;600;700&display=swap');

.login-page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  padding: 36px 20px;
  position: relative;
  overflow: hidden;
}

.atmosphere {
  position: absolute;
  inset: 0;
  background:
    radial-gradient(900px 480px at 12% 0%, rgba(242, 230, 210, 0.06), transparent 58%),
    #171b1f;
}

.orb {
  position: absolute;
  border-radius: 50%;
  filter: blur(40px);
  opacity: 0.55;
  animation: drift 14s ease-in-out infinite alternate;
}

.orb-a {
  width: 280px;
  height: 280px;
  left: 8%;
  top: 18%;
  background: rgba(243, 107, 33, 0.22);
}

.orb-b {
  width: 340px;
  height: 340px;
  right: 6%;
  bottom: 12%;
  background: rgba(20, 184, 212, 0.18);
  animation-delay: -4s;
}

.veil {
  position: absolute;
  inset: 0;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.025) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.025) 1px, transparent 1px);
  background-size: 56px 56px;
  mask-image: radial-gradient(ellipse at 50% 40%, black 20%, transparent 72%);
  opacity: 0.7;
}

.login-shell {
  position: relative;
  z-index: 1;
  width: min(980px, 100%);
  display: grid;
  grid-template-columns: 1.15fr 0.95fr;
  border-radius: 32px;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(12, 16, 14, 0.62);
  box-shadow:
    0 50px 100px -48px rgba(0, 0, 0, 0.85),
    inset 0 1px 0 rgba(255, 255, 255, 0.06);
  backdrop-filter: blur(22px);
  animation: rise 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
}

.hero-copy {
  padding: 56px 48px;
  color: #f5f0e8;
  background:
    linear-gradient(165deg, rgba(61, 107, 92, 0.34), transparent 52%),
    linear-gradient(25deg, rgba(166, 124, 82, 0.14), transparent 42%);
  display: flex;
  flex-direction: column;
  min-height: 560px;
}

.hero-copy :deep(.brand-mark) {
  margin-bottom: 28px;
}

.system-name {
  margin: 22px 0 0;
  font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
  font-size: 1.15rem;
  font-weight: 600;
  letter-spacing: 0.18em;
  color: #faf6ef;
}

.lead {
  margin-top: 22px;
  max-width: 18em;
  color: rgba(245, 240, 232, 0.72);
  font-size: 1.02rem;
  line-height: 1.75;
  font-weight: 400;
}

.hero-foot {
  margin-top: auto;
  padding-top: 40px;
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  color: rgba(197, 203, 198, 0.55);
}

.form-panel {
  padding: 48px 40px 44px;
  background: #f2e6d2;
}

.form-kicker {
  margin: 0 0 8px;
  font-family: 'Cormorant Garamond', serif;
  font-size: 0.88rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #f36b21;
}

.form-panel h2 {
  margin: 0;
  font-family: 'Noto Serif SC', 'Songti SC', serif;
  font-size: 1.75rem;
  font-weight: 600;
  color: #1c1917;
  letter-spacing: 0.06em;
}

.sub {
  margin: 8px 0 22px;
  color: #78716c;
  font-size: 0.92rem;
  line-height: 1.55;
}

.identity {
  margin-bottom: 22px;
  padding: 14px 14px 10px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.55);
  border: 1px solid rgba(28, 25, 23, 0.06);
}

.identity-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 12px;
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  color: #a8a29e;
}

.identity-head em {
  font-style: normal;
  color: #f36b21;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.identity-group {
  display: grid;
  grid-template-columns: 56px 1fr;
  gap: 8px;
  align-items: start;
  margin-bottom: 8px;
}

.group-title {
  padding-top: 6px;
  font-size: 0.72rem;
  color: #a8a29e;
  letter-spacing: 0.06em;
}

.demo-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.demo-chip {
  border: 1px solid #e4ddd2;
  background: #fffefb;
  color: #57534e;
  font-size: 0.76rem;
  padding: 6px 11px;
  border-radius: 999px;
  cursor: pointer;
  font: inherit;
  transition:
    border-color 0.2s ease,
    background 0.2s ease,
    color 0.2s ease,
    transform 0.2s ease;
}

.demo-chip:hover {
  border-color: #f36b21;
  color: #d85a16;
  transform: translateY(-1px);
}

.demo-chip.active {
  border-color: transparent;
  background: #f36b21;
  color: #f7f3ec;
  font-weight: 600;
  box-shadow: 0 8px 18px -12px rgba(47, 85, 73, 0.9);
}

.submit {
  width: 100%;
  margin-top: 10px;
  height: 48px;
  font-weight: 600;
  letter-spacing: 0.12em;
  border-radius: 14px !important;
}

.form-panel :deep(.el-form-item__label) {
  color: #78716c;
  font-weight: 500;
  letter-spacing: 0.06em;
}

.form-panel :deep(.el-input__wrapper) {
  border-radius: 14px;
  background: #fff;
  box-shadow: 0 0 0 1px #e7e0d6 inset;
  min-height: 46px;
}

.form-panel :deep(.el-input__wrapper:hover),
.form-panel :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #f36b21 inset !important;
}

@keyframes rise {
  from {
    opacity: 0;
    transform: translateY(22px) scale(0.98);
  }
  to {
    opacity: 1;
    transform: translateY(0) scale(1);
  }
}

@keyframes drift {
  from {
    transform: translate(0, 0) scale(1);
  }
  to {
    transform: translate(24px, -18px) scale(1.08);
  }
}

@keyframes glow {
  0%,
  100% {
    box-shadow: 0 16px 36px -16px rgba(166, 124, 82, 0.85);
  }
  50% {
    box-shadow: 0 18px 42px -12px rgba(196, 160, 116, 1);
  }
}

@media (max-width: 860px) {
  .login-shell {
    grid-template-columns: 1fr;
  }
  .hero-copy {
    min-height: auto;
    padding: 36px 28px 28px;
  }
  .form-panel {
    padding: 28px 24px 32px;
  }
  .identity-group {
    grid-template-columns: 1fr;
  }
}
</style>
