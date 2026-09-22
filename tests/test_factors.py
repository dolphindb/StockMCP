import pandas as pd
import numpy as np
from factors import financial_observations,attach_asof


def test_announcements_are_not_available_on_or_before_release():
    raw=pd.DataFrame([dict(ts_code='X',ann_date='2025-01-06',f_ann_date='2025-01-07',end_date='2024-09-30',report_type='1',revenue=100,n_income=20,n_income_attr_p=18)])
    obs=financial_observations(raw,'income')
    base=pd.DataFrame({'ts_code':['X']*3,'trade_date':pd.to_datetime(['2025-01-06','2025-01-07','2025-01-08'])})
    result=attach_asof(base,obs)
    assert result.net_profit_margin.isna().tolist()==[True,True,False]
    assert result.net_profit_margin.iloc[-1]==.2


def test_old_report_revision_does_not_replace_latest_quarter():
    raw=pd.DataFrame([
        dict(ts_code='X',ann_date='2024-10-20',f_ann_date='2024-10-20',end_date='2024-09-30',report_type='1',revenue=100,n_income=20,n_income_attr_p=18),
        dict(ts_code='X',ann_date='2025-01-20',f_ann_date='2025-01-20',end_date='2023-09-30',report_type='4',revenue=100,n_income=10,n_income_attr_p=9),
    ])
    result=financial_observations(raw,'income')
    assert result.net_profit_margin.tolist()==[.2,.2]
    assert result.profit_yoy.iloc[-1]==1
    assert result.income_end_date.iloc[-1]==pd.Timestamp('2024-09-30')


def test_parent_only_and_zero_denominator_not_fabricated():
    raw=pd.DataFrame([
        dict(ts_code='X',ann_date='2024-10-20',f_ann_date=None,end_date='2024-09-30',report_type='1',total_assets=0,total_liab=10,total_hldr_eqy_exc_min_int=0),
        dict(ts_code='X',ann_date='2024-10-21',f_ann_date=None,end_date='2024-09-30',report_type='6',total_assets=100,total_liab=10,total_hldr_eqy_exc_min_int=90),
    ])
    result=financial_observations(raw,'balance')
    assert len(result)==1 and np.isnan(result.debt_ratio.iloc[0])
