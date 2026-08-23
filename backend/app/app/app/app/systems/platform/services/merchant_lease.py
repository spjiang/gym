"""商户租赁有效期：剩余天数与进度。"""

from datetime import date

# 剩余不超过该天数视为即将到期
LEASE_EXPIRING_DAYS = 30


def lease_metrics(
    starts_on: date | None,
    ends_on: date | None,
    *,
    today: date | None = None,
) -> dict:
    """根据起止日计算剩余天数、剩余占比与状态。"""
    today = today or date.today()
    if starts_on is None and ends_on is None:
        return {
            "lease_days_total": None,
            "lease_days_remaining": None,
            "lease_progress": None,
            "lease_state": "unset",
        }

    remaining = (ends_on - today).days if ends_on else None
    total = (ends_on - starts_on).days if starts_on and ends_on else None
    if total is not None and total < 0:
        total = 0

    progress: int | None = None
    if total is not None and remaining is not None:
        if total == 0:
            progress = 0 if remaining <= 0 else 100
        else:
            progress = int(round(max(0, min(100, remaining / total * 100))))

    if ends_on is not None and remaining is not None and remaining < 0:
        state = "expired"
    elif starts_on is not None and today < starts_on:
        state = "not_started"
    elif remaining is not None and remaining <= LEASE_EXPIRING_DAYS:
        state = "expiring"
    else:
        state = "active"

    return {
        "lease_days_total": total,
        "lease_days_remaining": remaining,
        "lease_progress": progress,
        "lease_state": state,
    }
