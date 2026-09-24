"""平台版权主体：对外展示、页脚与协议落款。"""

COPYRIGHT_OWNER = "北京晨曦坤泽科技有限公司"


def copyright_notice() -> str:
    return (
        f"本服务由{COPYRIGHT_OWNER}运营。"
        f"观野SPACE 及相关软件、页面与内容之版权归{COPYRIGHT_OWNER}所有。"
    )


def copyright_line(year: int | None = None) -> str:
    from datetime import datetime

    y = year or datetime.now().year
    return f"© {y} {COPYRIGHT_OWNER}"
