# 数据源与因子加工

## 真实数据

在**不含合成样例数据**的独立实例安装后：

```bash
read -s TUSHARE_TOKEN
export TUSHARE_TOKEN
# 先用两个证券、五个交易日验证账户权限与网络。
python scripts/import_tushare.py --start 20250901 --end 20250905 --codes 600519.SH 000001.SZ
python scripts/factors.py --start 2025-09-01 --end 2025-09-05
```

默认串行请求，`--pause` 控制请求间隔。数据权限及额度由用户自己的 Tushare 账户决定。默认源顺序：股票列表 → 历史名称 → 原始日行情 → 复权因子 → 每日指标 → 涨跌停 → ST → 指数信息/行情/权重 → 财报 → 复权行情。股票列表保留 L/D/P 三种状态，避免只取目前上市股票。`--codes` 是小范围验证选项，不限制基准指数查询；不传时使用导入的证券集合。

`--sources` 可选择其中一部分；例如已有股票列表后补取特定日期行情。不允许在缺复权因子的情况下静默生成部分复权行情。指数权重额外读取开始日期前一月，以获得区间开始时的成分信息。接口采用分页，遇到接口忽略 offset 时主动报错，避免把截断数据当作完整导入。

可选资金流与基础信息：

```bash
python scripts/import_tushare.py --start 20250901 --end 20250905 \
  --sources stock_info stock_index_basic moneyflow moneyflow_ind_ths
```

stock_info 对应 bak_basic；stock_index_basic 对应 index_basic，为旧工具保留查询表名。个股资金流与同花顺行业资金流分别入表，不混合供应商口径。更早发布的周/月行情、其他选配数据源保留在 `Tushare数据导入/dataSource`，可通过旧入口按需调用。

参考：[Tushare 接口与权限](https://tushare.pro/document/1?doc_id=108)、[指数权重](https://tushare.pro/document/2?doc_id=96)、[ST 历史名单](https://tushare.pro/document/2?doc_id=397)。

## 因子表

原始数据写入 basic_factor/day_factor/quarter_factor 等分组库。`scripts/factors.py` 将指标写入 `dfs://factor/day_factor`，四列为：

| 列 | 类型 | 含义 |
|---|---|---|
| tradetime | DATE | 因子观测交易日 |
| securityid | SYMBOL | 股票代码 |
| value | DOUBLE | 数值，缺来源时保留 NULL |
| factorname | SYMBOL | 因子名，与元数据表一致 |

提供 34 个基础因子：7 个行情字段、15 个每日指标、12 个财务/状态/板块衍生字段。准确名单及中文说明由 `metadata_frame()` 生成；自定义因子须另外登记元数据和实际观测值，不能仅写说明。

关键口径：

- amount：千元；vol：手；total_mv/circ_mv：万元；PE/PB 为倍数。
- 新导入器生成固定基准复权价格：原始价 × 当日复权因子 / 首个已导入交易日复权因子。它与按最新交易日归一化的前复权价格只差常数尺度，避免每日改写归一基准。兼容表名仍为 stock_daily_prev。历史回补改变首日基准时，应重新加工完整因子区间，不能混用两种价格尺度。
- 财务信息按 `max(ann_date, f_ann_date)` 可得时点对齐，公告当日不使用，下一有行情日才可用。选择合并报表类型 1/4/5；旧季度后来的修订不会覆盖最新报告期。
- ROE 为累计归母净利润 / 同期末归母权益，不是年化或平均权益口径；收入和资产负债表报告期不一致时不计算。
- net_profit_margin 为累计净利润 / 累计营业收入，**不是增长率**；profit_yoy 才是同报告期归母净利润同比。上年基数非正时同比留空。
- debt_ratio 为总负债 / 总资产。以上财务比率用小数，不是百分数。
- list_days 为自然日数。ST 使用历史名称区间；无覆盖时为空，不能按当前名称回填历史。S、涨跌停根据当日原始行情和限价判断，不比较复权价与原始限价。
- 行业筛选仍基于 stock_basic 当前行业；基础数据的历史修订并不等价于完整 vintage 数据。不要将这套示例称为完整无偏的机构级点时数据库。

TSDB 表使用 LAST 策略对相同主键的观测更新。按日期分批构建即可完成回填；真实全市场长历史建议按月分批，避免一次把全部行情加载到 Python 内存。

## 检索

`get_factor_metas_by_rag` 现在提供可离线运行的检索实现：元数据和同义描述转成 UTF-8 字节 1–6 gram 的二值词项向量，按余弦相似度取结果，再与显式关键词匹配合并去重。它是本地词项向量检索，**不是预训练语义 embedding 模型**，不需要外部 API、密钥或隐含的向量库。元数据为空或没有匹配时可返回空结果；不会用固定假结果绕过依赖。

保留函数名称和返回合同，便于今后替换为机构自己的 embedding 检索：至少返回 factor_name、source_table、description、factor_code 四列。

## 增量更新

按照“导入相关原始数据 → 复权价格 → 重建受影响日期因子”的顺序运行。用操作系统自己的调度器执行命令即可，本仓库不会自动安装定时任务。重复执行不会清空数据库。财报新增或修订可能影响多个后续交易日，应重新构建相应区间，而不是仅重算公告当天。
