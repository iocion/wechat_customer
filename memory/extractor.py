"""信息提取器 - 从对话中提取关键信息"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


class InformationExtractor:
    """从对话中提取关键信息"""

    PHONE_PATTERN = re.compile(r"1[3-9]\d{9}")
    ADDRESS_KEYWORDS = ["地址", "收货", "寄到", "送到", "发货"]
    ORDER_KEYWORDS = ["订单", "订单号", "单号"]
    SIZE_KEYWORDS = ["尺码", "码数", "尺寸"]
    COLOR_KEYWORDS = ["颜色", "色号"]

    def extract_phone(self, text: str) -> str | None:
        match = self.PHONE_PATTERN.search(text)
        return match.group() if match else None

    def extract_address(self, text: str) -> str | None:
        for keyword in self.ADDRESS_KEYWORDS:
            if keyword in text:
                idx = text.index(keyword)
                return text[idx : idx + 50]
        return None

    def extract_order_id(self, text: str) -> str | None:
        for keyword in self.ORDER_KEYWORDS:
            if keyword in text:
                idx = text.index(keyword)
                after = text[idx + len(keyword) :]
                match = re.search(r"[\w\d]+", after)
                return match.group() if match else None
        return None

    def extract_preferences(self, text: str) -> dict[str, Any]:
        preferences = {}
        for keyword in self.SIZE_KEYWORDS:
            if keyword in text:
                match = re.search(rf"{keyword}[：:]\s*(\S+)", text)
                if match:
                    preferences["size"] = match.group(1)

        for keyword in self.COLOR_KEYWORDS:
            if keyword in text:
                match = re.search(rf"{keyword}[：:]\s*(\S+)", text)
                if match:
                    preferences["color"] = match.group(1)

        return preferences

    def extract_all(self, text: str) -> dict[str, Any]:
        """提取所有关键信息"""
        result = {}

        phone = self.extract_phone(text)
        if phone:
            result["phone"] = phone

        address = self.extract_address(text)
        if address:
            result["address"] = address

        order_id = self.extract_order_id(text)
        if order_id:
            result["order_id"] = order_id

        preferences = self.extract_preferences(text)
        if preferences:
            result["preferences"] = preferences

        return result
