from unittest.mock import Mock
import pandas as pd
import pytest
from import_tushare import Importer


def importer(pages):
    obj=Importer.__new__(Importer);obj.pause=0;obj.pro=Mock()
    obj.pro.query.side_effect=pages
    return obj


def test_pagination_uses_offset_and_keeps_final_page():
    obj=importer([pd.DataFrame({'x':range(500)}),pd.DataFrame({'x':[500]})])
    result=obj.query('daily',trade_date='20250106')
    assert len(result)==501
    assert obj.pro.query.call_args_list[1].kwargs['offset']==500


def test_ignored_offset_fails_instead_of_infinite_loop_or_partial_success():
    page=pd.DataFrame({'x':range(500)})
    obj=importer([page,page])
    with pytest.raises(RuntimeError,match='ignored pagination'):obj.query('daily')


def test_empty_result_and_provider_failure_are_distinct():
    assert importer([pd.DataFrame()]).query('daily').empty
    with pytest.raises(RuntimeError,match='returned None'):importer([None]).query('daily')
