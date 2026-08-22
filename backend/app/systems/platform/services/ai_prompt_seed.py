"""内置 AI 提示词模版种子。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.systems.platform.models.ai_analysis import AiPromptTemplate

# 通用系统角色说明
_COMMON_SYSTEM = """你是回龙观公园综合经营场地（健身房、酒吧、招商商户）的管理分析助手。
请基于提供的结构化业务数据进行分析，输出使用简体中文 Markdown。
要求：结论先行；区分事实与推断；给出可执行建议；敏感个人信息做脱敏；无数据时明确说明。"""

BUILTIN_TEMPLATES: list[dict] = [
    {
        "code": "ops_overview",
        "name": "综合运营分析",
        "category": "运营",
        "data_source": "operations",
        "sort_order": 10,
        "description": "跨商户会员、订单、审计日志的综合经营诊断",
        "system_prompt": _COMMON_SYSTEM
        + "\n侧重：整体经营健康度、各业态协同、短期风险与机会。",
        "user_prompt_template": """请对 {{merchant_name}} 在 {{date_from}} 至 {{date_to}} 期间的经营情况进行综合分析。

## 业务数据
{{data}}

## 输出结构
1. **核心结论**（3-5 条）
2. **经营亮点**
3. **风险与异常**
4. **分业态建议**（健身房 / 餐饮酒吧 / 平台运营）
5. **下周行动清单**""",
    },
    {
        "code": "audit_log_review",
        "name": "操作日志分析",
        "category": "运维",
        "data_source": "audit_logs",
        "sort_order": 20,
        "description": "分析管理后台、H5、小程序、设备端的操作日志与异常",
        "system_prompt": _COMMON_SYSTEM
        + "\n侧重：操作追溯、权限与合规、失败请求、异常行为模式。",
        "user_prompt_template": """请分析 {{merchant_name}} 在 {{date_from}} 至 {{date_to}} 的操作日志。

## 日志数据
{{data}}

## 输出结构
1. **操作概览**（总量、失败率、主要客户端分布）
2. **高频操作 TOP10** 及业务含义
3. **失败/异常操作** 清单与可能原因
4. **安全风险**（越权嫌疑、批量操作、敏感变更）
5. **运维建议**（审计策略、告警规则）""",
    },
    {
        "code": "member_growth",
        "name": "会员增长与留存",
        "category": "会员",
        "data_source": "members",
        "sort_order": 30,
        "description": "会员规模、新增、人脸/密码开通情况分析",
        "system_prompt": _COMMON_SYSTEM + "\n侧重：获客、激活、留存与会员结构。",
        "user_prompt_template": """请分析 {{merchant_name}} 在 {{date_from}} 至 {{date_to}} 的会员数据。

## 会员数据
{{data}}

## 输出结构
1. **会员规模与结构**
2. **新增与激活**（人脸、密码）
3. **潜在流失信号**
4. **运营活动建议**
5. **需跟进会员群体**""",
    },
    {
        "code": "order_revenue",
        "name": "订单与收款分析",
        "category": "财务",
        "data_source": "orders",
        "sort_order": 40,
        "description": "订单量、收款金额、状态分布与异常订单",
        "system_prompt": _COMMON_SYSTEM + "\n侧重：收入、转化、退款风险、订单结构。",
        "user_prompt_template": """请分析 {{merchant_name}} 在 {{date_from}} 至 {{date_to}} 的订单与收款。

## 订单数据
{{data}}

## 输出结构
1. **收款概览**
2. **订单类型/状态分布**
3. **异常与待跟进订单**
4. **同比/环比推断**（若数据不足请说明）
5. **提升转化建议**""",
    },
    {
        "code": "promotion_funnel",
        "name": "推广与返点分析",
        "category": "推广",
        "data_source": "promotion",
        "sort_order": 50,
        "description": "推广码访问、渠道效果与返点体系优化",
        "system_prompt": _COMMON_SYSTEM + "\n侧重：推广转化、渠道 ROI、返点规则优化。",
        "user_prompt_template": """请分析 {{merchant_name}} 的推广与返点相关数据（统计区间 {{date_from}} ~ {{date_to}}）。

## 推广数据
{{data}}

