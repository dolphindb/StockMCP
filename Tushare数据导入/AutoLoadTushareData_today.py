'''
Author: tanhua hua.tan@dolphindb.com
Date: 2025-10-21 16:22:33
LastEditors: tanhua hua.tan@dolphindb.com
LastEditTime: 2025-10-22 12:50:24
FilePath: \PythonModules\TushareToDDB\AutoLoadTushareData.py
Description: Modified to accept command line arguments for configuration
'''
#!/usr/bin/env python
# coding: utf-8
import basic
import importlib
import datetime
import dolphindb as ddb
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import os
import argparse

# 设置日志配置
logger_AutoLoadTushareData = logging.getLogger('logger_AutoLoadTushareData')
logger_AutoLoadTushareData.setLevel(logging.INFO)
# 日志输出到文件
fileHandler_AutoLoadTushareData = logging.FileHandler(basic.logDir + "/AutoLoadTushareData.log")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fileHandler_AutoLoadTushareData.setFormatter(formatter)
# 日志输出到控制台
console_AutoLoadTushareData = logging.StreamHandler() 
console_AutoLoadTushareData.setFormatter(formatter)
# 将 Handler 添加到 Logger
logger_AutoLoadTushareData.addHandler(fileHandler_AutoLoadTushareData)
logger_AutoLoadTushareData.addHandler(console_AutoLoadTushareData)

def parse_args():
    parser = argparse.ArgumentParser(description='AutoLoad Tushare Data to DolphinDB')
    parser.add_argument('--host', required=True, help='DolphinDB server host')
    parser.add_argument('--port', type=int, required=True, help='DolphinDB server port')
    parser.add_argument('--username', required=True, help='DolphinDB username')
    parser.add_argument('--password', required=True, help='DolphinDB password')
    parser.add_argument('--token', required=True, help='Tushare API token')
    parser.add_argument('--mode', type=int, choices=[1, 2], required=True, 
                       help='Import mode: 1 for full import, 2 for incremental import')
    parser.add_argument('--start_date', help='Start date for data import (YYYYMMDD)')
    parser.add_argument('--end_date', help='End date for data import (YYYYMMDD)')
    parser.add_argument('--parallelism', type=int, default=5, 
                       help='Number of parallel threads for data import')
    parser.add_argument('--data_sources', nargs='+', required=True, 
                       help='List of data sources to import')
    parser.add_argument('--log_dir', default='./logs', help='Directory for log files')
    parser.add_argument('--max_retries', type=int, default=3, help='Maximum retry attempts')
    return parser.parse_args()

def configure_basic_module(args):
    # Update basic module configuration with command line arguments
    basic.session = {
        "host": args.host,
        "port": args.port,
        "username": args.username,
        "password": args.password
    }
    basic.token = args.token
    basic.mode = args.mode
    basic.startDate = args.start_date if args.start_date else '19900101'
    basic.endDate = args.end_date if args.end_date else datetime.date.today().strftime("%Y%m%d")
    basic.parallelism = args.parallelism
    basic.dataSourceList = args.data_sources
    basic.logDir = args.log_dir
    basic.maxRetries = args.max_retries
    
    # Create log directory if it doesn't exist
    os.makedirs(basic.logDir, exist_ok=True)

def runDataSourceScript(dataSource, mode):
    try:
        # 如果数据导入模式为当日新增数据导入，且数据源为增量更新模式
        if mode == 1:
            startDate = basic.startDate
            endDate = basic.endDate
        if mode == 2:
            fullUpdateList = ['stock_basic', 'stock_daily_back', 'stock_daily_prev', 'stock_monthly_back', 'stock_monthly_prev', 'stock_name', 'stock_weekly_back', 'stock_weekly_prev']
            if dataSource not in fullUpdateList:
                startDate = datetime.date.today().strftime("%Y%m%d")
                endDate = datetime.date.today().strftime("%Y%m%d")
            else:
                startDate = ''
                endDate = datetime.date.today().strftime("%Y%m%d")

        module = importlib.import_module("dataSource." + dataSource)
        s.run('writeLogLevel(INFO, "easyTushareImport - AutoLoadTushareData - Loaded module: '+str(module)+'")')
        logger_AutoLoadTushareData.info("Loaded module: %s", module)

        # 调用脚本中的 main 函数
        if hasattr(module, "main"):
            module.main(basic.session, startDate, endDate, basic.token, dataSource, basic.maxRetries)
            logger_AutoLoadTushareData.info("Data source %s import completed.", dataSource)
            s.run('writeLogLevel(INFO, "'+'easyTushareImport - '+'AutoLoadTushareData'+' - Data source '+dataSource+' import completed.")')
        else:
            raise Exception(f"The script '{dataSource}' does not define a 'main' function.")
    except Exception as e:
        logger_AutoLoadTushareData.error("Failed to import the data source %s: %s.", dataSource, e)
        s.run('writeLogLevel(ERROR, "easyTushareImport - '+"AutoLoadTushareData"+" - Failed to import the data source "+dataSource+": "+str(e)+'.")')

if __name__ == "__main__":
    try:
        args = parse_args()
        configure_basic_module(args)
        
        # 与 DolphinDB 建立会话和连接
        session = basic.session
        s = ddb.session(session["host"], session["port"], session["username"], session["password"])
    except Exception as e:
        logger_AutoLoadTushareData.error("Failed to connect to DolphinDB server: %s.", e)
        exit(1)

    # 使用 ThreadPoolExecutor 并行执行
    with ThreadPoolExecutor(max_workers=basic.parallelism) as executor:
        # 提交任务到线程池
        futureToDataSource = {
            executor.submit(runDataSourceScript, dataSource, basic.mode): dataSource
            for dataSource in basic.dataSourceList
        }
        # 等待任务完成并处理结果
        for future in as_completed(futureToDataSource):
            dataSource = futureToDataSource[future]
            future.result()

