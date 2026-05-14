# -*- coding: utf-8 -*-
"""
汽车之家解析器（核心模块）
通过API接口获取品牌列表和配置参数数据

API接口：
  - 品牌列表页: /grade/carhtml/{A-Z}.html (HTML解析)
  - 配置参数API: /web-main/car/param/getParamConf (JSON API)
  - 车型信息API: /web-main/car/spec/getspecinfo (JSON API)
"""

import re
import logging
from typing import List, Dict, Optional

import requests
from parsel import Selector

from parsers.base import BaseParser
from config import AUTOHOME_BRAND_URL
from utils import (
    safe_request, clean_text, extract_series_id,
    extract_spec_id, extract_year, get_session,
)

logger = logging.getLogger(__name__)

# ==================== titleid 到字段名的映射 ====================
# 基于 getParamConf API 返回的 titlelist 中的 itemid
# titleid 是 paramconflist 中的索引，对应 titlelist 中的参数
TITLEID_FIELD_MAP = {
    # 基本参数 (titleid 从 paramconflist 的索引位置确定)
    # 通过 titlelist 中的 itemid 来匹配
    113: 'model_name',       # 车型名称
    112: 'official_price',   # 厂商指导价(元)
    -2:  'dealer_price',     # 经销商报价
    111: 'manufacturer',     # 厂商
    116: 'vehicle_level',    # 级别
    115: 'energy_type',      # 能源类型
    114: 'emission_standard',# 环保标准
    117: 'launch_date',      # 上市时间
    # 车身
    14: 'length',            # 长度(mm)
    23: 'width',             # 宽度(mm)
    16: 'height',            # 高度(mm)
    17: 'wheelbase',         # 轴距(mm)
    25: 'body_structure',    # 车身结构（从基本参数中获取"X门X座X厢车"）
    26: 'doors',             # 车门数
    27: 'seats',             # 座位数
    # 发动机
    37: 'engine_model',      # 发动机型号
    38: 'engine_desc',       # 发动机描述（如"1.5T 160马力 L4"）
    # 变速箱
    108: 'transmission',     # 变速箱简称
    # 底盘转向
    86: 'drive_mode',        # 驱动方式
    # 油耗
    119: 'fuel_consumption', # WLTC综合油耗
}

# 通过 itemname 关键词匹配的字段映射
ITEMNAME_FIELD_MAP = {
    '厂商指导价': 'official_price',
    '经销商报价': 'dealer_price',
    '厂商': 'manufacturer',
    '级别': 'vehicle_level',
    '能源类型': 'energy_type',
    '上市时间': 'launch_date',
    '车身结构': 'body_structure_full',  # 如"5门5座两厢车"
    '座位数': 'seats',
    '长*宽*高': 'dimensions',
    '轴距': 'wheelbase',
    '发动机': 'engine',
    '变速箱': 'transmission',
    '驱动方式': 'drive_mode',
    '综合油耗': 'fuel_consumption',
    'WLTC综合油耗': 'fuel_consumption',
    'NEDC综合油耗': 'fuel_consumption',
    'CLTC纯电续航': 'ev_range',
    '纯电续航': 'ev_range',
    'NEDC纯电续航': 'ev_range',
    '快充时间': 'fast_charge_time',
    '慢充时间': 'slow_charge_time',
}


