---
task: 01M1SAA01YRRTWAVADT2F81RRQ
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 4
---

# REVIEW: посторонние файлы в каталоге планки не попадают в артефактную ветку

## Соответствие SPEC

| Требование/AC | Вердикт | Комментарий |
|---|---|---|
| Требование 1 (checkpoint фильтрует посторонние) | OK | `_is_stray_acceptance_test_file` + фильтр в `_commit_external_step_artifacts` (orchestrator/checkpoint.py) — без изменений с итерации 1, повторно перепроверено на текущем дереве. |
| Требование 2 (guard именует нарушение) | OK | `is_extraneous_acceptance_test_file`/`scan_extraneous_acceptance_files` в обоих режимах `main()` (scripts/guard.py) — без изменений с итерации 1. |
| Требование 3 (codebase_map пишет в корень) | OK | `repo_root()` через `git rev-parse --show-toplevel` (scripts/codebase_map.py) — без изменений с итерации 1. |
| AC-1..AC-8 | OK | Все критерии приёмки покрыты залоченной планкой `tasks/01M1SAA01YRRTWAVADT2F81RRQ/acceptance_tests/` (не тронута с итерации 1, сверено `git diff` между коммитом test_author и текущим HEAD — пусто) — 11 тестов/41 subtest зелёные. |
| Требование 5 / AC-5 итерации 1 (докстринг «Ловит мутацию» в новых `tests/*.py`) | OK (закрыто в этой итерации) | Единственное замечание прошлой итерации (R1-F1) исправлено коммитом `dbf2adb2` — см. «Реестр замечаний». |

## Замечания

Пусто — единственное замечание прошлой итерации (R1-F1) закрыто, новых
блокеров/major/minor не найдено.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_checkpoint_stray_acceptance_files.py (5 методов); tests/test_guard_extraneous_acceptance_files.py (7 методов); tests/test_codebase_map.py::RepoRootTest (2 метода) | 14 новых unit-тестовых методов без докстринга `Ловит мутацию: …` | нарушение конвенции test-authoring.md — при регрессии тестового намерения не восстановить его из докстринга | Проверено построчно (`git show dbf2adb2` — диф трёх файлов): все 14 методов несут докстринг `Ловит мутацию: <конкретная мутация> → <что наблюдаемо ломается>`, конкретны (называют именно ослабляемую проверку — расширение, глубину пути, префикс, подавление исключения git-процесса и т.п.), не пересказывают имя метода. Логика тестов при этом не менялась (диф — только добавление docstring-строк, тела методов и ассерты идентичны). Прогон `pytest tests/test_checkpoint_stray_acceptance_files.py tests/test_guard_extraneous_acceptance_files.py tests/test_codebase_map.py` — 26/26 (24 subtests) зелёных. Закрыто. |

## Вердикт

approved

## Проверено исполнением

- Инкрементальный diff пакета (от sha предыдущего вердикта `dbf2adb2` до HEAD `500e7518`) оказался бесполезен для ревью: `dbf2adb2` — это сам коммит-фикс R1-F1 этой задачи, а два коммита после него — «подтяжка main» (слияние с main, принёсшее ЦЕЛИКОМ чужую задачу 01M1RGQV4DG2FX1B90W4EEETTR — report.py/config.py/её артефакты — не имеющую отношения к SPEC этой задачи). SPEC.md/PLAN.md этой задачи пакетом тоже не были показаны («не показан» и в ветке, и в дереве — они материализуются из артефактной ветки `artifact/01m1saa01yrrtwavadt2f81rrq`, не из кодовой). Восстановил контекст вручную:
  - `git log --oneline -20` / `git merge-base main <ветка>` — merge-base с main совпадает с текущим тупиком слияний ветки (main не разошёлся дальше того, что уже подтянуто, за вычетом одного свежего коммита `cc5b8241`, не влияющего на эту задачу);
  - `git show artifact/01m1saa01yrrtwavadt2f81rrq:tasks/01M1SAA01YRRTWAVADT2F81RRQ/{SPEC,PLAN,REVIEW}.md` — прочитал реальные SPEC/PLAN/REVIEW(it1) с артефактной ветки;
  - `git diff main...task/01m1saa01yrrtwavadt2f81rrq-postoronnie-fayly-v-kataloge-p --stat -- . ':(exclude)tasks/'` — реальный (не инкрементальный) diff ветки относительно main: РОВНО зона SPEC (`orchestrator/checkpoint.py`, `scripts/guard.py`, `scripts/codebase_map.py`, три файла `tests/`, регенерация `docs/codebase-map.md`), 7 файлов — никаких посторонних файлов чужих задач в фактическом diff ветки нет (весь шум от «подтяжки main» уже растворился в main, ветка и main сошлись).
- `git show dbf2adb2 -- tests/test_checkpoint_stray_acceptance_files.py tests/test_codebase_map.py tests/test_guard_extraneous_acceptance_files.py` — построчно подтвердил: фикс R1-F1 — чистое добавление докстрингов, ни один ассерт/тело метода не изменено.
- `python3 -m pytest tests/test_checkpoint_stray_acceptance_files.py tests/test_guard_extraneous_acceptance_files.py tests/test_codebase_map.py -q` — 26 тестов (24 subtests), все зелёные.
- `python3 -m pytest tasks/01M1SAA01YRRTWAVADT2F81RRQ/acceptance_tests/ -q` — 11 тестов (41 subtest), все зелёные; `git diff` между коммитом test_author и текущим HEAD по этому каталогу — пусто, планка не менялась с итерации 1.
- `python3 -m pytest tests/test_checkpoint_external_step_artifacts.py tests/test_guard_artifact_branch_mode.py tests/test_guard_schema.py tests/test_guard_split_signals.py tests/test_guard_zones.py tests/test_id_format_guard.py tests/test_step_autocommit.py tests/test_timeout_checkpoint.py -q` — 161 тест (32 subtests), все зелёные (AC-8, существующие зональные тесты не ослаблены).
- `python3 scripts/guard.py --all` — «GUARD: ок (513 файлов)»; `python3 scripts/guard.py --all --artifact-branch` — «сдано 402 / черновиков 111 / нарушений 0» на реальном дереве пульта: новое правило по-прежнему не красит ни одну существующую задачу.
- Регенерация карты (`python3 scripts/codebase_map.py`, сверка построчным diff без `built_at_sha`) — содержимое совпадает с закоммиченным `docs/codebase-map.md` (расхождение только в `built_at_sha`, ожидаемое отставание — не дефект); working tree после проверки восстановлен `git checkout -- docs/codebase-map.md`.

## Предложения системе

- Тот же класс, что уже отмечен ревью 01M1RGQV4DG2FX1B90W4EEETTR (см. память): генератор ревью-пакета берёт sha предыдущего вердикта буквально и строит инкрементальный diff от него до HEAD, не учитывая, что между вердиктом и HEAD могли лечь коммиты «подтяжка main» — тогда показанный diff и SPEC/PLAN «не показаны» вводят в заблуждение вместо помощи. Стоит явно включить этот сценарий (fix-коммит роли сразу после которого следует ≥1 merge main) в область фикса регрессии по инкрементальному diff.
