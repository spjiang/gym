"""餐饮管理系统 — 能力注册。"""

SYSTEM = {
    "code": "catering",
    "name": "观野BAR",
    "description": "酒吧菜单维护、点单下单与收款退款闭环。",
    "is_business": True,
    "sort_order": 30,
    "permissions": [
        {"code": "system:catering", "name": "进入观野BAR"},
        {"code": "catering:menu", "name": "餐饮菜单维护"},
        {"code": "catering:order", "name": "餐饮点单收款"},
    ],
    "menus": [
        {
            "code": "catering.menu",
            "path": "/catering/menu",
            "name": "餐饮菜单",
            "required_any": ["catering:menu", "*"],
            "sort_order": 10,
        },
        {
            "code": "catering.orders",
            "path": "/catering/orders",
            "name": "点单收款",
            "required_any": ["catering:order", "*"],
            "sort_order": 20,
        },
    ],
}
