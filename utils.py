# -*- coding: utf-8 -*-
"""
工具函数模块
提供请求封装、UA轮换、随机延迟、日志输出等功能
"""

import random
import time
import re
import logging
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config import (
    MOBILE_USER_AGENTS, DESKTOP_USER_AGENTS,
    REQUEST_TIMEOUT, MAX_RETRIES, MIN_DELAY, MAX_DELAY,
    CONFIG_MIN_DELAY, CONFIG_MAX_DELAY,
    BLOCK_KEYWORDS,
)

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def get_random_user_agent(mobile: bool = True) -> str:
    """随机获取一个 User-Agent"""
    pool = MOBILE_USER_AGENTS if mobile else DESKTOP_USER_AGENTS
    return random.choice(pool)


def get_session(mobile: bool = True) -> requests.Session:
    """
    创建一个配置好的 requests.Session
    - 随机 User-Agent
    - 完整的请求头
    - 连接池大小为1（串行请求）
    - 自动重试策略
    """
    session = requests.Session()

    # 设置请求头
    ua = get_random_user_agent(mobile)
    if mobile:
        session.headers.update({
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://m.autohome.com.cn/',
        })
    else:
        session.headers.update({
            'User-Agent': ua,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.autohome.com.cn/',
        })

    # 设置连接池大小为1（串行请求，避免并发触发封禁）
    adapter = HTTPAdapter(
        pool_connections=1,
        pool_maxsize=1,
        max_retries=Retry(
            total=0,  # 我们自己控制重试逻辑
        )
    )
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    return session


def random_delay(min_s: float = None, max_s: float = None) -> None:
    """随机延迟，避免请求过于频繁"""
    min_s = min_s or MIN_DELAY
    max_s = max_s or MAX_DELAY
    delay = random.uniform(min_s, max_s)
    time.sleep(delay)


def safe_request(
    session: requests.Session,
    url: str,
    timeout: int = None,
    is_config_page: bool = False,
    params: dict = None,
) -> Optional[requests.Response]:
    """
    安全的请求封装
    - 自动随机延迟
    - 异常捕获和重试
    - 反爬检测
    - 状态码检查

    Args:
        session: requests.Session 对象
        url: 请求URL
        timeout: 超时时间（秒）
        is_config_page: 是否为配置页（使用更长的延迟）
        params: URL查询参数（dict）

    Returns:
        Response 对象，失败返回 None
    """
    timeout = timeout or REQUEST_TIMEOUT
    min_delay = CONFIG_MIN_DELAY if is_config_page else MIN_DELAY
    max_delay = CONFIG_MAX_DELAY if is_config_page else MAX_DELAY

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # 随机延迟
            random_delay(min_delay, max_delay)

            # 每次请求前随机更换UA
            session.headers['User-Agent'] = get_random_user_agent(mobile=is_config_page)

            response = session.get(url, params=params, timeout=timeout)

            # 检查状态码
            if response.status_code == 403:
                logger.warning(f"[403] 可能被封禁，暂停60秒: {url}")
                time.sleep(60)
                continue
            elif response.status_code == 429:
                logger.warning(f"[429] 请求频率过高，暂停120秒: {url}")
                time.sleep(120)
                continue
            elif response.status_code >= 500:
                logger.warning(f"[{response.status_code}] 服务器错误，重试 {attempt}/{MAX_RETRIES}: {url}")
                continue
            elif response.status_code != 200:
                logger.warning(f"[{response.status_code}] 请求失败: {url}")
                return None

            # 检查是否被反爬拦截
            text = response.text
            blocked = False
            for keyword in BLOCK_KEYWORDS:
                if keyword in text:
                    logger.warning(f"[反爬检测] 页面包含'{keyword}'，暂停60秒: {url}")
                    time.sleep(60)
                    # 清除cookies重新尝试
                    session.cookies.clear()
                    blocked = True
                    break
            if blocked:
                continue

            # 检查页面内容是否过短（可能是空页面或错误页）
            # API JSON 响应可能较短，仅对非配置页检查
            if not is_config_page and len(text) < 500:
                logger.warning(f"[内容过短] 页面内容仅 {len(text)} 字符: {url}")
                return None

            return response

        except requests.exceptions.Timeout:
            logger.warning(f"[超时] 请求超时，重试 {attempt}/{MAX_RETRIES}: {url}")
            timeout = int(timeout * 1.5)  # 递增超时
        except requests.exceptions.ConnectionError:
            logger.warning(f"[连接错误] 网络连接失败，重试 {attempt}/{MAX_RETRIES}: {url}")
            time.sleep(5)
        except requests.exceptions.RequestException as e:
            logger.error(f"[请求异常] {type(e).__name__}: {e}")
            return None

    logger.error(f"[失败] 达到最大重试次数，放弃: {url}")
    return None


def log_progress(current: int, total: int, success: int, fail: int, phase: str = "", extra: str = "") -> None:
    """格式化输出进度信息"""
    pct = (current / total * 100) if total > 0 else 0
    msg = f"[{phase}] 进度: {current}/{total} ({pct:.1f}%) | 成功: {success} | 失败: {fail}"
    if extra:
        msg += f" | {extra}"
    logger.info(msg)


def clean_text(text: str) -> str:
    """
    清理文本
    - 去除多余空白
    - 统一空值标记
    """
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r'\s+', ' ', text)
    # 统一空值
    if text in ['-', '暂无', '--', '---', '/', '无', '', '暂无报价', '暂无数据']:
        return ""
    return text


def extract_series_id(url: str) -> Optional[str]:
    """从URL中提取车系ID"""
    match = re.search(r'autohome\.com\.cn/(\d+)/', url)
    if match:
        return match.group(1)
    return None


def extract_spec_id(url: str) -> Optional[str]:
    """从URL中提取车型ID"""
    match = re.search(r'/spec/(\d+)/', url)
    if match:
        return match.group(1)
    return None


def extract_year(model_name: str) -> str:
    """从车型名称中提取年款（如 '2025款 1.5T 豪华型' -> '2025款'）"""
    match = re.match(r'(\d{4}款)', model_name)
    if match:
        return match.group(1)
    return ""
