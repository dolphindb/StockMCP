"""Legacy optional-source runner; new deployments should use scripts/import_tushare.py."""
import argparse
import datetime
import importlib
import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import basic


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',default=basic.session['host'])
    parser.add_argument('--port',type=int,default=basic.session['port'])
    parser.add_argument('--username',default=basic.session['username'])
    parser.add_argument('--password',default=basic.session['password'])
    parser.add_argument('--token',default=basic.token)
    parser.add_argument('--mode',type=int,choices=[1,2],default=basic.mode)
    parser.add_argument('--start_date',default=basic.startDate)
    parser.add_argument('--end_date',default=basic.endDate)
    parser.add_argument('--parallelism',type=int,default=basic.parallelism)
    parser.add_argument('--data_sources',nargs='+',default=basic.dataSourceList)
    parser.add_argument('--log_dir',default=basic.logDir)
    parser.add_argument('--max_retries',type=int,default=basic.maxRetries)
    args=parser.parse_args(argv)
    if not args.password or not args.token:parser.error('Set DDB_PASSWORD and TUSHARE_TOKEN (or supply explicit arguments)')
    if args.parallelism<1:parser.error('parallelism must be positive')
    basic.session=dict(host=args.host,port=args.port,username=args.username,password=args.password)
    basic.token=args.token;basic.logDir=args.log_dir;basic.maxRetries=args.max_retries
    os.makedirs(basic.logDir,exist_ok=True)
    logging.basicConfig(level=logging.INFO,handlers=[logging.StreamHandler(),logging.FileHandler(os.path.join(basic.logDir,'AutoLoadTushareData.log'))])
    def run(source):
        module=importlib.import_module('dataSource.'+source)
        start,end=args.start_date,args.end_date
        if args.mode==2:
            start=end=datetime.date.today().strftime('%Y%m%d')
            if source in ['stock_basic','stock_name'] or source.endswith(('_back','_prev')):start=args.start_date
        # Each legacy module owns its DDB session. No shared global session is
        # used by parallel jobs. Errors propagate through future.result().
        module.main(basic.session,start,end,basic.token,source,basic.maxRetries)
        logging.info('Completed %s',source)
    with ThreadPoolExecutor(max_workers=args.parallelism) as pool:
        jobs={pool.submit(run,source):source for source in args.data_sources}
        for future in as_completed(jobs):future.result()

if __name__=='__main__':main()
