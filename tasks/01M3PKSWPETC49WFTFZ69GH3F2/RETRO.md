---
operator: Alexander Sidorenko
model: unknown
artel_sha: 4c52ebd08ec447a1581eb7856a8324b0eef330f8
---

# RETRO: 01M3PKSWPETC49WFTFZ69GH3F2 — Канарейка исполняет код проверяемого коммита, а не код пина (ADR-0021, этап 0)

Итог: done, sha 4c52ebd08ec447a1581eb7856a8324b0eef330f8
Адрес артефактов: refs/artifacts/01M3PKSWPETC49WFTFZ69GH3F2
Суть: Канарейка исполняет код проверяемого коммита, а не код пина (ADR-0021, этап 0) — Канарейка (`orchestrator/canary.py`) клонирует пульт, переключает клон на проверяемый коммит (`target_sha`) и подменяет модульные атрибуты `config` (`_CLONE_CONFIG_ATTRS`) на пути клона, но заводит и ведёт учебную задачу в процессе пульта: `_run_task_in_ephemeral_clone` зовёт `catalog.cmd_new`, `workspace.ensure` и `_drive_task` (а с ним `auto.cmd_auto`, помощники гейтов, подъём потолка) — всё это код пина.

Стоимость итого: $16.65
  analyst: $0.93, токенов 692601 (input=18, output=9324, cache_write=78368, cache_read=604891), провайдер claude, модель claude-opus-5-5
  test_author: $6.36, токенов 11426879 (input=126, output=105411, cache_write=254355, cache_read=11066987), провайдер claude, модель claude-opus-5-5
  developer: $7.56, токенов 15241204 (input=178, output=85676, cache_write=360829, cache_read=14794521), провайдер claude, модель claude-opus-5-5
  reviewer: $1.80, токенов 1822337 (input=54, output=21456, cache_write=129222, cache_read=1671605), провайдер claude, модель claude-opus-5-5

Ревью: 1 итераций; приёмка: 0 отказ(ов)

Эскалации: нет

Приёмочные тесты: 20 тест(ов), 0 manual, 0 skip
