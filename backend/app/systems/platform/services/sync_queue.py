"""授权变更异步同步骨架：默认进程内队列，可选 RabbitMQ。"""

from __future__ import annotations

import json
import logging
import queue
import threading
from dataclasses import asdict, dataclass
from typing import Any

from app.core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass
class GrantSyncMessage:
    grant_id: int
    access_point_id: int
    member_id: int
    action: str  # upsert | revoke


_local_queue: queue.Queue[GrantSyncMessage] = queue.Queue()
_worker_started = False


def _process_message(msg: GrantSyncMessage) -> None:
    # 工程级占位：记录同步意图，后续对接具体 Pad SDK
    logger.info("门禁授权同步任务: %s", json.dumps(asdict(msg), ensure_ascii=False))


def _local_worker() -> None:
    while True:
        msg = _local_queue.get()
        try:
            _process_message(msg)
        except Exception as exc:
            logger.exception("处理授权同步消息失败")
            from app.systems.platform.services.error_events import record_error

            record_error(
                error_code="grant_sync_failed",
                message=str(exc) or "授权同步失败",
                source="worker",
                exc=exc,
            )
        finally:
            _local_queue.task_done()


def ensure_worker() -> None:
    global _worker_started
    if _worker_started:
        return
    t = threading.Thread(target=_local_worker, name="grant-sync-worker", daemon=True)
    t.start()
    _worker_started = True


def publish_grant_sync(msg: GrantSyncMessage) -> None:
    """发布授权同步；RabbitMQ 未启用时走进程内队列。"""
    settings = get_settings()
    if settings.enable_rabbitmq:
        try:
            # 延迟导入，避免未安装 pika 时影响主路径
            import pika  # type: ignore

            params = pika.URLParameters(settings.rabbitmq_url)
            conn = pika.BlockingConnection(params)
            ch = conn.channel()
            ch.queue_declare(queue="access.grant.sync", durable=True)
            ch.basic_publish(
                exchange="",
                routing_key="access.grant.sync",
                body=json.dumps(asdict(msg)).encode("utf-8"),
                properties=pika.BasicProperties(delivery_mode=2),
            )
            conn.close()
            return
        except Exception:
            logger.exception("RabbitMQ 发布失败，回退本地队列")

    ensure_worker()
    _local_queue.put(msg)


def queue_stats() -> dict[str, Any]:
    return {"local_queue_size": _local_queue.qsize(), "rabbitmq_enabled": get_settings().enable_rabbitmq}
