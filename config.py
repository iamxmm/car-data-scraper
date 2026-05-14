# -*- coding: utf-8 -*-
"""
全局配置模块
定义URL模板、常量、字段映射等
"""

import os

# ==================== 路径配置 ====================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULT_DIR = os.path.join(BASE_DIR, "result")
os.makedirs(RESULT_DIR, exist_ok=True)
DB_PATH = os.path.join(RESULT_DIR, "car_data.db")
CSV_PATH = os.path.join(RESULT_DIR, "car_data.csv")
EXCEL_PATH = os.path.join(RESULT_DIR, "car_data.xlsx")

# ==================== 汽车之家 URL 模板 ====================
AUTOHOME_BRAND_URL = "https://www.autohome.com.cn/grade/carhtml/{letter}.html"
AUTOHOME_CONFIG_URL = "https://m.autohome.com.cn/config/series/{series_id}.html"
AUTOHOME_SPEC_URL = "https://m.autohome.com.cn/spec/{spec_id}/"

# ==================== 字母列表 ====================
LETTERS = [chr(i) for i in range(ord('A'), ord('Z') + 1)]

# ==================== 请求参数 ====================
REQUEST_TIMEOUT = 15          # 请求超时（秒）
MIN_DELAY = 1.0               # 最小延迟（秒）
MAX_DELAY = 3.0               # 最大延迟（秒）
CONFIG_MIN_DELAY = 2.0        # 配置页最小延迟
CONFIG_MAX_DELAY = 4.0        # 配置页最大延迟
MAX_RETRIES = 3               # 最大重试次数
BATCH_PAUSE_COUNT = 50        # 每N个车系额外暂停
BATCH_PAUSE_MIN = 10          # 批量暂停最小时长（秒）
BATCH_PAUSE_MAX = 30          # 批量暂停最大时长（秒）
SESSION_RESET_COUNT = 200     # 每N个车系重建Session

# ==================== 20个目标字段定义 ====================
# (数据库字段名, 中文名, 配置页参数名关键词)
FIELD_DEFINITIONS = [
    ("brand",           "品牌名称",     None),                   # 从品牌列表页获取
    ("sub_brand",       "子品牌",       None),                   # 从品牌列表页获取
    ("series_id",       "车系ID",       None),                   # 从URL提取
    ("series_name",     "车系名称",     None),                   # 从品牌列表页获取
    ("spec_id",         "车型ID",       None),                   # 从配置页URL提取
    ("year",            "年款",         None),                   # 从车型名称提取
    ("model_name",      "车型名称",     None),                   # 从配置页提取
    ("official_price",  "官方指导价",   "厂商指导价"),
    ("dealer_price",    "经销商报价",   "参考价"),               # 参考价区域
    ("body_structure",  "车身结构",     "车身结构"),
    ("energy_type",     "能源类型",     "能源类型"),
    ("seats",           "座位数",       "座位数"),
    ("dimensions",      "车身尺寸",     "长*宽*高"),
    ("wheelbase",       "轴距",         "轴距"),
    ("engine",          "发动机/电机",  "发动机"),
    ("transmission",    "变速箱",       "变速箱"),
    ("drive_mode",      "驱动方式",     "驱动方式"),
    ("fuel_consumption","综合油耗",     "WLTC综合油耗"),
    ("ev_range",        "纯电续航",     "CLTC纯电续航"),
    ("charging_time",   "充电时间",     "快充时间"),
    ("vehicle_level",   "车辆级别",     "级别"),
    ("launch_date",     "上市时间",     "上市时间"),
    ("status",          "车型状态",     None),                   # 从年款分组判断
]

# 导出时使用的字段名列表（有序）
EXPORT_FIELDNAMES = [
    "brand", "sub_brand", "series_id", "series_name", "spec_id",
    "year", "model_name", "official_price", "dealer_price",
    "body_structure", "energy_type", "seats", "dimensions", "wheelbase",
    "engine", "transmission", "drive_mode", "fuel_consumption",
    "ev_range", "charging_time", "vehicle_level", "launch_date", "status"
]

# 导出时使用的表头（中文）
EXPORT_HEADERS = [
    "品牌", "子品牌", "车系ID", "车系名称", "车型ID",
    "年款", "车型名称", "官方指导价", "经销商报价",
    "车身结构", "能源类型", "座位数", "车身尺寸(长*宽*高)", "轴距(mm)",
    "发动机/电机", "变速箱", "驱动方式", "综合油耗",
    "纯电续航(km)", "充电时间", "车辆级别", "上市时间", "状态"
]

# ==================== User-Agent 列表 ====================
MOBILE_USER_AGENTS = [
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 13; 23013RK75C) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/120.0.6099.119 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; V2302A) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S921B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 13; SM-N986B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
]

DESKTOP_USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
]

# ==================== 反爬检测关键词 ====================
BLOCK_KEYWORDS = ["验证码", "安全验证", "请输入", "访问受限", "频率过快", "异常访问"]
