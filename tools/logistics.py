"""物流查询工具"""

from __future__ import annotations

import logging
import re
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class LogisticsTool(BaseTool):
    """物流查询工具"""

    LOGISTICS_KEYWORDS = ["物流", "快递", "发货", "到哪了", "什么时候到"]

    @property
    def name(self) -> str:
        return "logistics_query"

    @property
    def description(self) -> str:
        return "查询物流状态"

    def can_handle(self, message: str) -> bool:
        return any(kw in message for kw in self.LOGISTICS_KEYWORDS)

    def execute(self, order_id: str = "", **kwargs: Any) -> dict[str, Any]:
        """查询物流"""
        if not order_id:
            return {"success": False, "error": "请提供订单号"}

        return {
            "success": True,
            "order_id": order_id,
            "status": "运输中",
            "location": "北京转运中心",
            "message": f"订单 {order_id} 物流状态：运输中，当前位置：北京转运中心，预计明天送达",
        }

    def extract_order_id(self, message: str) -> str:
        """从消息中提取订单号"""
        for keyword in ["订单", "订单号", "单号"]:
            if keyword in message:
                idx = message.index(keyword)
                after = message[idx + len(keyword) :]
                match = re.search(r"[\w\d]+", after)
                return match.group() if match else ""
        return ""
