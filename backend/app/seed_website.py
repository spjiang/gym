"""官网 Demo：主视觉/品牌图进 MinIO，并写入可运营的饱满文案与文章。"""

from __future__ import annotations

import hashlib
import struct
import zlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.core.copyright import COPYRIGHT_OWNER
from app.core.object_store import PUBLIC_BUCKET, ensure_buckets, put_bytes
from app.core.upload_urls import public_object_url
from app.systems.platform.models.org import Site
from app.systems.platform.models.website import WebsiteArticle
from app.systems.platform.services.website import get_or_create_settings, mark_published

ASSETS_DIR = Path(__file__).resolve().parent / "seed_assets" / "website"
_CONTENT_TYPE = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


def _asset_path(stem: str) -> Path | None:
    for ext in (".jpg", ".jpeg", ".webp", ".png"):
        path = ASSETS_DIR / f"{stem}{ext}"
        if path.is_file():
            return path
    return None


def _object_name(stem: str) -> str:
    path = _asset_path(stem)
    ext = (path.suffix.lower() if path else ".png")
    if ext == ".jpeg":
        ext = ".jpg"
    return hashlib.md5(f"gym-website-demo:{stem}".encode("utf-8")).hexdigest() + ext


def _png_chunk(tag: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)


def _poster_png(
    width: int,
    height: int,
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
    accent: tuple[int, int, int],
    seed: int,
) -> bytes:
    """海报风主视觉：渐变、地平线、块面与颗粒，避免纯色空板。"""
    raw = bytearray()
    horizon = int(height * 0.62)
    for y in range(height):
        t = y / max(height - 1, 1)
        shade = 1.0 - 0.42 * (t**1.25)
        r = int((top[0] * (1 - t) + bottom[0] * t) * shade)
        g = int((top[1] * (1 - t) + bottom[1] * t) * shade)
        b = int((top[2] * (1 - t) + bottom[2] * t) * shade)
        if abs(y - horizon) < 18:
            mix = 1.0 - abs(y - horizon) / 18
            r = int(r * (1 - mix * 0.35) + accent[0] * mix * 0.35)
            g = int(g * (1 - mix * 0.35) + accent[1] * mix * 0.35)
            b = int(b * (1 - mix * 0.35) + accent[2] * mix * 0.35)
        raw.append(0)
        for x in range(width):
            n = ((x * 374761 + y * 668265 + seed) & 255) % 19
            vx = abs(x / max(width - 1, 1) - 0.5) * 2
            vy = abs(y / max(height - 1, 1) - 0.45)
            vig = max(0.55, 1.0 - (vx * vx + vy * vy) * 0.45)
            block = 0
            if y > horizon:
                col = (x + seed * 13) % 220
                if 40 < col < 88 or 130 < col < 168:
                    h = 28 + (seed + x) % 70
                    if y > height - h:
                        block = 22
            pr = min(255, int((r + n - 6 + block) * vig))
            pg = min(255, int((g + n - 6 + block // 2) * vig))
            pb = min(255, int((b + n - 6) * vig))
            raw.extend((pr, pg, pb))
    compressed = zlib.compress(bytes(raw), 6)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + _png_chunk(b"IDAT", compressed)
        + _png_chunk(b"IEND", b"")
    )


SCENES: dict[str, tuple[tuple[int, int, int], tuple[int, int, int], tuple[int, int, int]]] = {
    "hero": ((38, 46, 58), (232, 122, 46), (243, 107, 33)),
    "space": ((46, 78, 68), (196, 168, 92), (20, 184, 212)),
    "fit": ((24, 58, 92), (72, 168, 196), (20, 184, 212)),
    "bar": ((22, 18, 26), (168, 72, 48), (243, 107, 33)),
    "space_g1": ((58, 96, 78), (148, 156, 128), (196, 168, 92)),
    "space_g2": ((36, 52, 48), (120, 132, 108), (243, 107, 33)),
    "space_g3": ((72, 88, 70), (210, 186, 120), (20, 184, 212)),
    "fit_g1": ((32, 74, 112), (120, 196, 180), (20, 184, 212)),
    "fit_g2": ((18, 44, 72), (88, 140, 168), (243, 107, 33)),
    "fit_g3": ((40, 90, 120), (160, 210, 196), (72, 168, 196)),
    "bar_g1": ((18, 16, 22), (128, 52, 68), (243, 107, 33)),
    "bar_g2": ((28, 22, 30), (96, 40, 48), (168, 72, 48)),
    "bar_g3": ((14, 16, 22), (80, 64, 72), (20, 184, 212)),
    "news": ((36, 44, 58), (92, 108, 140), (20, 184, 212)),
    "news2": ((48, 56, 50), (160, 140, 88), (243, 107, 33)),
    "jobs": ((48, 52, 46), (180, 140, 72), (243, 107, 33)),
    "partners": ((40, 40, 48), (160, 112, 72), (243, 107, 33)),
    "logo": ((23, 26, 32), (232, 122, 46), (243, 107, 33)),
}


def _scene_payload(stem: str) -> tuple[bytes, str]:
    path = _asset_path(stem)
    if path is not None:
        ext = ".jpg" if path.suffix.lower() == ".jpeg" else path.suffix.lower()
        return path.read_bytes(), _CONTENT_TYPE[ext]
    top, bottom, accent = SCENES[stem]
    size = (128, 128) if stem == "logo" else (480, 270)
    seed = int(hashlib.md5(stem.encode()).hexdigest()[:8], 16)
    return _poster_png(size[0], size[1], top, bottom, accent, seed), "image/png"


def upload_scene(stem: str) -> str:
    name = _object_name(stem)
    data, content_type = _scene_payload(stem)
    put_bytes(PUBLIC_BUCKET, name, data, content_type)
    return public_object_url(name)


def _upsert_article(
    db: Session,
    *,
    site_id: int,
    channel: str,
    title: str,
    summary: str,
    body: str,
    cover: str,
    contact_hint: str | None,
    sort_order: int,
) -> None:
    row = db.scalar(
        select(WebsiteArticle).where(
            WebsiteArticle.site_id == site_id,
            WebsiteArticle.channel == channel,
            WebsiteArticle.title == title,
        )
    )
    if row is not None:
        return
    row = WebsiteArticle(
        site_id=site_id,
        channel=channel,
        title=title,
        status="draft",
        summary=summary,
        cover_image_url=cover,
        body=body,
        contact_hint=contact_hint,
        sort_order=sort_order,
    )
    db.add(row)
    mark_published(row)


SPACE_BODY = """观野SPACE 是回龙观公园综合场地的公共客厅。白天是训练与散步的过路点，傍晚是社区活动，夜里把人送到 BAR。我们把健身房、清吧和户外场地放在同一座园子里，方便邻居下班后来训练、吃饭、偶遇朋友。

## 一座园子，三种节奏

不必在城市里来回切换场景。你可以先在 FIT 练完一组力量，穿过中庭到 SPACE 坐一会儿，再决定是回家还是留下喝一杯。园区对邻居开放，会员体系打通办卡、约课、点餐与门禁。

## 空间怎么用

- **中庭与草坪**：市集、体验课、社区集合，雨天改室内。
- **连廊与座椅**：训练间隙休息，不等待成「排队」。
- **通往 FIT / BAR**：步行可达，夜灯把动线连起来。

## 适合谁来

第一次走进健身房的人、已经有训练习惯的邻居、只想来公园坐坐的人，以及需要包场办小型活动的团队。我们不把这里做成景区打卡点，更在意你下周还愿不愿意再来。

## 怎么到店

地址见页脚。建议地铁或骑行，机动车请按公园停车指引。到店后可先到前台问当日课表与 BAR 是否有驻场。办卡、约课、看菜单请走会员中心或微信小程序「观野SPACE」。
"""

FIT_BODY = """观野FIT 面向想稳定训练的邻居，也欢迎第一次走进健身房的人。力量区、有氧、团课与私教在同一屋檐下；办卡、预约、门禁走同一套会员体系，不用在多个小程序之间来回跳。

## 训练空间

力量区以自由重量和固定器械为主，地面做减震，高峰时段仍能找到一组架子。有氧区靠窗，傍晚能看见公园树影。更衣与淋浴按日常场馆标准配置，请自备锁和拖鞋。

## 团课与私教

循环训练、瑜伽、基础力量入门是常驻课种。课表在会员中心查看，可提前预约。私教按教练排期，体验课请先到前台或会籍顾问处登记，不要直接占用器械区做一对一。

## 办卡与门禁

卡种、有效期和请假规则以会员中心展示为准。入会后面准入场，请保持人脸采集清晰。临访请走前台登记，不要尾随进门。

## 开放习惯

建议工作日清晨或午后错峰。周末上午常有体验课占用草坪，室内力量区照常。身体不适请停止训练并告知当值教练。
"""

BAR_BODY = """观野BAR 是训练之后的夜生活：简餐、特调、驻场与包场。灯光偏暗，座位有吧台与卡座。可到店扫桌码点餐，也可先在会员端看菜单。请适量饮酒，未成年人谢绝酒水。

## 吃什么、喝什么

简餐走快手热菜和分享小食，适合练完后不想再出门找饭店的人。特调按季节更换，不含酒精的选项会单独标注。过敏原请向吧台确认，不要自行假设「都能做」。

## 驻场与包场

周末晚间常有驻唱或小编制演出，以当场通知和新闻公告为准。生日、团建、品牌快闪可谈包场，档期要提前到店沟通，官网不收集意向表。

## 入场提醒

请携带有效证件。酒后请勿驾车。外带食品请先问吧台。高峰请等位，不要占座空桌。

## 和 FIT 的关系

可以先训练再过来，不必换另一套会员身份。点餐账号与会员中心打通。BAR 打烊后请从园区主路离开，保持公园安静。
"""


def seed_official_website(db: Session, *, site: Site) -> None:
    """补齐官网演示内容。已有配置或同标题文章不覆盖，避免重启冲掉运营修改。"""
    ensure_buckets()
    urls = {stem: upload_scene(stem) for stem in SCENES}
    member_url = (get_settings().member_web_public_url or "http://localhost:8081").rstrip("/")
    row = get_or_create_settings(db, site.id, staff_id=None)
    already = bool(row.home_json or row.site_json or row.brands_json)
    if not already:
        row.site_json = {
            "display_name": "观野SPACE",
            "seo_title": "观野SPACE · 回龙观公园 · 健身 / 清吧 / 社区",
            "seo_description": "回龙观公园综合场地：观野FIT 训练、观野BAR 夜生活、SPACE 社区客厅。办卡约课点餐请到会员中心。",
            "logo_url": urls["logo"],
            "member_web_url": member_url,
            "miniprogram_hint": "微信搜索「观野SPACE」进入会员小程序",
            "footer_note": f"回龙观公园综合经营场地 · 版权所有 {COPYRIGHT_OWNER}",
            "icp_beian": None,
        }
        row.home_json = {
            "hero_image_url": urls["hero"],
            "headline": "在回龙观，遇见运动与夜色",
            "subheadline": "SPORTS · EVENTS · COMMUNITY",
            "show_space": True,
            "show_fit": True,
            "show_bar": True,
        }
        row.brands_json = {
            "space": {
                "title": "观野SPACE",
                "cover_image_url": urls["space"],
                "body": SPACE_BODY.strip(),
                "gallery_image_urls": [
                    urls["space"],
                    urls["space_g1"],
                    urls["space_g2"],
                    urls["space_g3"],
                    urls["hero"],
                    urls["fit"],
                ],
                "cta_label": "进入会员中心",
                "cta_url": member_url,
            },
            "fit": {
                "title": "观野FIT",
                "cover_image_url": urls["fit"],
                "body": FIT_BODY.strip(),
                "gallery_image_urls": [
                    urls["fit"],
                    urls["fit_g1"],
                    urls["fit_g2"],
                    urls["fit_g3"],
                    urls["space"],
                    urls["jobs"],
                ],
                "cta_label": "去办卡 / 约课",
                "cta_url": member_url,
            },
            "bar": {
                "title": "观野BAR",
                "cover_image_url": urls["bar"],
                "body": BAR_BODY.strip(),
                "gallery_image_urls": [
                    urls["bar"],
                    urls["bar_g1"],
                    urls["bar_g2"],
                    urls["bar_g3"],
                    urls["hero"],
                    urls["partners"],
                ],
                "cta_label": "查看菜单",
                "cta_url": member_url,
            },
        }
        flag_modified(row, "site_json")
        flag_modified(row, "home_json")
        flag_modified(row, "brands_json")

    articles = [
        dict(
            channel="news",
            title="观野SPACE 园区开放，健身与夜生活在同一座园子",
            summary="回龙观公园综合场地对邻居开放：白天 FIT 训练，傍晚 SPACE 社区，夜里 BAR。办卡约课点餐走会员中心。",
            cover=urls["news"],
            sort_order=60,
            contact_hint=None,
            body="""观野SPACE 位于回龙观公园，把观野FIT、观野BAR 和公共空间放在一起。开放后，邻居可以按自己的节奏使用场地：晨练、下班力量训练、周末市集，或只是在中庭坐一会儿。

## 开放意味着什么

园区主路与中庭对到访者开放。器械区、更衣室、吧台仍按业态管理：FIT 凭会籍或临访入场，BAR 按桌码点餐，酒水核验年龄。

## 你现在可以做的事

1. 在会员中心查看卡种、团课课表与 BAR 菜单。
2. 到前台了解当日是否有体验课或驻场。
3. 把朋友带来走一圈，不必先办卡。

欢迎带朋友来坐坐。地址、电话与营业时间见页脚，与「观野SPACE 介绍」保持一致。
""",
        ),
        dict(
            channel="news",
            title="本周六户外训练日：公园草坪免费体验课",
            summary="FIT 教练带练热身与基础力量，无需办卡。名额有限，雨天改期，着运动服装并自备水杯。",
            cover=urls["fit"],
            sort_order=50,
            contact_hint=None,
            body="""本周六上午 9:30 在园区草坪集合。由观野FIT 教练带领约 45 分钟的热身、深蹲模式与核心稳定。面向零基础，不强制推销卡种。

## 怎么参加

无需提前在官网留资。请提前 10 分钟到 SPACE 中庭签到，名额按到场顺序。请穿运动鞋，自备水杯。雨天或大风改期，以当天前台通知和本栏目更新为准。

## 体验课后

若想继续室内力量区，可咨询会籍顾问办理体验入场。已经是会员的，可直接约下一节团课。
""",
        ),
        dict(
            channel="news",
            title="BAR 夜场驻唱与特调菜单更新",
            summary="新一季特调上线，周末有驻唱。请携带有效证件，未成年人谢绝酒水，酒后请勿驾车。",
            cover=urls["bar"],
            sort_order=40,
            contact_hint=None,
            body="""观野BAR 更新了季节特调，并保留无酒精选项。周末晚间安排驻唱，开唱时间以到店公示为准，建议先看会员端菜单再决定是否留位。

## 点餐

到店扫桌码，或先在会员中心浏览。高峰期厨房按桌出餐，请谅解等待。外带与改签规则问吧台。

## 入场

请携带有效证件。未成年人不可点酒。包场与生日布置请提前到店谈档期，官网不设意向表。
""",
        ),
        dict(
            channel="news",
            title="团课课表上线：力量、瑜伽与循环训练",
            summary="常驻课种已可在会员中心预约。请提前占位，迟到超过开课后约定时间可能无法入场。",
            cover=urls["fit_g1"],
            sort_order=30,
            contact_hint=None,
            body="""观野FIT 团课课表已同步到会员中心。常驻课种包括基础力量、循环训练与瑜伽。教室容量有限，请提前预约；取消请按课表规则操作，以免占用名额。

私教不在团课课表里展示，请通过会籍或前台约教练。体验课占用草坪时，室内团课仍按原教室进行。
""",
        ),
        dict(
            channel="news",
            title="周末市集：运动装备、手作与补给摊位",
            summary="SPACE 中庭不定期摆摊，摊主与档期以当场公示为准。现场不替代会员零售柜台结算。",
            cover=urls["news2"],
            sort_order=20,
            contact_hint=None,
            body="""部分周末会在 SPACE 中庭安排市集：运动护具、补给、手作与社区摊位。摊位由场地统筹，不向访客在官网收集入驻表单。

市集期间请给消防通道留空，童车与宠物按公园规定。购物与 FIT 零售、BAR 点餐是分开的账，不要混用桌码。
""",
        ),
        dict(
            channel="news",
            title="会员须知：办卡、门禁、停车与临访",
            summary="办卡与约课在会员中心完成；门禁靠人脸。临访请前台登记。停车遵循公园指引。",
            cover=urls["space_g2"],
            sort_order=10,
            contact_hint="前台咨询或致电页脚电话",
            body="""请把官网当成了解场地的窗口，把办业务放到会员中心或小程序。

- **办卡 / 约课 / 点餐**：会员中心或微信搜索「观野SPACE」。
- **门禁**：入会后采集人脸，保持照片清晰。不要尾随。
- **临访**：前台登记，按时离场。
- **停车**：按回龙观公园停车与限行提示，场地不设独立收费承诺。
- **儿童**：器械区与吧台酒水区有年龄限制，请看现场标识。
""",
        ),
        dict(
            channel="jobs",
            title="健身顾问 / 会籍顾问",
            summary="接待到店、介绍卡种、协助入会。有健身房会籍经验优先，工作地点在观野FIT。",
            cover=urls["jobs"],
            sort_order=40,
            contact_hint="请将纸质或电子简历交前台，或致电页脚电话，不在官网投递。",
            body="""**工作地点**：回龙观公园 · 观野FIT。

## 职责

接待到店体验、介绍卡种与课包、协助会员完成入会与第一次预约。需要把规则讲清楚，而不是只追成交。

## 要求

沟通清楚，能接受周末班次。有会籍或服务行业经验优先。能使用后台办理基础开卡即可，复杂退款走主管。

## 如何联系

官网不设投递表单。请到前台咨询或致电页脚电话，按现场指引提交简历。
""",
        ),
        dict(
            channel="jobs",
            title="吧台调酒 / 服务员",
            summary="夜班为主，需健康证。有清吧或餐吧经验优先，工作地点在观野BAR。",
            cover=urls["bar"],
            sort_order=30,
            contact_hint="前台咨询或致电页脚电话",
            body="""**工作地点**：观野BAR。需能适应夜班，注重卫生与核验年龄。

职责包括吧台出杯、桌台服务、扫码点餐协助与打烊收档。酒后客人离场时提醒交通安全。有清吧、餐吧或咖啡经验优先，需办理健康证。
""",
        ),
        dict(
            channel="jobs",
            title="团课教练（兼职）",
            summary="可授基础力量、循环或瑜伽。需相关证书与可核验的带课记录，档期与课酬面议。",
            cover=urls["fit_g2"],
            sort_order=20,
            contact_hint="请先到 FIT 前台预约试课评估，勿在官网投递附件。",
            body="""观野FIT 需要能稳定出勤的兼职团课教练。课种以基础力量、循环训练、瑜伽为主。请携带证书原件到店，安排一次试课后再谈档期。

不接受只发作品集、不到店的远程合作。课酬、满班与取消规则面议，以合同为准。
""",
        ),
        dict(
            channel="jobs",
            title="前台接待",
            summary="园区总台：问询、临访登记、快递与失物。需倒班，普通话清楚，耐心对待第一次到店的邻居。",
            cover=urls["space"],
            sort_order=10,
            contact_hint="前台咨询或致电页脚电话",
            body="""前台是观野SPACE 的第一句话。工作包括问路、当日课表说明、临访登记、失物与快递代收（按现场制度）。

需要倒班与周末出勤。会用电脑处理登记即可，复杂会员问题转会籍或 BAR 当值。
""",
        ),
        dict(
            channel="partners",
            title="园区招商：轻餐 / 运动零售 / 康复理疗",
            summary="面向与 FIT、BAR 客群匹配的轻资产品牌。铺位与档期需到店看场，官网不收集留资。",
            cover=urls["partners"],
            sort_order=30,
            contact_hint="到店洽谈，电话见页脚",
            body="""观野SPACE 欢迎与训练、夜生活互补的品牌：轻餐、运动零售、康复理疗等。我们提供铺位与共同客流，不承诺保底营业额。

## 合作方式

请先到访场地，看动线、水电与营业时间是否匹配，再与运营谈面积和档期。本期**不接受**线上表单留资，也不通过官网收取意向金。

## 不适合谁

强推销、噪音过大、与酒类竞品冲突、占用消防通道的业态，以及无法配合园区统一闭园时间的品牌。
""",
        ),
        dict(
            channel="partners",
            title="快闪铺：运动装备与补给",
            summary="适合周末市集或短期快闪。提供中庭摊位或连廊一侧，档期按周谈，需自备陈列。",
            cover=urls["news2"],
            sort_order=20,
            contact_hint="到店与运营约看场时间",
            body="""中庭与连廊可安排短期快闪：护具、补给、复训周边。用电与夜间收摊需遵守公园与场地规定。

请带产品清单到店，不要邮寄样品到前台代收。档期与费用面议。
""",
        ),
        dict(
            channel="partners",
            title="理疗康复合作说明",
            summary="面向有执业资质的康复、筋膜或理疗团队。需证照齐全，服务时间避开 BAR 高峰喧哗。",
            cover=urls["fit_g3"],
            sort_order=10,
            contact_hint="到店洽谈，电话见页脚",
            body="""若你的团队已有固定客群、希望靠近训练场景，可以谈独立房间或分时使用。必须提供可核验资质，不得在器械区现场推销疗程。

合作细节（分成、水电、预约系统是否打通）一律到店谈。官网仅作说明，不构成要约。
""",
        ),
    ]
    for item in articles:
        _upsert_article(db, site_id=site.id, **item)
    db.flush()
