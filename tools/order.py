"""订单查询工具"""

from __future__ import annotations

import logging
import re
from typing import Any

from tools.base import BaseTool

logger = logging.getLogger(__name__)


class OrderTool(BaseTool):
    """订单查询工具"""

    ORDER_KEYWORDS = ["订单", "订单号", "单号"]

    @property
    def name(self) -> str:
        return "order_query"

    @property
    def description(self) -> str:
        return "查询订单状态"

    def can_handle(self, message: str) -> bool:
        return any(kw in message for kw in self.ORDER_KEYWORDS)

    def execute(self, order_id: str = "", **kwargs: Any) -> dict[str, Any]:
        """查询订单"""
        if not order_id:
            return {"success": False, "error": "请提供订单号"}

        return {
            "success": True,
            "order_id": order_id,
            "status": "待发货",
            "message": f"订单 {order_id} 状态：待发货，预计1-3个工作日内发出",
        }

    def extract_order_id(self, message: str) -> str:
        """从消息中提取订单号"""
        for keyword in self.ORDER_KEYWORDS:
            if keyword in message:
                idx = message.index(keyword)
                after = message[idx + len(keyword) :]
                match = re.search(r"[\w\d]+", after)
                return match.group() if match else ""
        return ""
