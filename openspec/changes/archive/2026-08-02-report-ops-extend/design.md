## Context

批准设计见 `docs/superpowers/specs/2026-08-02-report-ops-extend-design.md`。

## Decisions

- 会籍新开/续费：区间内已履约的 `MembershipOrderLink`（`fulfilled_membership_id` 非空）按 `action` 计数
- 在籍/停卡：当前快照（非区间）；到期：`ends_at` 落在区间且状态非 void
- 团课：场次 `starts_at` 落在区间；预约含 booked/attended/no_show；满课=预约占用≥capacity；出勤=attended
- 私教核销：审计 `pt.consume` 在区间内计数（无独立核销流水表）
- 销量：区间内 `StockMovement` type=sale 的 `-quantity_delta` 合计；库存读 `RetailSku`

## Risks

- 私教核销依赖审计日志；若审计被裁剪会失真（一期可接受）
