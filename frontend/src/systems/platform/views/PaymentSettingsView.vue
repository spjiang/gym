<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import http from '../../../core/api/http'

type SecretFlag = { configured: boolean }
type Settings = {
  mode: string
  dry_run: boolean
  source: string
  mp_app_id: string
  oa_app_id: string
  mch_id: string
  mch_serial_no: string
  notify_url: string
  h5_return_url: string
  mp_app_secret: SecretFlag
  oa_app_secret: SecretFlag
  api_v3_key: SecretFlag
  mch_private_key: SecretFlag
}

const loading = ref(false)
const saving = ref(false)
const form = reactive({
  mode: 'unconfigured',
  dry_run: true,
  mp_app_id: '',
  oa_app_id: '',
  mch_id: '',
  mch_serial_no: '',
  notify_url: '',
  h5_return_url: '',
  mp_app_secret: '',
  oa_app_secret: '',
  api_v3_key: '',
  mch_private_key: '',
})
const meta = reactive({
  source: 'env',
  mp_app_secret: false,
  oa_app_secret: false,
  api_v3_key: false,
  mch_private_key: false,
})

async function load() {
  loading.value = true
  try {
    const { data } = await http.get<Settings>('/site/payment-settings')
    form.mode = data.mode === 'jdpay' ? 'wechat' : data.mode
    form.dry_run = data.dry_run
    form.mp_app_id = data.mp_app_id || ''
    form.oa_app_id = data.oa_app_id || ''
    form.mch_id = data.mch_id || ''
    form.mch_serial_no = data.mch_serial_no || ''
    form.notify_url = data.notify_url || ''
    form.h5_return_url = data.h5_return_url || ''
    form.mp_app_secret = ''
    form.oa_app_secret = ''
    form.api_v3_key = ''
    form.mch_private_key = ''
    meta.source = data.source
    meta.mp_app_secret = !!data.mp_app_secret?.configured
    meta.oa_app_secret = !!data.oa_app_secret?.configured
    meta.api_v3_key = !!data.api_v3_key?.configured
    meta.mch_private_key = !!data.mch_private_key?.configured
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '加载失败')
  } finally {
    loading.value = false
  }
}

async function save() {
  saving.value = true
  try {
    const payload: Record<string, unknown> = {
      mode: form.mode,
      dry_run: form.dry_run,
      mp_app_id: form.mp_app_id,
      oa_app_id: form.oa_app_id,
      mch_id: form.mch_id,
      mch_serial_no: form.mch_serial_no,
      notify_url: form.notify_url,
      h5_return_url: form.h5_return_url,
    }
    if (form.mp_app_secret) payload.mp_app_secret = form.mp_app_secret
    if (form.oa_app_secret) payload.oa_app_secret = form.oa_app_secret
    if (form.api_v3_key) payload.api_v3_key = form.api_v3_key
    if (form.mch_private_key) payload.mch_private_key = form.mch_private_key
    await http.put('/site/payment-settings', payload)
    ElMessage.success('已保存')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '保存失败')
  } finally {
    saving.value = false
  }
}

