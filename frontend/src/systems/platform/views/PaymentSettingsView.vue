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
    form.mode = data.mode
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
  <div v-loading="loading">
    <div class="toolbar">
      <h3>京东支付</h3>
      <div class="actions">
        <el-button @click="importEnv" :loading="saving">从环境变量导入</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </div>
    </div>
    <el-alert
      type="info"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
      title="全场地共用一套京东支付商户号。密钥仅写入不回显；留空表示不修改已保存密钥。"
      :description="`当前生效来源：${meta.source === 'db' ? '数据库' : '环境变量兜底'}`"
    />

    <el-form label-width="140px" style="max-width: 720px">
      <el-form-item label="支付模式">
        <el-select v-model="form.mode" style="width: 240px">
          <el-option label="未配置" value="unconfigured" />
          <el-option label="模拟支付" value="mock" />
          <el-option label="京东支付" value="jdpay" />
          <el-option label="京东支付（兼容 wechat）" value="wechat" />
        </el-select>
      </el-form-item>
      <el-form-item label="DRY_RUN">
        <el-switch v-model="form.dry_run" active-text="干跑（不调京东）" inactive-text="真实下单" />
      </el-form-item>
      <el-form-item label="小程序 AppID">
        <el-input v-model="form.mp_app_id" />
      </el-form-item>
      <el-form-item :label="`小程序 Secret${meta.mp_app_secret ? '（已配置）' : ''}`">
        <el-input v-model="form.mp_app_secret" type="password" show-password placeholder="留空不修改" />
      </el-form-item>
      <el-form-item label="公众号 AppID">
        <el-input v-model="form.oa_app_id" placeholder="H5 微信内 OAuth，可与小程序不同" />
      </el-form-item>
      <el-form-item :label="`公众号 Secret${meta.oa_app_secret ? '（已配置）' : ''}`">
        <el-input v-model="form.oa_app_secret" type="password" show-password placeholder="留空不修改" />
      </el-form-item>
      <el-form-item label="商户号">
        <el-input v-model="form.mch_id" />
      </el-form-item>
      <el-form-item :label="`APIv3 密钥${meta.api_v3_key ? '（已配置）' : ''}`">
        <el-input v-model="form.api_v3_key" type="password" show-password placeholder="留空不修改" />
      </el-form-item>
      <el-form-item label="证书序列号">
        <el-input v-model="form.mch_serial_no" />
      </el-form-item>
      <el-form-item :label="`商户私钥 PEM${meta.mch_private_key ? '（已配置）' : ''}`">
        <el-input
          v-model="form.mch_private_key"
          type="textarea"
          :rows="5"
          placeholder="-----BEGIN PRIVATE KEY----- … 留空不修改"
        />
      </el-form-item>
      <el-form-item label="支付回调 URL">
        <el-input v-model="form.notify_url" placeholder="https://你的域名/api/v1/payments/wechat/notify" />
      </el-form-item>
      <el-form-item label="H5 回跳">
        <el-input v-model="form.h5_return_url" placeholder="会员 H5 根地址或订单页" />
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.toolbar h3 {
  margin: 0;
}
.actions {
  display: flex;
  gap: 8px;
}
</style>
