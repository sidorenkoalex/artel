---
operator: Alexander Sidorenko
model: unknown
artel_sha: 65a128b89067f5180af0e2755ede192c7b4cdb16
---

# RETRO: 01M3ZK2C47Q3D2HQ0PZQFFFZBA — Тесты не подменяют time.sleep всего процесса

Итог: killed — причина: kill switch
Адрес артефактов: артефакты не сохранены (ветка удалена при kill)
Суть: Тесты не подменяют time.sleep всего процесса — --- task: 01M3ZK2C47Q3D2HQ0PZQFFFZBA type: tz author_role: operator status: draft schema_version: 2 --- # ТЗ: Тесты не подменяют time.sleep всего процесса # ТЗ: Тесты не подменяют time.sleep всего процесса Источник: строки бэклога 02.10 «Подмены time.sleep на весь процесс в tests/ — общий шаблон» (П2) и «Подмена time.sleep во всём процессе в tests/test_main_ci_line.py»; задача 01M3YS928033B1QF89VN2N5KC3 (причина нестабильного test_missing_cli_is_not_retried); решение Оператора 02.10 — первая настоящая задача набора `codex-all`.

Стоимость итого: $1.45
  analyst: $0.36, токенов 672206 (input=72165, output=7913, cache_write=0, cache_read=592128), провайдер codex, модель gpt-5.6-terra
  test_author: $1.10, токенов 3133226 (input=104473, output=28817, cache_write=0, cache_read=2999936), провайдер codex, модель gpt-6-sol

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 4 тест(ов), 0 manual, 0 skip