class AutohomeParser(BaseParser):
    """汽车之家数据解析器"""

    def __init__(self, session: requests.Session = None):
        self.session = session or get_session(mobile=False)
        # API专用Session
        self.api_session = get_session(mobile=False)
        self.api_session.headers.update({
            'Accept': 'application/json, text/plain, */*',
            'Referer': 'https://www.autohome.com.cn/',
        })

    def get_source_name(self) -> str:
        return "autohome"

    # ==================== 品牌列表解析 ====================

    def fetch_brand_list(self) -> List[Dict]:
        """
        遍历A-Z字母页，获取所有品牌和车系
        """
        all_series = []
        letters = [chr(i) for i in range(ord('A'), ord('Z') + 1)]

        for i, letter in enumerate(letters):
            url = AUTOHOME_BRAND_URL.format(letter=letter)
            logger.info(f"[品牌列表] 正在获取字母 {letter} ({i+1}/26): {url}")

            response = safe_request(self.session, url, is_config_page=False)
            if response is None:
                logger.warning(f"[品牌列表] 获取字母 {letter} 失败，跳过")
                continue

            series_list = self._parse_brand_page(response.text)
            all_series.extend(series_list)
            logger.info(f"[品牌列表] 字母 {letter} 完成，发现 {len(series_list)} 个车系")

        logger.info(f"[品牌列表] 全部完成，共发现 {len(all_series)} 个车系")
        return all_series

    def _parse_brand_page(self, html: str) -> List[Dict]:
        """解析品牌列表页HTML，提取品牌和车系"""
        sel = Selector(text=html)
        series_list = []

        # 查找所有 h4 标签（车系名称）
        all_h4 = sel.css('h4')

        # 提取品牌名列表
        brand_names = []
        for h3 in sel.css('h3'):
            text = h3.css('::text').get('')
            link_text = h3.css('a::text').get('')
            name = clean_text(link_text or text)
            if name:
                brand_names.append(name)

        for h4 in all_h4:
            link = h4.css('a')
            if not link:
                continue

            href = link.css('::attr(href)').get('')
            name = link.css('::text').get('')
            series_id = extract_series_id(href)
            if not series_id:
                continue

            series_name = clean_text(name)
            if not series_name:
                continue

            # 查找指导价
            parent = h4.xpath('./..')
            price_text = ""
            if parent:
                price_span = parent.css('span::text, a[href*="price"]::text').getall()
                price_text = ''.join(price_span).replace('指导价：', '').replace('指导价:', '').strip()

            # 查找品牌和子品牌
            brand, sub_brand = self._find_brand_context(h4, brand_names, sel)

            series_list.append({
                'brand': brand,
                'sub_brand': sub_brand,
                'series_id': series_id,
                'series_name': series_name,
                'price_range': clean_text(price_text),
            })

        return series_list

    def _find_brand_context(self, h4_element, brand_names: list, sel: Selector) -> tuple:
        """通过向上遍历DOM树，找到车系所属的品牌和子品牌"""
        brand = ""
        sub_brand = ""

        try:
            ancestors = h4_element.xpath('ancestor::*')
            for ancestor in ancestors:
                h3 = ancestor.css('h3')
                if h3:
                    brand_text = h3.css('::text').get('')
                    brand_link_text = h3.css('a::text').get('')
                    brand = clean_text(brand_link_text or brand_text)
                    break

            parent_ul = h4_element.xpath('ancestor::ul[1]')
            if parent_ul:
                prev_siblings = parent_ul.xpath('preceding-sibling::*')
                for sibling in reversed(prev_siblings):
                    a_tags = sibling.css('a')
                    for a in a_tags:
                        a_href = a.css('::attr(href)').get('')
                        a_text = a.css('::text').get('')
                        if a_href and re.search(r'brand-\d+-\d+', a_href):
                            sub_brand = clean_text(a_text)
                            break
                    if sub_brand:
                        break
        except Exception:
            pass

        return brand, sub_brand

    # ==================== 配置页解析（通过API） ====================

    def fetch_series_config(self, series_id: str, brand_name: str = "",
                            sub_brand: str = "", series_name: str = "") -> List[Dict]:
        """
        通过API获取车系的全部配置数据
        API: /web-main/car/param/getParamConf
        """
        api_url = f"https://www.autohome.com.cn/web-main/car/param/getParamConf"
        params = {
            'mode': '1',
            'site': '1',
            'seriesid': series_id,
        }

        response = safe_request(self.api_session, api_url, is_config_page=True, params=params)
        if response is None:
            return []

        try:
            data = response.json()
            if data.get('returncode') != 0:
                logger.warning(f"[API] 获取车系 {series_id} 配置失败: {data.get('message')}")
                return []

            result = data.get('result', {})
            return self._parse_api_data(result, series_id, brand_name, sub_brand, series_name)

        except Exception as e:
            logger.error(f"[API] 解析车系 {series_id} 配置失败: {e}")
            return []

    def _parse_api_data(self, result: dict, series_id: str, brand_name: str = "",
                        sub_brand: str = "", series_name: str = "") -> List[Dict]:
        """
        解析 getParamConf API 返回的数据
        """
        # 获取面包屑信息
        bread = result.get('bread', {})
        if bread.get('brandname'):
            brand_name = brand_name or bread['brandname']
        if bread.get('seriesname'):
            series_name = series_name or bread['seriesname']

        # 获取参数分类列表（用于建立 titleid -> 参数名 的映射）
        titlelist = result.get('titlelist', [])
        # 建立 titleid -> itemid -> itemname 的映射
        # paramconflist 中的 titleid 对应 titlelist 中的参数
        # 但实际上 paramconflist 的索引顺序与 titlelist 中所有 items 的平铺顺序一致

        # 获取年款信息
        conditionlist = result.get('conditionlist', [])
        year_map = {}  # year_id -> year_name
        for cond in conditionlist:
            if cond.get('typevalue') == 'year':
                for item in cond.get('list', []):
                    year_map[item['id']] = item['name']

        # 获取车型列表
        datalist = result.get('datalist', [])
        if not datalist:
            return []

        # 建立参数名映射表
        # paramconflist 是按顺序排列的，每个元素对应一个参数
        # 我们需要知道每个位置的参数名
        param_name_list = self._build_param_name_list(titlelist)

        # 解析每个车型
        results = []
        for spec in datalist:
            spec_id = str(spec.get('specid', ''))
            spec_name = spec.get('specname', '')
            spec_status = spec.get('specstatus', 0)
            min_price = spec.get('minprice', '')
            condition = spec.get('condition', [])

            # 从 condition 中提取年款
            year = ''
            for cond_val in condition:
                if cond_val in year_map:
                    year = year_map[cond_val]
                    break
            if not year:
                year = extract_year(spec_name)

            # 判断状态
            # specstatus: 20=在售, 30=停售, 40=即将上市
            if spec_status == 20:
                status = '在售'
            elif spec_status == 30:
                status = '停售'
            elif spec_status == 40:
                status = '即将上市'
            else:
                status = '在售'

            # 解析参数值
            # 注意：API 中可能存在同名参数（如两个"车身结构"），需要保留所有值
            param_values = {}
            param_multi = {}  # 保存重复参数名的所有值
            pcl = spec.get('paramconflist', [])
            for idx, param_item in enumerate(pcl):
                if idx < len(param_name_list):
                    param_name = param_name_list[idx]
                    value = clean_text(param_item.get('itemname', ''))
                    if param_name in param_values and value:
                        # 重复参数名，保留两个值
                        if param_name not in param_multi:
                            param_multi[param_name] = [param_values[param_name]]
                        param_multi[param_name].append(value)
                        param_values[param_name] = value  # 后面的覆盖前面的
                    elif value:
                        param_values[param_name] = value

            # 组装数据记录
            record = {
                'source': 'autohome',
                'brand': brand_name,
                'sub_brand': sub_brand,
                'series_id': series_id,
                'series_name': series_name,
                'spec_id': spec_id,
                'year': year,
                'model_name': spec_name,
                'official_price': min_price,
                'dealer_price': self._get_param(param_values, '经销商报价'),
                'body_structure': self._extract_body_structure(param_values, param_multi),
                'energy_type': self._get_param(param_values, '能源类型'),
                'seats': self._extract_seats(param_values, param_multi),
                'dimensions': self._build_dimensions(param_values),
                'wheelbase': self._get_param(param_values, '轴距(mm)', '轴距'),
                'engine': self._build_engine(param_values),
                'transmission': self._build_transmission(param_values),
                'drive_mode': self._get_param(param_values, '驱动方式'),
                'fuel_consumption': self._build_fuel_consumption(param_values),
                'ev_range': self._build_ev_range(param_values),
                'charging_time': self._build_charging_time(param_values),
                'vehicle_level': self._get_param(param_values, '级别'),
                'launch_date': self._get_param(param_values, '上市时间'),
                'status': status,
            }

            results.append(record)

        return results

    def _build_param_name_list(self, titlelist: list) -> list:
        """
        根据 titlelist 构建参数名列表
        titlelist 中每个分组有 items，按顺序平铺
        """
        param_names = []
        for group in titlelist:
            items = group.get('items', [])
            for item in items:
                itemid = item.get('itemid', 0)
                itemname = item.get('itemname', '')
                param_names.append(itemname)
        return param_names

    def _get_param(self, param_values: dict, *keys) -> str:
        """
        通用参数查找方法
        支持精确匹配和模糊匹配（忽略括号内的单位后缀）
        例如：查找"座位数"也能匹配到"座位数(个)"
        """
        # 第一轮：精确匹配
        for key in keys:
            val = param_values.get(key, '')
            if val:
                return val

        # 第二轮：模糊匹配（去掉括号部分后比较）
        key_base = keys[0].split('(')[0].strip() if keys else ''
        if key_base:
            for k, v in param_values.items():
                k_base = k.split('(')[0].strip()
                if k_base == key_base and v:
                    return v

        return ''

    def _extract_body_structure(self, param_values: dict, param_multi: dict = None) -> str:
        """
        提取车身结构
        API 中有两个"车身结构"参数：
          - 位置11: "5门5座两厢车"（详细格式）
          - 位置28: "两厢车"（简洁格式）
        优先返回简洁格式
        """
        # 如果有重复的"车身结构"，优先取更简洁的（不含数字的）
        if param_multi and '车身结构' in param_multi:
            for val in param_multi['车身结构']:
                if val and not re.search(r'\d+门', val):
                    return val

        full = param_values.get('车身结构', '')
        if not full:
            return ''
        # 如果值包含"X门X座X厢车"格式，提取最后的类型
        if re.search(r'\d+门\d+座', full):
            match = re.search(r'(\S+厢车|\S+车)$', full)
            if match:
                return match.group(1)
        return full

    def _build_dimensions(self, param_values: dict) -> str:
        """
        拼接车身尺寸（长*宽*高）
        API 可能返回"长*宽*高(mm)"组合值，或独立的"长度(mm)"/"宽度(mm)"/"高度(mm)"
        """
        # 优先检查组合值（带或不带单位后缀）
        combined = self._get_param(param_values, '长*宽*高(mm)', '长*宽*高')
        if combined:
            return combined

        # 分别获取长、宽、高并拼接
        length = self._get_param(param_values, '长度(mm)', '长度')
        width = self._get_param(param_values, '宽度(mm)', '宽度')
        height = self._get_param(param_values, '高度(mm)', '高度')

        parts = [v for v in [length, width, height] if v]
        return '*'.join(parts) if len(parts) == 3 else ''

    def _build_fuel_consumption(self, param_values: dict) -> str:
        """
        获取综合油耗
        兼容多种标准：WLTC/NEDC/CLTC/工信部，以及带单位后缀的版本
        """
        for key in ['WLTC综合油耗(L/100km)', 'WLTC综合油耗',
                     'CLTC综合油耗(L/100km)', 'CLTC综合油耗',
                     'NEDC综合油耗(L/100km)', 'NEDC综合油耗',
                     '综合油耗(L/100km)', '综合油耗',
                     '工信部综合油耗(L/100km)', '工信部综合油耗']:
            val = param_values.get(key, '')
            if val:
                return val
        # 模糊匹配
        return self._get_param(param_values, '综合油耗')

    def _build_ev_range(self, param_values: dict) -> str:
        """
        获取纯电续航里程
        兼容多种标准：CLTC/NEDC/WLTC，以及带单位后缀的版本
        """
        for key in ['CLTC纯电续航里程(km)', 'CLTC纯电续航',
                     'NEDC纯电续航里程(km)', 'NEDC纯电续航',
                     'WLTC纯电续航里程(km)', 'WLTC纯电续航',
                     '纯电续航里程(km)', '纯电续航']:
            val = param_values.get(key, '')
            if val:
                return val
        return self._get_param(param_values, '纯电续航')

    def _build_charging_time(self, param_values: dict) -> str:
        """组合快充和慢充时间"""
        # 兼容多种参数名格式
        fast = self._get_param(param_values, '电池快充时间(小时)', '快充时间', '快充时间(小时)')
        slow = self._get_param(param_values, '电池慢充时间(小时)', '慢充时间', '慢充时间(小时)')
        parts = []
        if fast:
            parts.append(f"快充{fast}小时")
        if slow:
            parts.append(f"慢充{slow}小时")
        return ' / '.join(parts) if parts else ''

    def _build_transmission(self, param_values: dict) -> str:
        """
        获取变速箱信息
        燃油车取"变速箱"，新能源车取"简称"或"变速箱类型"
        """
        val = self._get_param(param_values, '变速箱')
        if val:
            return val
        # 新能源车：尝试取"简称"（如"电动车单速变速箱"）
        val = self._get_param(param_values, '简称')
        if val and '变速箱' in val:
            return val
        # 再尝试"变速箱类型"
        val = self._get_param(param_values, '变速箱类型')
        if val:
            return val
        return ''

    def _build_engine(self, param_values: dict) -> str:
        """
        组装发动机/电机参数
        燃油车：取"发动机型号" + "发动机"描述
        新能源车：取"电机类型" + "电动机总功率"等
        """
        model = self._get_param(param_values, '发动机型号')
        desc = self._get_param(param_values, '发动机')
        if model and desc:
            return f"{model}（{desc}）"
        if model or desc:
            return model or desc

        # 新能源车：尝试获取电机信息
        motor_type = self._get_param(param_values, '电机类型')
        motor_power = self._get_param(param_values, '电动机总功率(kW)', '电动机总功率')
        motor_torque = self._get_param(param_values, '电动机总扭矩(N·m)', '电动机总扭矩')
        motor_ps = self._get_param(param_values, '电动机总马力(Ps)', '电动机总马力')

        parts = []
        if motor_type:
            parts.append(motor_type)
        if motor_ps:
            parts.append(f"{motor_ps}马力")
        elif motor_power:
            parts.append(f"{motor_power}kW")
        if motor_torque:
            parts.append(f"{motor_torque}N·m")

        return ' '.join(parts) if parts else ''

    def _extract_seats(self, param_values: dict, param_multi: dict = None) -> int:
        """
        提取座位数
        优先从"座位数(个)"获取，其次从"车身结构"中解析（如"5门5座两厢车"）
        """
        seats_str = self._get_param(param_values, '座位数(个)', '座位数')
        if seats_str:
            return self._parse_int(seats_str)

        # 从"车身结构"中提取（如"5门5座两厢车" -> 5）
        # 优先检查第一个"车身结构"值（包含"X门X座"信息的那个）
        if param_multi and '车身结构' in param_multi:
            for val in param_multi['车身结构']:
                match = re.search(r'(\d+)座', val)
                if match:
                    return int(match.group(1))

        body = param_values.get('车身结构', '')
        if body:
            match = re.search(r'(\d+)座', body)
            if match:
                return int(match.group(1))

        return 0

    def _parse_int(self, value: str) -> int:
        """安全解析整数字符串"""
        if not value:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0
