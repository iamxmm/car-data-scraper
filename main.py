# -*- coding: utf-8 -*-
"""
汽车垂直网站完整车型数据爬虫 — 主入口
=============================================

功能：
  - 爬取汽车之家全量车型数据（20个字段）
  - 数据保存至 SQLite 本地数据库
  - 支持导出 CSV / Excel
  - 支持断点续爬、失败重试
  - 反爬措施：随机UA、请求延迟、Session管理

使用方式：
  1. 安装依赖：pip install -r requirements.txt
  2. 运行爬虫：python main.py
  3. 仅获取品牌列表（不爬配置）：python main.py --dry-run
  4. 指定字母范围：python main.py --start-letter A --end-letter C
  5. 重试失败任务：python main.py --retry-failed
  6. 仅导出数据：python main.py --export-only

可适配网站：
  - 汽车之家（已实现，主数据源）
  - 懂车帝（预留接口，待实现）
  - 易车网（预留接口，待实现）

作者：SOLO
日期：2026-05-13
"""

import argparse
import logging
import random
import sys
import time
from datetime import datetime

from config import (
    DB_PATH, CSV_PATH, EXCEL_PATH,
    LETTERS, BATCH_PAUSE_COUNT, BATCH_PAUSE_MIN, BATCH_PAUSE_MAX,
    SESSION_RESET_COUNT,
)
from db import (
    init_db, is_series_crawled, batch_insert_car_models,
    insert_crawl_log, insert_failed_task, get_failed_tasks,
    get_all_car_models, get_statistics, close_db,
)
from utils import get_session, log_progress, random_delay
from parsers.autohome import AutohomeParser
from exporters.csv_exporter import export_to_csv, export_to_excel

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('crawl.log', encoding='utf-8'),
    ]
)
logger = logging.getLogger(__name__)


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description='汽车垂直网站车型数据爬虫',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例：
  python main.py                          # 全量爬取
  python main.py --dry-run                # 仅获取品牌列表
  python main.py --start-letter A --end-letter C  # 爬取A-C字母
  python main.py --retry-failed           # 重试失败任务
  python main.py --export-only            # 仅导出已有数据
  python main.py --test                   # 测试模式（仅爬1个车系）
        """
    )

    parser.add_argument(
        '--source', type=str, default='autohome',
        choices=['autohome', 'dongchedi', 'yiche'],
        help='数据源（默认: autohome）'
    )
    parser.add_argument(
        '--output', type=str, default='all',
        choices=['csv', 'excel', 'all', 'db'],
        help='输出格式（默认: all，同时输出CSV和Excel）'
    )
    parser.add_argument(
        '--start-letter', type=str, default='A',
        help='起始字母（默认: A）'
    )
    parser.add_argument(
        '--end-letter', type=str, default='Z',
        help='结束字母（默认: Z）'
    )
    parser.add_argument(
        '--retry-failed', action='store_true',
        help='重试失败的任务'
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='仅获取品牌/车系列表，不爬取配置数据'
    )
    parser.add_argument(
        '--export-only', action='store_true',
        help='仅从数据库导出数据，不爬取'
    )
    parser.add_argument(
        '--test', action='store_true',
        help='测试模式：仅爬取1个车系验证功能'
    )
    parser.add_argument(
        '--db-path', type=str, default=DB_PATH,
        help=f'数据库文件路径（默认: {DB_PATH}）'
    )

    return parser.parse_args()


def crawl_brand_list(parser) -> list:
    """获取品牌和车系列表"""
    logger.info("=" * 60)
    logger.info("阶段一：获取品牌和车系列表")
    logger.info("=" * 60)

    series_list = parser.fetch_brand_list()

    # 过滤无效车系
    valid_series = [s for s in series_list if s.get('series_id')]

    logger.info(f"共获取 {len(series_list)} 个车系，有效 {len(valid_series)} 个")

    # 按品牌统计
    brands = {}
    for s in valid_series:
        brand = s.get('brand', '未知')
        brands[brand] = brands.get(brand, 0) + 1

    logger.info(f"涉及 {len(brands)} 个品牌")
    for brand, count in sorted(brands.items(), key=lambda x: -x[1])[:10]:
        logger.info(f"  {brand}: {count} 个车系")

    return valid_series


def crawl_series_configs(parser, conn, series_list: list, args) -> tuple:
    """
    爬取所有车系的配置数据
    Returns:
        (success_count, fail_count)
    """
    logger.info("=" * 60)
    logger.info("阶段二：爬取车系配置数据")
    logger.info("=" * 60)

    total = len(series_list)
    success_count = 0
    fail_count = 0
    total_specs = 0

    # 按字母范围过滤
    start_letter = args.start_letter.upper()
    end_letter = args.end_letter.upper()

    for i, series_info in enumerate(series_list):
        series_id = series_info['series_id']
        series_name = series_info['series_name']
        brand_name = series_info.get('brand', '')
        sub_brand = series_info.get('sub_brand', '')

        # 字母范围过滤（基于品牌名首字母）
        if brand_name:
            first_char = brand_name[0].upper()
            if first_char < start_letter or first_char > end_letter:
                continue

        # 断点续爬：检查是否已爬取
        if is_series_crawled(conn, series_id):
            continue

        # 进度输出
        log_progress(i + 1, total, success_count, fail_count,
                     phase="配置爬取", extra=f"当前: {brand_name} {series_name}")

        try:
            # 请求配置页并解析
            config_url = f"https://m.autohome.com.cn/config/series/{series_id}.html"
            car_models = parser.fetch_series_config(
                series_id, brand_name, sub_brand, series_name
            )

            if car_models:
                # 写入数据库
                inserted = batch_insert_car_models(conn, car_models)
                success_count += 1
                total_specs += len(car_models)
                insert_crawl_log(conn, series_id, 'success', spec_count=len(car_models))
                logger.info(f"  ✓ {brand_name} {series_name}: {len(car_models)} 个车型")
            else:
                fail_count += 1
                insert_failed_task(conn, series_id, config_url, error_type='empty_data')
                insert_crawl_log(conn, series_id, 'fail', error_msg='无车型数据')
                logger.warning(f"  ✗ {brand_name} {series_name}: 无车型数据")

        except KeyboardInterrupt:
            logger.info("用户中断，保存进度后退出...")
            break
        except Exception as e:
            fail_count += 1
            config_url = f"https://m.autohome.com.cn/config/series/{series_id}.html"
            insert_failed_task(conn, series_id, config_url, error_type=str(e)[:100])
            insert_crawl_log(conn, series_id, 'fail', error_msg=str(e)[:200])
            logger.error(f"  ✗ {brand_name} {series_name}: {e}")

        # 批量暂停（每N个车系额外暂停）
        if (i + 1) % BATCH_PAUSE_COUNT == 0:
            pause_time = random.uniform(BATCH_PAUSE_MIN, BATCH_PAUSE_MAX)
            logger.info(f"[批量暂停] 已爬取 {i + 1} 个车系，暂停 {pause_time:.0f} 秒...")
            time.sleep(pause_time)

        # Session 重置（每N个车系重建Session）
        if (i + 1) % SESSION_RESET_COUNT == 0:
            logger.info("[Session重置] 重建网络连接...")
            parser.session = get_session(mobile=False)
            parser.api_session = get_session(mobile=False)
            parser.api_session.headers.update({
                'Accept': 'application/json, text/plain, */*',
                'Referer': 'https://www.autohome.com.cn/',
            })

        # 测试模式：只爬1个
        if args.test and i >= 0:
            logger.info("[测试模式] 仅爬取1个车系，退出")
            break

    logger.info(f"\n配置爬取完成！成功: {success_count} | 失败: {fail_count} | 总车型数: {total_specs}")
    return success_count, fail_count


def retry_failed(parser, conn, args) -> None:
    """重试失败的任务"""
    logger.info("=" * 60)
    logger.info("重试失败任务")
    logger.info("=" * 60)

    failed_tasks = get_failed_tasks(conn)
    if not failed_tasks:
        logger.info("没有需要重试的失败任务")
        return

    logger.info(f"共 {len(failed_tasks)} 个失败任务待重试")

    success = 0
    for task in failed_tasks:
        series_id = task['series_id']
        logger.info(f"重试车系: {series_id}")

        try:
            car_models = parser.fetch_series_config(series_id)
            if car_models:
                batch_insert_car_models(conn, car_models)
                insert_crawl_log(conn, series_id, 'success', spec_count=len(car_models))
                # 从失败表中删除
                conn.execute("DELETE FROM failed_tasks WHERE series_id=? AND source='autohome'",
                           (series_id,))
                conn.commit()
                success += 1
                logger.info(f"  ✓ 重试成功: {len(car_models)} 个车型")
            else:
                logger.warning(f"  ✗ 重试失败: 无车型数据")

            # 更大的延迟
            time.sleep(random.uniform(5, 10))

        except Exception as e:
            logger.error(f"  ✗ 重试异常: {e}")

    logger.info(f"重试完成！成功: {success}/{len(failed_tasks)}")


def export_data(conn, args) -> None:
    """从数据库导出数据"""
    logger.info("=" * 60)
    logger.info("阶段三：导出数据")
    logger.info("=" * 60)

    data = get_all_car_models(conn)
    if not data:
        logger.warning("数据库中没有数据，跳过导出")
        return

    logger.info(f"从数据库读取 {len(data)} 条记录")

    output = args.output
    if output in ('all', 'csv'):
        export_to_csv(data)
    if output in ('all', 'excel'):
        export_to_excel(data)
    if output == 'db':
        logger.info("仅数据库模式，跳过文件导出")


def print_statistics(conn) -> None:
    """打印统计信息"""
    stats = get_statistics(conn)

    logger.info("\n" + "=" * 60)
    logger.info("数据统计")
    logger.info("=" * 60)
    logger.info(f"总车型数: {stats.get('total', 0)}")
    logger.info(f"品牌数: {stats.get('brands', 0)}")
    logger.info(f"车系数: {stats.get('series', 0)}")

    if stats.get('by_energy'):
        logger.info("按能源类型:")
        for k, v in stats['by_energy'].items():
            logger.info(f"  {k}: {v}")

    if stats.get('by_status'):
        logger.info("按状态:")
        for k, v in stats['by_status'].items():
            logger.info(f"  {k}: {v}")

    if stats.get('crawl_status'):
        logger.info("爬取状态:")
        for k, v in stats['crawl_status'].items():
            logger.info(f"  {k}: {v}")

    failed = stats.get('failed', 0)
    if failed > 0:
        logger.info(f"失败任务数: {failed}（可使用 --retry-failed 重试）")

    logger.info("=" * 60)


def main():
    """主函数"""
    args = parse_args()

    # 打印启动信息
    logger.info("=" * 60)
    logger.info("汽车垂直网站车型数据爬虫 v1.0")
    logger.info(f"数据源: {args.source}")
    logger.info(f"输出格式: {args.output}")
    logger.info(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 初始化数据库
    conn = init_db(args.db_path)

    try:
        # 仅导出模式
        if args.export_only:
            export_data(conn, args)
            print_statistics(conn)
            return

        # 初始化解析器
        parser = AutohomeParser()

        # 重试失败任务
        if args.retry_failed:
            retry_failed(parser, conn, args)
            print_statistics(conn)
            return

        # 获取品牌列表
        series_list = crawl_brand_list(parser)

        if args.dry_run:
            logger.info("[Dry Run] 仅获取品牌列表，不爬取配置数据")
            logger.info(f"共 {len(series_list)} 个车系待爬取")
            return

        # 测试模式：只取前1个车系
        if args.test:
            series_list = series_list[:1]
            logger.info(f"[测试模式] 仅爬取 {len(series_list)} 个车系")

        # 爬取配置数据
        crawl_series_configs(parser, conn, series_list, args)

        # 导出数据
        export_data(conn, args)

        # 打印统计
        print_statistics(conn)

    except KeyboardInterrupt:
        logger.info("\n程序被用户中断")
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
    finally:
        close_db(conn)
        logger.info(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")


if __name__ == '__main__':
    main()
