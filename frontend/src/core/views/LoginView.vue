<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useAuthStore } from '../stores/auth'
import BrandMark from '../components/BrandMark.vue'
import { copyrightLine, COPYRIGHT_OWNER } from '../copyright'

type DemoAccount = {
  role: string
  person?: string
  username: string
  password: string
  hint?: string
}

type DemoSection = {
  label: string
  accounts: DemoAccount[]
}

type DemoGroup = {
  code: string
  name: string
  tone: 'space' | 'fit' | 'bar'
  sections: DemoSection[]
}

/** 演示身份：与 seed / Demo账号说明 一致 */
const DEMO_GROUPS: DemoGroup[] = [
  {
    code: 'SPACE',
    name: '场地综合',
    tone: 'space',
    sections: [
      {
        label: '管理层',
        accounts: [
          { role: '场地超管', username: 'admin', password: 'Admin@123456', hint: '全权限' },
          { role: '综合运营', person: '张敏', username: 'site_ops', password: 'Demo@123456', hint: '跨业态运营' },
          { role: '财务', person: '李会计', username: 'finance', password: 'Demo@123456', hint: '对账与提现' },
        ],
      },
    ],
  },
  {
    code: 'FIT',
    name: '观野FIT',
    tone: 'fit',
    sections: [
      {
        label: '门店',
        accounts: [
          { role: '管理员', person: '陈店长', username: 'gym_admin', password: 'Demo@123456', hint: '门店全权' },
          { role: '运营', person: '小陈', username: 'gym_ops', password: 'Demo@123456', hint: '排课 · 报表' },
          { role: '前台', person: '小王', username: 'front01', password: 'Demo@123456', hint: '接待与收银' },
        ],
      },
      {
        label: '教练',
        accounts: [
          { role: '教练', person: '阿强', username: 'coach01', password: 'Demo@123456', hint: '团课 · 私教' },
          { role: '教练', person: '小雅', username: 'coach02', password: 'Demo@123456', hint: '团课 · 私教' },
        ],
      },
      {
        label: '销售',
        accounts: [
          { role: '销售', person: '大明', username: 'sales01', password: 'Demo@123456', hint: '会籍 · 课包' },
          { role: '销售', person: '小芳', username: 'sales02', password: 'Demo@123456', hint: '会籍 · 课包' },
          { role: '销售', person: '小军', username: 'sales03', password: 'Demo@123456', hint: '会籍 · 课包' },
        ],
      },
    ],
  },
  {
    code: 'BAR',
    name: '观野BAR',
    tone: 'bar',
    sections: [
      {
        label: '门店',
        accounts: [
          { role: '管理人员', person: '赵店长', username: 'bar_admin', password: 'Demo@123456', hint: '菜单与人员' },
          { role: '运营', person: '小周', username: 'bar_ops', password: 'Demo@123456', hint: '日常运营' },
          { role: '收银', person: '小刘', username: 'bar_cashier', password: 'Demo@123456', hint: '点餐收银' },
        ],
      },
    ],
  },
]

const ALL_ACCOUNTS = DEMO_GROUPS.flatMap((g) =>
  g.sections.flatMap((s) => s.accounts.map((a) => ({ ...a, group: g.code, groupName: g.name }))),
)

function accountTitle(acc: DemoAccount) {
  return acc.person ? `${acc.role} · ${acc.person}` : acc.role
}

const username = ref('admin')
const password = ref('Admin@123456')
const loading = ref(false)
/** 手风琴：同时只展开一个业态分组 */
const expandedGroup = ref('SPACE')
const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const activeAccount = computed(() => ALL_ACCOUNTS.find((a) => a.username === username.value))

const activeLabel = computed(() => {
  const hit = activeAccount.value
  if (!hit) return ''
  return `${hit.group} · ${accountTitle(hit)}`
})

function fillDemo(account: DemoAccount, groupCode: string) {
  username.value = account.username
  password.value = account.password
  expandedGroup.value = groupCode
}

function toggleGroup(code: string) {
  expandedGroup.value = expandedGroup.value === code ? '' : code
}

function groupAccountCount(group: DemoGroup) {
  return group.sections.reduce((n, s) => n + s.accounts.length, 0)
}

function groupHasActive(group: DemoGroup) {
  return group.sections.some((s) => s.accounts.some((a) => a.username === username.value))
}

