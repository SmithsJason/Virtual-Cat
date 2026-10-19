# 评估说明

`recall_cases.json` 为人工编写的小型管道验证集，标记 dev 与 test，不是论文研究结果。开发集用于调参，测试集需独立扩充后冻结。当前样例不足以支持准确率或用户体验结论。

```bash
TEST_DATABASE_URL=postgresql+asyncpg://miaoban:miaoban@localhost:5432/miaoban_test \
  .venv/bin/python evals/recall_benchmark.py
```

默认只评估数据库关键词召回，不调用外部模型。加 `--allow-remote` 且配置 `EMBEDDING_API_KEY` 后才比较混合召回，产生 API 用量。报告输出 `.local/recall-report.json`，逐例记录 expected、actual、Recall@5、Precision@5 和无答案误召回。空集合的 precision 记 null。

正式实验还需：扩充真实中文改写与干扰样本；标注状态、时间和归属；固定提示词、模型、向量版本和参数；独立进行回答准确率与无依据作答评价。四种上下文策略的构建入口为 `app.services.context.build(strategy=...)`：`recent20`、`budget`、`summary`、`memory`。recent20 也有预算保护，不是无约束地重放旧版本。用户体验需真实试用问卷，不用模拟对话替代。
