"""子系统 manifest 发现。"""

from __future__ import annotations

from typing import Any


def iter_system_manifests() -> list[dict[str, Any]]:
    from app.systems.catering.manifest import SYSTEM as catering
    from app.systems.gym.manifest import SYSTEM as gym
    from app.systems.platform.manifest import SYSTEM as platform

    return [platform, gym, catering]
