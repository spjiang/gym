<script setup lang="ts">
import { ref, watch } from 'vue'
import http from '../api/http'

type MemberAgreement = { id: number; title: string; content: string }

const props = defineProps<{
  open: boolean
  merchantId: number | undefined
  scene: string
  summary: string
  confirmLabel?: string
}>()

const emit = defineEmits<{
  'update:open': [boolean]
  confirm: []
}>()

const loading = ref(false)
const err = ref('')
const agreed = ref(false)
const fullOpen = ref(false)
const agreement = ref<MemberAgreement | null>(null)

function close() {
  emit('update:open', false)
}

async function load() {
  if (!props.merchantId) {
    err.value = '请先选择门店'
    loading.value = false
    return
  }
  loading.value = true
  err.value = ''
  agreed.value = false
  fullOpen.value = false
  agreement.value = null
  try {
    const { data } = await http.get<MemberAgreement>('/member/agreements', {
      params: { merchant_id: props.merchantId, scene: props.scene },
    })
    agreement.value = data
  } catch (e: unknown) {
    err.value = e instanceof Error ? e.message : '该门店尚未配置购买协议，请联系门店'
  } finally {
    loading.value = false
  }
}

function submit() {
  if (!agreement.value) return
  if (!agreed.value) {
    err.value = '请先阅读并同意协议'
    return
  }
  emit('confirm')
  emit('update:open', false)
}

watch(
  () => props.open,
  (v) => {
    if (v) void load()
  },
)
</script>

<template>
  <div v-if="open" class="sheet" role="dialog" aria-label="确认购买">
    <button type="button" class="sheet__mask" aria-label="关闭" @click="close" />
    <div class="sheet__panel">
      <div class="sheet__head">
        <strong>确认订单</strong>
        <button type="button" class="sheet__close" @click="close">取消</button>
      </div>
      <p v-if="summary" class="summary">{{ summary }}</p>
      <p v-if="loading" class="mw-page__desc">加载协议…</p>
      <p v-else-if="err && !agreement" class="mw-msg mw-msg--error">{{ err }}</p>
      <template v-else-if="agreement">
        <p v-if="err" class="mw-msg mw-msg--error">{{ err }}</p>
        <label class="agree">
          <input v-model="agreed" type="checkbox" />
          <span class="agree__text">
            我已阅读并同意
            <button type="button" class="link" @click.prevent="fullOpen = true">《{{ agreement.title }}》</button>
          </span>
        </label>
        <button class="mw-btn mw-btn--block" type="button" :disabled="!agreed" @click="submit">
          {{ confirmLabel || '确认支付' }}
        </button>
      </template>
    </div>
    <div v-if="fullOpen && agreement" class="sheet sheet--full" role="dialog" aria-label="协议全文">
      <button type="button" class="sheet__mask" aria-label="关闭全文" @click="fullOpen = false" />
      <div class="sheet__panel sheet__panel--full">
        <div class="sheet__head">
          <strong>{{ agreement.title }}</strong>
          <button type="button" class="sheet__close" @click="fullOpen = false">关闭</button>
        </div>
        <div class="body" v-html="agreement.content" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.sheet {
  position: fixed;
  inset: 0;
  z-index: 50;
}
.sheet--full {
  z-index: 51;
}
.sheet__mask {
  position: absolute;
  inset: 0;
  border: 0;
  min-height: 0;
  padding: 0;
  background: rgba(0, 0, 0, 0.55);
}
.sheet__panel {
  position: absolute;
  left: 50%;
  transform: translateX(-50%);
  bottom: 0;
  width: min(100%, var(--mw-shell-max));
  max-height: 80vh;
  overflow: auto;
  padding: 16px 16px calc(16px + var(--mw-safe-bottom));
  border-radius: 16px 16px 0 0;
  background: var(--mw-bg-elevated);
}
.sheet__panel--full {
  max-height: 88vh;
}
.sheet__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.sheet__close {
  min-height: 32px;
  padding: 0;
  border: 0;
  background: transparent;
  color: var(--mw-text-secondary);
  font-size: 13px;
}
.summary {
  margin: 0 0 12px;
  font-weight: 650;
}
.agree {
  display: flex;
  gap: 8px;
  align-items: flex-start;
  margin: 12px 0 16px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--mw-text-secondary);
}
.agree input {
  width: 18px;
  height: 18px;
  min-height: 0;
  margin-top: 3px;
  flex-shrink: 0;
}
.agree__text {
  flex: 1;
  min-width: 0;
}
.link {
  display: inline;
  border: 0;
  padding: 0;
  min-height: 0;
  height: auto;
  width: auto;
  background: transparent;
  color: var(--mw-brand);
  font: inherit;
  font-weight: 650;
  vertical-align: baseline;
}
.body {
  white-space: pre-wrap;
  font-size: 14px;
  line-height: 1.7;
  color: var(--mw-text);
}
.body :deep(p) {
  margin: 0 0 10px;
}
</style>