function isExpanded(code: string) {
  return expandedGroup.value === code
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
        <p class="hero-foot">{{ COPYRIGHT_OWNER }} · 版权所有</p>
      </section>

      <section class="form-panel">
        <p class="form-kicker">Staff Access</p>
        <h2>欢迎回来</h2>
        <p class="sub">凭所授之职，启今日之经营。</p>

        <div class="identity" aria-label="体验身份">
          <div class="identity-head">
            <div>
              <span class="identity-kicker">择一身份入场</span>
              <p v-if="activeAccount" class="identity-active">
                当前 <strong>{{ activeLabel }}</strong>
                <code>@{{ activeAccount.username }}</code>
              </p>
            </div>
          </div>

          <div class="group-stack">
            <article
              v-for="group in DEMO_GROUPS"
              :key="group.code"
              class="biz-group"
              :class="[
                `tone-${group.tone}`,
                { expanded: isExpanded(group.code), 'has-active': groupHasActive(group) },
              ]"
            >
              <button type="button" class="biz-head" @click="toggleGroup(group.code)">
                <span class="biz-head-main">
                  <span class="biz-code">{{ group.code }}</span>
                  <span class="biz-name">{{ group.name }}</span>
                  <span class="biz-count">{{ groupAccountCount(group) }} 账号</span>
                </span>
                <span class="biz-head-side">
                  <em v-if="groupHasActive(group) && !isExpanded(group.code)" class="biz-picked">已选</em>
                  <span class="chevron" aria-hidden="true" />
                </span>
              </button>

              <div v-show="isExpanded(group.code)" class="biz-body">
                <div v-for="section in group.sections" :key="section.label" class="biz-section">
                  <span v-if="group.sections.length > 1" class="section-label">{{ section.label }}</span>
                  <div class="account-grid">
                    <button
                      v-for="acc in section.accounts"
                      :key="acc.username"
                      type="button"
                      class="account-card"
                      :class="{ active: username === acc.username }"
                      @click="fillDemo(acc, group.code)"
                    >
                      <span class="card-top">
                        <span class="card-role">{{ acc.role }}</span>
                        <span v-if="acc.hint" class="card-hint">{{ acc.hint }}</span>
                      </span>
                      <span class="card-name">{{ acc.person || acc.role }}</span>
                      <span class="card-user">@{{ acc.username }}</span>
                    </button>
                  </div>
                </div>
              </div>
            </article>
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
    <p class="page-copy">{{ copyrightLine() }}</p>
  </div>
</template>

<style scoped>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@500;600&family=JetBrains+Mono:wght@400;500&family=Noto+Serif+SC:wght@500;600;700&display=swap');

.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 28px 16px;
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

.page-copy {
  position: relative;
  z-index: 1;
  margin: 18px 0 0;
  text-align: center;
  font-size: 0.75rem;
  color: rgba(197, 203, 198, 0.55);
}

.login-shell {
  position: relative;
  z-index: 1;
  width: min(1080px, 100%);
  display: grid;
  grid-template-columns: 0.95fr 1.05fr;
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
  padding: 52px 44px;
  color: #f5f0e8;
  background:
    linear-gradient(165deg, rgba(61, 107, 92, 0.34), transparent 52%),
    linear-gradient(25deg, rgba(166, 124, 82, 0.14), transparent 42%);
  display: flex;
  flex-direction: column;
  min-height: 560px;
}

.hero-copy :deep(.brand-mark) {
  margin-bottom: 24px;
}

.system-name {
  margin: 18px 0 0;
  font-family: 'Noto Sans SC', 'PingFang SC', sans-serif;
  font-size: 1.12rem;
  font-weight: 600;
  letter-spacing: 0.18em;
  color: #faf6ef;
}

.lead {
  margin-top: 20px;
  max-width: 18em;
  color: rgba(245, 240, 232, 0.72);
  font-size: 1rem;
  line-height: 1.75;
}

.hero-foot {
  margin-top: auto;
  padding-top: 36px;
  font-size: 0.78rem;
  letter-spacing: 0.12em;
  color: rgba(197, 203, 198, 0.55);
}

.form-panel {
  padding: 40px 36px 36px;
  background: #f2e6d2;
}

.form-kicker {
  margin: 0 0 6px;
  font-family: 'Cormorant Garamond', serif;
  font-size: 0.88rem;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: #f36b21;
}

.form-panel h2 {
  margin: 0;
  font-family: 'Noto Serif SC', 'Songti SC', serif;
  font-size: 1.65rem;
  font-weight: 600;
  color: #1c1917;
  letter-spacing: 0.06em;
}

.sub {
  margin: 6px 0 18px;
  color: #78716c;
  font-size: 0.9rem;
  line-height: 1.55;
}

.identity {
  margin-bottom: 18px;
  padding: 14px;
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.62);
  border: 1px solid rgba(28, 25, 23, 0.06);
}

.identity-head {
  margin-bottom: 12px;
}

.identity-kicker {
  display: block;
  font-size: 0.72rem;
  letter-spacing: 0.1em;
  color: #a8a29e;
  text-transform: uppercase;
}

.identity-active {
  margin: 6px 0 0;
  font-size: 0.82rem;
  color: #57534e;
  line-height: 1.5;
}