async function importEnv() {
  saving.value = true
  try {
    await http.post('/site/payment-settings/import-env')
    ElMessage.success('已从环境变量导入')
    await load()
  } catch (e: unknown) {
    ElMessage.error(e instanceof Error ? e.message : '导入失败')
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<template>
  <div class="pay-page" v-loading="loading">
    <div class="toolbar">
      <div>
        <h3>微信支付</h3>
        <p class="lead">全场地共用一套商户号（APIv3）。密钥只写入不回显，已保存的项留空即保持不变。</p>
      </div>
      <div class="actions">
        <el-tag :type="meta.source === 'db' ? 'success' : 'info'" effect="plain" size="small">
          {{ meta.source === 'db' ? '生效：数据库' : '生效：环境变量兜底' }}
        </el-tag>
        <el-button @click="importEnv" :loading="saving">从环境变量导入</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </div>
    </div>

    <el-form label-position="top" class="pay-form">
      <el-card shadow="never" class="panel">
        <template #header>
          <div class="panel-head">
            <span class="panel-title">支付方式</span>
          </div>
        </template>
        <div class="field-grid">
          <el-form-item label="模式">
            <el-select v-model="form.mode" style="width: 100%">
              <el-option label="未配置" value="unconfigured" />
              <el-option label="模拟支付" value="mock" />
              <el-option label="微信支付" value="wechat" />
            </el-select>
          </el-form-item>
          <el-form-item label="下单">
            <el-radio-group v-model="form.dry_run">
              <el-radio-button :value="true">干跑（不调微信）</el-radio-button>
              <el-radio-button :value="false">真实下单</el-radio-button>
            </el-radio-group>
            <p class="field-hint">联调先用干跑；确认凭证无误后再切真实下单。</p>
          </el-form-item>
        </div>
      </el-card>

      <el-card shadow="never" class="panel">
        <template #header>
          <div class="panel-head">
            <span class="panel-title">小程序</span>
            <span class="panel-sub">会员端收款主路径</span>
          </div>
        </template>
        <div class="field-grid">
          <el-form-item label="AppID">
            <el-input v-model="form.mp_app_id" placeholder="wx 开头，开发管理里复制" />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="label-with-tag">
                Secret
                <el-tag :type="meta.mp_app_secret ? 'success' : 'info'" effect="plain" size="small">
                  {{ meta.mp_app_secret ? '已配置' : '未配置' }}
                </el-tag>
              </span>
            </template>
            <el-input v-model="form.mp_app_secret" type="password" show-password placeholder="留空不修改" />
          </el-form-item>
        </div>
      </el-card>

      <el-card shadow="never" class="panel">
        <template #header>
          <div class="panel-head">
            <span class="panel-title">微信商户</span>
            <span class="panel-sub">pay.weixin.qq.com · 账户中心 / API 安全</span>
          </div>
        </template>
        <div class="field-grid">
          <el-form-item label="商户号">
            <el-input v-model="form.mch_id" placeholder="10 位数字 mch_id" />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="label-with-tag">
                APIv3 密钥
                <el-tag :type="meta.api_v3_key ? 'success' : 'info'" effect="plain" size="small">
                  {{ meta.api_v3_key ? '已配置' : '未配置' }}
                </el-tag>
              </span>
            </template>
            <el-input v-model="form.api_v3_key" type="password" show-password placeholder="32 位，留空不修改" />
          </el-form-item>
          <el-form-item label="证书序列号">
            <el-input v-model="form.mch_serial_no" placeholder="API 证书页复制" />
          </el-form-item>
          <el-form-item class="field-span">
            <template #label>
              <span class="label-with-tag">
                商户私钥
                <el-tag :type="meta.mch_private_key ? 'success' : 'info'" effect="plain" size="small">
                  {{ meta.mch_private_key ? '已配置' : '未配置' }}
                </el-tag>
              </span>
            </template>
            <el-input
              v-model="form.mch_private_key"
              type="textarea"
              :rows="4"
              class="pem-input"
              placeholder="粘贴 apiclient_key.pem 全文（含 BEGIN/END），已配置则留空"
            />
          </el-form-item>
        </div>
      </el-card>

      <el-card shadow="never" class="panel">
        <template #header>
          <div class="panel-head">
            <span class="panel-title">回调地址</span>
          </div>
        </template>
        <div class="field-grid">
          <el-form-item label="支付回调 URL">
            <el-input v-model="form.notify_url" placeholder="https://api.你的域名/api/v1/payments/wechat/notify" />
          </el-form-item>
          <el-form-item label="H5 回跳">
            <el-input v-model="form.h5_return_url" placeholder="会员 H5 根地址，如 https://m.你的域名" />
          </el-form-item>
        </div>
      </el-card>

      <el-card shadow="never" class="panel panel-optional">
        <template #header>
          <div class="panel-head">
            <span class="panel-title">公众号 / 微信内 H5</span>
            <el-tag type="info" effect="plain" size="small">可选</el-tag>
          </div>
        </template>
        <p class="panel-note">只做小程序支付可空着。以后要在微信里打开会员 H5 并付款，再填已认证服务号的 AppID。</p>
        <div class="field-grid">
          <el-form-item label="AppID">
            <el-input v-model="form.oa_app_id" placeholder="服务号 AppID，可与小程序不同" />
          </el-form-item>
          <el-form-item>
            <template #label>
              <span class="label-with-tag">
                Secret
                <el-tag :type="meta.oa_app_secret ? 'success' : 'info'" effect="plain" size="small">
                  {{ meta.oa_app_secret ? '已配置' : '未配置' }}
                </el-tag>
              </span>
            </template>
            <el-input v-model="form.oa_app_secret" type="password" show-password placeholder="留空不修改" />
          </el-form-item>
        </div>
      </el-card>
    </el-form>
  </div>
</template>

<style scoped>
.pay-page {
  max-width: 880px;
}
.toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
.toolbar h3 {
  margin: 0 0 6px;
  font-size: 1.1rem;
}
.lead {
  margin: 0;
  max-width: 520px;
  font-size: 13px;
  line-height: 1.55;
  color: var(--admin-ink-muted);
}
.actions {
  display: flex;
  flex-shrink: 0;
  flex-wrap: wrap;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
}
.pay-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.panel {
  margin: 0;
}
.panel :deep(.el-card__header) {
  padding: 12px 18px;
}
.panel :deep(.el-card__body) {
  padding: 16px 18px 8px;
}
.panel :deep(.el-form-item) {
  margin-bottom: 14px;
}
.panel :deep(.el-form-item__label) {
  margin-bottom: 4px;
  line-height: 1.4;
}
.panel-head {
  display: flex;
  align-items: center;
  gap: 10px;
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--admin-ink);
}
.panel-sub {
  font-size: 12px;
  font-weight: 400;
  color: var(--admin-ink-muted);
}
.panel-note {
  margin: 0 0 12px;
  font-size: 13px;
  line-height: 1.5;
  color: var(--admin-ink-muted);
}
.panel-optional {
  opacity: 0.96;
}
.field-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 20px;
}
.field-span {
  grid-column: 1 / -1;
}
.field-hint {
  margin: 8px 0 0;
  font-size: 12px;
  line-height: 1.45;
  color: var(--admin-ink-muted);
}
.label-with-tag {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}
.pem-input :deep(textarea) {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 720px) {
  .toolbar {
    flex-direction: column;
  }
  .actions {
    justify-content: flex-start;
  }
  .field-grid {
    grid-template-columns: 1fr;
  }
}
</style>
