---
operator: Alexander Sidorenko
model: unknown
artel_sha: 8f5ee80ed80a6f967c8323471130ba958ba5d6a4
---

# RETRO: 01M6RJDRR027G50D81W8T3T8AK — Шаблон заголовка MR задачи внешнего проекта: policy.mr_title_template

Итог: done, sha 470cedc7def8d25a0a8df26802d72024263bcce3
Адрес артефактов: refs/artifacts/01M6RJDRR027G50D81W8T3T8AK
Суть: Шаблон заголовка MR задачи внешнего проекта: policy.mr_title_template — Заголовок MR задачи внешнего проекта сейчас собирается жёстко: `f"{task_id}: {t['title'] or task_id}"` — `orchestrator/github_adapter.py:186` (`gh pr create`) и `:441` (черновой MR через `forge.open_mr`, в том числе для GitLab).

Стоимость итого: $14.20
  analyst: $2.61, токенов 2139221 (input=50, output=16875, cache_write=236754, cache_read=1885542), провайдер claude, модель claude-opus-5-5
  spec_auditor: $5.24, токенов 7706590 (input=144, output=54158, cache_write=336030, cache_read=7316258), провайдер claude, модель claude-opus-5-5
  test_author: $3.08, токенов 5108821 (input=84, output=39395, cache_write=164154, cache_read=4905188), провайдер claude, модель claude-opus-5-5
  developer: $2.52, токенов 3507403 (input=66, output=16665, cache_write=190997, cache_read=3299675), провайдер claude, модель claude-opus-5-5
  reviewer: $0.76, токенов 707155 (input=22, output=7926, cache_write=58600, cache_read=640607), провайдер claude, модель claude-opus-5-5

Ревью: 0 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 0 тест(ов), 0 manual, 0 skip
