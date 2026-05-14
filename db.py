# -*- coding: utf-8 -*-
"""
SQLite 数据库操作层
负责建表、数据插入、去重、日志记录、断点续爬等
"""

import sqlite3
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def init_db(db_path: str) -> sqlite3.Connection:
    """初始化数据库，创建连接和表"""
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 让查询结果可以通过列名访问
    conn.execute("PRAGMA journal_mode=WAL")  # 提高并发性能
    conn.execute("PRAGMA synchronous=NORMAL")
    create_tables(conn)
    logger.info(f"数据库初始化完成: {db_path}")
    return conn


def create_tables(conn: sqlite3.Connection) -> None:
    """创建所有数据表"""
    cursor = conn.cursor()

    # 主数据表：车型信息
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS car_models (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            source          TEXT NOT NULL DEFAULT 'autohome',
            brand           TEXT NOT NULL DEFAULT '',
            sub_brand       TEXT DEFAULT '',
            series_id       TEXT NOT NULL DEFAULT '',
            series_name     TEXT NOT NULL DEFAULT '',
            spec_id         TEXT NOT NULL DEFAULT '',
            year            TEXT DEFAULT '',
            model_name      TEXT NOT NULL DEFAULT '',
            official_price  TEXT DEFAULT '',
            dealer_price    TEXT DEFAULT '',
            body_structure  TEXT DEFAULT '',
            energy_type     TEXT DEFAULT '',
            seats           INTEGER DEFAULT 0,
            dimensions      TEXT DEFAULT '',
            wheelbase       TEXT DEFAULT '',
            engine          TEXT DEFAULT '',
            transmission    TEXT DEFAULT '',
            drive_mode      TEXT DEFAULT '',
            fuel_consumption TEXT DEFAULT '',
            ev_range        TEXT DEFAULT '',
            charging_time   TEXT DEFAULT '',
            vehicle_level   TEXT DEFAULT '',
            launch_date     TEXT DEFAULT '',
            status          TEXT DEFAULT '',
            crawled_at      TEXT DEFAULT (datetime('now', 'localtime')),
            UNIQUE(source, spec_id)
        )
    """)

    # 索引
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_brand ON car_models(brand)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_series_id ON car_models(series_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_energy_type ON car_models(energy_type)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_status ON car_models(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_source ON car_models(source)")

    # 爬取日志表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS crawl_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id   TEXT NOT NULL DEFAULT '',
            source      TEXT NOT NULL DEFAULT 'autohome',
            status      TEXT NOT NULL DEFAULT '',
            error_msg   TEXT DEFAULT '',
            spec_count  INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    # 失败任务表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS failed_tasks (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            series_id   TEXT NOT NULL DEFAULT '',
            source      TEXT NOT NULL DEFAULT 'autohome',
            url         TEXT NOT NULL DEFAULT '',
            error_type  TEXT DEFAULT '',
            retry_count INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now', 'localtime')),
            updated_at  TEXT DEFAULT (datetime('now', 'localtime'))
        )
    """)

    conn.commit()


def insert_car_model(conn: sqlite3.Connection, data: dict) -> bool:
    """
    插入单条车型数据
    使用 INSERT OR REPLACE 实现去重（基于 source + spec_id 唯一键）
    """
    try:
        # 处理 seats 字段（整数类型）
        seats = data.get('seats', 0)
        if isinstance(seats, str):
            seats = int(seats) if seats.isdigit() else 0

        conn.execute("""
            INSERT OR REPLACE INTO car_models (
                source, brand, sub_brand, series_id, series_name, spec_id,
                year, model_name, official_price, dealer_price,
                body_structure, energy_type, seats, dimensions, wheelbase,
                engine, transmission, drive_mode, fuel_consumption,
                ev_range, charging_time, vehicle_level, launch_date, status
            ) VALUES (
                :source, :brand, :sub_brand, :series_id, :series_name, :spec_id,
                :year, :model_name, :official_price, :dealer_price,
                :body_structure, :energy_type, :seats, :dimensions, :wheelbase,
                :engine, :transmission, :drive_mode, :fuel_consumption,
                :ev_range, :charging_time, :vehicle_level, :launch_date, :status
            )
        """, {
            'source': data.get('source', 'autohome'),
            'brand': data.get('brand', ''),
            'sub_brand': data.get('sub_brand', ''),
            'series_id': data.get('series_id', ''),
            'series_name': data.get('series_name', ''),
            'spec_id': data.get('spec_id', ''),
            'year': data.get('year', ''),
            'model_name': data.get('model_name', ''),
            'official_price': data.get('official_price', ''),
            'dealer_price': data.get('dealer_price', ''),
            'body_structure': data.get('body_structure', ''),
            'energy_type': data.get('energy_type', ''),
            'seats': seats,
            'dimensions': data.get('dimensions', ''),
            'wheelbase': data.get('wheelbase', ''),
            'engine': data.get('engine', ''),
            'transmission': data.get('transmission', ''),
            'drive_mode': data.get('drive_mode', ''),
            'fuel_consumption': data.get('fuel_consumption', ''),
            'ev_range': data.get('ev_range', ''),
            'charging_time': data.get('charging_time', ''),
            'vehicle_level': data.get('vehicle_level', ''),
            'launch_date': data.get('launch_date', ''),
            'status': data.get('status', ''),
        })
        return True
    except sqlite3.Error as e:
        logger.error(f"插入数据失败: {e}, data={data.get('spec_id', 'unknown')}")
        return False