## 输出结构
1. **推广位概览**
2. **高访问推广码 TOP 榜** 及解读
3. **低效/停用推广位**
4. **返点与分成优化建议**
5. **下阶段投放策略**""",
    },
    {
        "code": "access_traffic",
        "name": "门禁通行分析",
        "category": "门禁",
        "data_source": "access",
        "sort_order": 60,
        "description": "通行成功率、拒访原因与高峰时段",
        "system_prompt": _COMMON_SYSTEM + "\n侧重：通行效率、设备异常、会员体验。",
        "user_prompt_template": """请分析 {{merchant_name}} 在 {{date_from}} 至 {{date_to}} 的门禁通行数据。

## 通行数据
{{data}}

## 输出结构
1. **通行概览**（总量、通过率、拒访率）
2. **拒访原因分布**
3. **高峰时段推断**
4. **设备/授权问题排查建议**
5. **会员体验改进点**""",
    },
    {
        "code": "membership_health",
        "name": "会籍健康度分析",
        "category": "健身房",
        "data_source": "membership",
        "sort_order": 70,
        "description": "会籍开通、到期、活跃与续费风险",
        "system_prompt": _COMMON_SYSTEM + "\n侧重：健身房会籍销售与续费。",
        "user_prompt_template": """请分析 {{merchant_name}} 在 {{date_from}} 至 {{date_to}} 的会籍数据。

## 会籍数据
{{data}}

## 输出结构
1. **会籍概览**
2. **新开/在籍/即将到期**
3. **续费风险会员特征**
4. **产品组合建议**
5. **销售跟进优先级**""",
    },
    {
        "code": "catering_ops",
        "name": "餐饮经营分析",
        "category": "餐饮",
        "data_source": "catering",
        "sort_order": 80,
        "description": "餐饮订单量、客单价与吧台运营建议",
        "system_prompt": _COMMON_SYSTEM + "\n侧重：餐饮/bar 业态点单、出餐、时段运营。",
        "user_prompt_template": """请分析 {{merchant_name}} 在 {{date_from}} 至 {{date_to}} 的餐饮经营数据。

## 餐饮订单数据
{{data}}

## 输出结构
1. **餐饮营收概览**
2. **订单时段/品类推断**
3. **运营瓶颈**
4. **吧台与厨房协同建议**
5. **促销与套餐建议**""",
    },
    {
        "code": "risk_compliance",
        "name": "风险与合规巡检",
        "category": "运维",
        "data_source": "audit_logs",
        "sort_order": 90,
        "description": "基于操作日志的权限变更、敏感操作合规检查",
        "system_prompt": _COMMON_SYSTEM
        + "\n侧重：合规、内控、权限滥用、数据安全；对可疑操作保持审慎。",
        "user_prompt_template": """请以合规审计视角，检查 {{merchant_name}} 在 {{date_from}} 至 {{date_to}} 的操作日志。

## 日志数据
{{data}}

## 输出结构
1. **合规总体评价**
2. **敏感操作清单**（删改、权限、支付、会员隐私）
3. **疑似违规/越权模式**
4. **需人工复核项**
5. **制度与流程改进建议**""",
    },
    {
        "code": "weekly_ops_brief",
        "name": "周报运营简报",
        "category": "运营",
        "data_source": "operations",
        "sort_order": 15,
        "description": "适合管理层的 weekly 一页纸经营简报",
        "system_prompt": _COMMON_SYSTEM + "\n输出应简洁，适合管理层快速阅读，控制在 800 字以内。",
        "user_prompt_template": """请为 {{merchant_name}} 生成 {{date_from}} 至 {{date_to}} 的运营周报简报。

## 数据
{{data}}

## 输出结构
- **本周一句话总结**
- **关键指标**（会员/订单/收款/日志）
- **三件好事 / 三个问题**
- **下周重点三件事**""",
    },
]


def seed_ai_prompt_templates(db: Session, site_id: int) -> None:
    """为场地写入内置提示词模版（已存在则跳过）。"""
    for item in BUILTIN_TEMPLATES:
        exists = db.scalar(
            select(AiPromptTemplate.id).where(
                AiPromptTemplate.site_id == site_id,
                AiPromptTemplate.code == item["code"],
            )
        )
        if exists is not None:
            continue
        db.add(
            AiPromptTemplate(
                site_id=site_id,
                code=item["code"],
                name=item["name"],
                category=item["category"],
                data_source=item["data_source"],
                system_prompt=item["system_prompt"],
                user_prompt_template=item["user_prompt_template"],
                description=item.get("description"),
                is_builtin=True,
                is_active=True,
                sort_order=item.get("sort_order", 100),
            )
        )
