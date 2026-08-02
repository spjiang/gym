## 1. 模型与迁移

- [x] 1.1 新增 `backend/app/models/course.py`（Coach / Pt* / Group*）并在 `models/__init__.py` 导出
- [x] 1.2 新增 Alembic `20260802_0003_course.py`，升级可应用

## 2. 权限种子

- [x] 2.1 在 `seed.py` 为商户管理员/前台/教练合并 `coach:manage`、`course:manage`、`course:book`、`course:checkin`、`pt:sell`

## 3. 私教履约与核销

- [x] 3.1 实现 `services/pt_fulfillment.py`，支付成功钩子处理 `pt_package`
- [x] 3.2 API：课包商品 CRUD、purchase 下单、consume 核销；写审计
- [x] 3.3 测试：支付后得课包、核销扣次、无课时拒绝

## 4. 教练与团课排课

- [x] 4.1 API：教练 CRUD/启停；停用不可排新场
- [x] 4.2 API：团课模板、场次创建、改派教练；写审计
- [x] 4.3 测试：创建教练与场次、停用拒绝排场、改派

## 5. 代约 / 取消 / 签到

- [x] 5.1 实现 `services/course_booking.py`（会籍校验、满员行锁、取消释放）
- [x] 5.2 API：代约、取消、签到（不扣会籍次数）；教练数据范围过滤
- [x] 5.3 测试：有会籍可约、无会籍拒绝、满员拒绝、取消后再约、签到、教练范围

## 6. 前端

- [x] 6.1 路由与菜单：教练、私教课包、团课、教练工作台
- [x] 6.2 页面：列表/表单、售课引导支付、代约取消签到、核销

## 7. 验收

- [x] 7.1 `pytest` 全绿；主路径冒烟通过
- [x] 7.2（归档后）回写 PRD §10 私教/团课为 ✅