def batch_insert_car_models(conn: sqlite3.Connection, data_list: list) -> int:
    """批量插入车型数据，使用事务"""
    success_count = 0
    try:
        conn.execute("BEGIN TRANSACTION")
        for data in data_list:
            if insert_car_model(conn, data):
                success_count += 1
        conn.commit()
    except sqlite3.Error as e:
        conn.rollback()
        logger.error(f"批量插入失败，已回滚: {e}")
    return success_count


def is_series_crawled(conn: sqlite3.Connection, series_id: str, source: str = 'autohome') -> bool:
    """检查车系是否已被成功爬取（断点续爬）"""
    try:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM crawl_log WHERE series_id=? AND source=? AND status='success'",
            (series_id, source)
        )
        count = cursor.fetchone()[0]
        return count > 0
    except sqlite3.Error:
        return False


def insert_crawl_log(conn: sqlite3.Connection, series_id: str, status: str,
                     spec_count: int = 0, error_msg: str = "", source: str = 'autohome') -> None:
    """记录爬取日志"""
    try:
        conn.execute("""
            INSERT INTO crawl_log (series_id, source, status, spec_count, error_msg)
            VALUES (?, ?, ?, ?, ?)
        """, (series_id, source, status, spec_count, error_msg))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"写入日志失败: {e}")


def insert_failed_task(conn: sqlite3.Connection, series_id: str, url: str,
                       error_type: str = "", source: str = 'autohome') -> None:
    """记录失败任务"""
    try:
        conn.execute("""
            INSERT OR REPLACE INTO failed_tasks (series_id, source, url, error_type, retry_count, updated_at)
            VALUES (?, ?, ?, ?, COALESCE((SELECT retry_count FROM failed_tasks WHERE series_id=? AND source=?), 0) + 1, datetime('now', 'localtime'))
        """, (series_id, source, url, error_type, series_id, source))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"记录失败任务失败: {e}")


def get_failed_tasks(conn: sqlite3.Connection, source: str = 'autohome') -> list:
    """获取所有失败任务"""
    try:
        cursor = conn.execute(
            "SELECT series_id, url, error_type, retry_count FROM failed_tasks WHERE source=? AND retry_count < 3",
            (source,)
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error:
        return []


def get_all_car_models(conn: sqlite3.Connection, source: str = 'autohome') -> list:
    """获取所有车型数据"""
    try:
        cursor = conn.execute(
            "SELECT * FROM car_models WHERE source=? ORDER BY brand, series_name, year",
            (source,)
        )
        return [dict(row) for row in cursor.fetchall()]
    except sqlite3.Error as e:
        logger.error(f"查询数据失败: {e}")
        return []


def get_statistics(conn: sqlite3.Connection, source: str = 'autohome') -> dict:
    """获取统计信息"""
    stats = {}
    try:
        # 总记录数
        cursor = conn.execute("SELECT COUNT(*) FROM car_models WHERE source=?", (source,))
        stats['total'] = cursor.fetchone()[0]

        # 品牌数
        cursor = conn.execute("SELECT COUNT(DISTINCT brand) FROM car_models WHERE source=?", (source,))
        stats['brands'] = cursor.fetchone()[0]

        # 车系数
        cursor = conn.execute("SELECT COUNT(DISTINCT series_id) FROM car_models WHERE source=?", (source,))
        stats['series'] = cursor.fetchone()[0]

        # 按能源类型统计
        cursor = conn.execute("""
            SELECT energy_type, COUNT(*) as cnt FROM car_models
            WHERE source=? AND energy_type != ''
            GROUP BY energy_type ORDER BY cnt DESC
        """, (source,))
        stats['by_energy'] = dict(cursor.fetchall())

        # 按状态统计
        cursor = conn.execute("""
            SELECT status, COUNT(*) as cnt FROM car_models
            WHERE source=? AND status != ''
            GROUP BY status ORDER BY cnt DESC
        """, (source,))
        stats['by_status'] = dict(cursor.fetchall())

        # 爬取日志统计
        cursor = conn.execute("""
            SELECT status, COUNT(*) as cnt FROM crawl_log
            WHERE source=?
            GROUP BY status
        """, (source,))
        stats['crawl_status'] = dict(cursor.fetchall())

        # 失败任务数
        cursor = conn.execute("SELECT COUNT(*) FROM failed_tasks WHERE source=?", (source,))
        stats['failed'] = cursor.fetchone()[0]

    except sqlite3.Error as e:
        logger.error(f"获取统计信息失败: {e}")

    return stats


def close_db(conn: sqlite3.Connection) -> None:
    """关闭数据库连接"""
    try:
        conn.close()
        logger.info("数据库连接已关闭")
    except Exception:
        pass
