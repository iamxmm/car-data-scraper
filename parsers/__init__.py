# -*- coding: utf-8 -*-
"""
解析器抽象基类
定义统一接口，支持多数据源扩展
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional


class BaseParser(ABC):
    """解析器基类，所有数据源解析器必须继承此类"""

    @abstractmethod
    def fetch_brand_list(self) -> List[Dict]:
        """
        获取品牌和车系列表
        Returns:
            [{'brand': str, 'sub_brand': str, 'series_id': str,
              'series_name': str, 'price_range': str}, ...]
        """
        pass

    @abstractmethod
    def fetch_series_config(self, series_id: str, brand_name: str = "",
                            sub_brand: str = "", series_name: str = "") -> List[Dict]:
        """
        获取车系配置数据
        Returns:
            [车型数据字典, ...] 每个字典包含全部20个字段
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """返回数据源名称"""
        pass
