---
operator: Alexander Sidorenko
model: unknown
artel_sha: a5df6f64b8a5aaa4dc964ddc89ef5f06a84e4229
---

# RETRO: 01M41M6KGWA9PJ6G1KPDC6XY70 — CI быстрее: проверка на минимальной версии Python отдельным параллельным заданием; песочница FsmTest не сорит в каталог задач

Итог: done, sha a5df6f64b8a5aaa4dc964ddc89ef5f06a84e4229
Адрес артефактов: refs/artifacts/01M41M6KGWA9PJ6G1KPDC6XY70
Суть: CI быстрее: проверка на минимальной версии Python отдельным параллельным заданием; песочница FsmTest не сорит в каталог задач — Время прогона CI определяет задание `python` («Синтаксис и тесты оркестратора», `.github/workflows/ci.yml:189`): замер Оператора 03.10.2026 по CI `main` — 314 с, из них полный `tests/` с `-n auto` 193 с и `tests/test_invariants.py` на минимальной версии Python в один процесс 110 с, последовательно в том же задании (`ci.yml:232-245`).

Стоимость итого: $7.37
  analyst: $0.89, токенов 770376 (input=20, output=8389, cache_write=73384, cache_read=688583), провайдер claude, модель claude-opus-5-5
  test_author: $3.00, токенов 5053197 (input=112, output=50836, cache_write=125811, cache_read=4876438), провайдер claude, модель claude-opus-5-5
  developer: $2.42, токенов 4522487 (input=76, output=21615, cache_write=139816, cache_read=4360980), провайдер claude, модель claude-opus-5-5
  reviewer: $1.05, токенов 1444432 (input=46, output=11473, cache_write=68444, cache_read=1364469), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 9 тест(ов), 0 manual, 0 skip
