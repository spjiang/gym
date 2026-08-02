## 1. 模型与迁移

- [x] 1.1 新增 `models/retail.py` 并导出
- [x] 1.2 Alembic `20260802_0004_retail.py`

## 2. 权限

- [x] 2.1 seed 合并 retail 权限到商户管理员与前台

## 3. 库存与履约服务

- [x] 3.1 `services/retail_stock.py`：入出库盘点、非负、流水
- [x] 3.2 `services/retail_fulfillment.py`：支付前校验、扣减、退款回补
- [x] 3.3 commerce 支付/退款钩子接入

## 4. API 与测试

- [x] 4.1 `api/retail.py`：分类/SKU/库存/流水/零售下单
- [x] 4.2 测试：入库出库盘点、低库存、售卖扣减、超卖拒付、退款回补

## 5. 前端

- [x] 5.1 路由菜单 `/retail`
- [x] 5.2 SKU/库存/预警/收银页面

## 6. 验收

- [x] 6.1 pytest 全绿
- [x] 6.2 回写 PRD §10
