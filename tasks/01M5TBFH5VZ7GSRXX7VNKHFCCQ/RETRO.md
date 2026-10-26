---
operator: Alexander Sidorenko
model: unknown
artel_sha: 7f37c6dd7eb35695e7d0e0c8dce9344f0a1e5059
---

# RETRO: 01M5TBFH5VZ7GSRXX7VNKHFCCQ — Эпики Э4: проекция доски наружу — board, report из модели, внешние ссылки

Итог: done, sha 9a57d9e09109902bd5277cae04b9ab24c2eb9410
Адрес артефактов: refs/artifacts/01M5TBFH5VZ7GSRXX7VNKHFCCQ
Суть: Эпики Э4: проекция доски наружу — board, report из модели, внешние ссылки — ADR-0028 (принят 25.10.2026), п. 12–16, шаг Э4; идёт после Э1 (01M5TBBDFS6DWQY6MS263T1KPY), который ввёл модель доски `orchestrator/board.py` (`build_model(conn, project)` — модель одного проекта).

Стоимость итого: $35.59
  analyst: $6.16, токенов 5352063 (input=120, output=54400, cache_write=514804, cache_read=4782739), провайдер claude, модель claude-opus-5-5
  spec_auditor: $13.05, токенов 22366732 (input=406, output=132890, cache_write=761664, cache_read=21471772), провайдер claude, модель claude-opus-5-5
  test_author: $9.09, токенов 20402949 (input=256, output=124447, cache_write=326686, cache_read=19951560), провайдер claude, модель claude-opus-5-5
  developer: $5.82, токенов 14395015 (input=146, output=55423, cache_write=235944, cache_read=14103502), провайдер claude, модель claude-opus-5-5
  reviewer: $1.46, токенов 2225662 (input=42, output=10965, cache_write=102755, cache_read=2111900), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: 1 (последняя): test_author: критерий неисполним тестом — AC-14: «cmd_report на 2 и на 7 задачах делает одинаковое число запросов к steps» недостижимо в зонах задачи: уже на main `report.token_rate_divergence` → `spend.known_cost_pairs` (orchestrator/spend.py:658, файл вне зон) читает `store.task_steps` на КАЖДУЮ задачу; переформулировать критерий (вариант а) или расширить зоны (вариант б)?

Приёмочные тесты: 2 тест(ов), 0 manual, 0 skip
