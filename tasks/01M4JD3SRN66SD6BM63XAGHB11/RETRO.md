---
operator: Alexander Sidorenko
model: unknown
artel_sha: c6c9245c4a2674e96c075bea34be43171e36a2df
---

# RETRO: 01M4JD3SRN66SD6BM63XAGHB11 — Приложения PLAN на рубеже in_dev → verifying и в CI ветки

Итог: done, sha c6c9245c4a2674e96c075bea34be43171e36a2df
Адрес артефактов: refs/artifacts/01M4JD3SRN66SD6BM63XAGHB11
Суть: Приложения PLAN на рубеже in_dev → verifying и в CI ветки — Рубеж `in_dev -> verifying` гоняет планку и долгоживущие файлы задачи в рабочей копии без приложений PLAN (`orchestrator/advance_gates/acceptance.py::_acceptance_run_body`: `workspace.ensure`, `acceptance.plank_in_code_copy`, `acceptance.run`), тогда как автогейт, approve и suite-run накладывают их через `orchestrator/appendix_tree.py::suite_tree`.

Стоимость итого: $10.83
  analyst: $1.57, токенов 1376562 (input=40, output=14317, cache_write=129432, cache_read=1232773), провайдер claude, модель claude-opus-5-5
  test_author: $4.41, токенов 7973148 (input=106, output=61295, cache_write=205459, cache_read=7706288), провайдер claude, модель claude-opus-5-5
  developer: $3.89, токенов 8382071 (input=110, output=41042, cache_write=179611, cache_read=8161308), провайдер claude, модель claude-opus-5-5
  reviewer: $0.96, токенов 866974 (input=20, output=8394, cache_write=80038, cache_read=778522), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