.identity-active strong {
  color: #f36b21;
  font-weight: 600;
}

.identity-active code {
  display: inline-block;
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 6px;
  background: rgba(243, 107, 33, 0.1);
  color: #c2410c;
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 0.76rem;
}

.group-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.biz-group {
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  border: 1px solid rgba(28, 25, 23, 0.05);
  border-left: 3px solid var(--tone, #f36b21);
  overflow: hidden;
}

.biz-group.has-active:not(.expanded) {
  box-shadow: inset 0 0 0 1px rgba(243, 107, 33, 0.15);
}

.biz-head {
  display: flex;
  width: 100%;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 10px 12px;
  border: none;
  background: transparent;
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition: background 0.2s ease;
}

.biz-head:hover {
  background: rgba(243, 107, 33, 0.04);
}

.biz-head-main {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px 8px;
  min-width: 0;
}

.biz-head-side {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.biz-picked {
  font-style: normal;
  font-size: 0.68rem;
  color: #f36b21;
  font-weight: 600;
  letter-spacing: 0.04em;
}

.chevron {
  width: 8px;
  height: 8px;
  border-right: 1.5px solid #a8a29e;
  border-bottom: 1.5px solid #a8a29e;
  transform: rotate(45deg);
  transition: transform 0.22s ease;
  margin-top: -2px;
}

.biz-group.expanded .chevron {
  transform: rotate(-135deg);
  margin-top: 2px;
}

.biz-count {
  font-size: 0.64rem;
  color: #d6d3d1;
  letter-spacing: 0.04em;
}

.biz-body {
  padding: 0 10px 10px;
}

.biz-group.tone-space {
  --tone: #f36b21;
}

.biz-group.tone-fit {
  --tone: #3d6b5c;
}

.biz-group.tone-bar {
  --tone: #14b8d4;
}

.biz-code {
  font-family: Montserrat, Arial, sans-serif;
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.14em;
  color: var(--tone);
}

.biz-name {
  font-size: 0.72rem;
  color: #a8a29e;
  letter-spacing: 0.04em;
}

.biz-section + .biz-section {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px dashed rgba(28, 25, 23, 0.08);
}

.section-label {
  display: block;
  margin: 0 2px 6px;
  font-size: 0.68rem;
  letter-spacing: 0.08em;
  color: #a8a29e;
}

.account-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(118px, 1fr));
  gap: 8px;
}

.account-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 2px;
  padding: 10px 11px;
  border-radius: 12px;
  border: 1px solid #e8e0d4;
  background: linear-gradient(180deg, #fffefb 0%, #faf7f2 100%);
  cursor: pointer;
  font: inherit;
  text-align: left;
  transition:
    border-color 0.2s ease,
    box-shadow 0.2s ease,
    transform 0.2s ease,
    background 0.2s ease;
}

.account-card:hover {
  border-color: #f36b21;
  transform: translateY(-2px);
  box-shadow: 0 10px 24px -18px rgba(28, 25, 23, 0.55);
}

.account-card.active {
  border-color: transparent;
  background: linear-gradient(145deg, #f36b21 0%, #e85d14 100%);
  box-shadow: 0 12px 28px -16px rgba(243, 107, 33, 0.75);
  transform: translateY(-1px);
}

.card-top {
  display: flex;
  width: 100%;
  justify-content: space-between;
  align-items: center;
  gap: 4px;
}

.card-role {
  font-size: 0.64rem;
  letter-spacing: 0.06em;
  color: #a8a29e;
  font-weight: 600;
}

.account-card.active .card-role {
  color: rgba(255, 255, 255, 0.82);
}

.card-hint {
  font-size: 0.58rem;
  color: #d6d3d1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 48px;
}

.account-card.active .card-hint {
  color: rgba(255, 255, 255, 0.65);
}

.card-name {
  font-size: 0.92rem;
  font-weight: 700;
  color: #292524;
  line-height: 1.25;
}

.account-card.active .card-name {
  color: #fff;
}

.card-user {
  font-family: 'JetBrains Mono', ui-monospace, monospace;
  font-size: 0.68rem;
  color: #78716c;
  letter-spacing: -0.02em;
}

.account-card.active .card-user {
  color: rgba(255, 255, 255, 0.88);
}

.submit {
  width: 100%;
  margin-top: 8px;
  height: 48px;
  font-weight: 600;
  letter-spacing: 0.12em;
  border-radius: 14px !important;
}

.form-panel :deep(.el-form-item) {
  margin-bottom: 14px;
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

@media (max-width: 920px) {
  .login-shell {
    grid-template-columns: 1fr;
  }
  .hero-copy {
    min-height: auto;
    padding: 32px 24px 24px;
  }
  .form-panel {
    max-height: none;
    padding: 24px 20px 28px;
  }
  .account-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
