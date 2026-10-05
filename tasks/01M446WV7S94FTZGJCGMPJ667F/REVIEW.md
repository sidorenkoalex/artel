---
task: 01M446WV7S94FTZGJCGMPJ667F
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Клон проекта получает ссылки документов задач; doctor не шумит на свежем клоне

## Фаза A — план
- Таблица покрытия полна: тр. 1–2 — код + долгоживущий
  `tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py` (AC-1…AC-5),
  тр. 3–4 — код + `tests/test_doctor_closed_ref_fix.py` (AC-6…AC-8), тр. 5 —
  заявки «Ловит мутацию» во всех новых методах `tests/`.
- Шаги размера одного MR; подход (ленивый импорт, тот же узел
  `fetch_all_from_origin`, push без force) с архитектурой не конфликтует.
- «Влияние на систему» соответствует диффу: 3 модуля кода, 2 новых файла
  тестов, карта. Существующие тесты не тронуты (`git diff 09c724f9 -- tests/`
  — только новые файлы). Откат — revert merge.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `workspace.py:121` — `_fetch_docs_refs` только в ветке заведения клона, после `git clone`/хуков/идентичности; узел `artifact_branch.fetch_all_from_origin` (сдвиг только вперёд); неудача — одна строка, исход `(clone, None)`. Ветка «каталог уже есть» не изменена (AC-2 зелёный). |
| 2 | OK | `artifact_branches.py:216-218` — `not local and remote == closing` считается и не даёт проблемы; `_only_in_origin_summary` — одна `ok`-строка с числом и `artel.py docs --fetch-all`, добавляется и к `warn`, и к `skip`, и к итоговой `ok`. Прочие случаи — прежний `_closed_ref_problem` (`warn`). |
| 3 | OK | `_fix_unsent_closed_ref`: объект в клоне → прежнее правило; нет → поиск в `config.ROOT` только для `DEFAULT_TARGET`, push `<sha>:refs/artifacts/<id>` без `+`; отказ → `[FIX]` с id и stderr; объекта нигде нет / внешний проект → `[FIX]` с id и коммитом закрытия. «origin = коммиту закрытия → ничего» сохранено (`artifact_branches.py:166`). |
| 4 | OK | `cli.py:161` — `_fix_project_clones` перед `_fix_unsent_closed_refs`, оба до `all_checks`. |
| 5 | OK | Заявки «Ловит мутацию» есть у всех новых методов; две из них подтверждены временной мутацией (см. ниже). |

## Замечания

Замечаний уровня blocker/major/minor, требующих итерации, нет. Наблюдения
без требования правки — в разделе «Вердикт».

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет.

## Вердикт

approved.

Наблюдения (не требуют итерации, на усмотрение):
- `orchestrator/doctor/artifact_branches.py:131-132` — новая ветка «объект
  в клоне есть, локальной ссылки нет → досылка sha из клона» ни одним
  тестом не охраняется: временная мутация (тело ветки заменено на `pass`)
  оставила зелёными `test_doctor_closed_ref_fix`, долгоживущий файл задачи,
  `test_artifact_ref_sync`, `test_doctor_artifact_branch_sync`, `test_doctor`
  (146 passed). SPEC этот случай отдельно не требует (прежнее поведение —
  молчаливый пропуск; «голова есть и ≠ закрытию — не досылать» сохранено),
  push без force, поэтому не major; при случае — тест на эту ветку.
- `orchestrator/workspace.py:135-139` — проверка «каталога клона нет после
  успешного `git clone`» существует только ради заглушки git песочницы
  (`TargetSourcedRemoteTest` берёт `fetch_calls[0]`); с настоящим git ветка
  мёртвая. Вреда нет, правка существующего теста была бы рискованнее;
  `tests/test_workspace_clone_docs_refs.py` — докстринг метода состоит из
  одной заявки, сценарий описан в докстринге модуля.

## Проверено исполнением
- `python3 …/orchestrator/artel.py plank-run 01M446WV7S94FTZGJCGMPJ667F` —
  5 passed, код выхода 0.
- `python3 -m pytest -q tests/test_doctor_closed_ref_fix.py
  tests/test_workspace_clone_docs_refs.py
  tests/test_01m446wv7s94ftzgjcgmpj667f_clone_refs.py
  tests/test_artifact_ref_sync.py tests/test_doctor_artifact_branch_sync.py
  tests/test_workspace.py tests/test_branch_freshness_gate.py
  tests/test_docs_fetch_edges.py` — 74 passed.
- Временная мутация 1: в `_fix_unsent_closed_ref` снято условие «задача
  артели» перед поиском в главной копии →
  `test_external_project_does_not_search_main_copy` красный (1 failed,
  4 passed); код возвращён.
- Временная мутация 2: ветка `elif not local` → `pass` — 146 passed по
  пяти модулям doctor/ref-sync (см. наблюдение выше); код возвращён.
- `git status --short` после мутаций — пусто (дерево чистое).
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  без строки `built_at_sha` — расхождений нет (карта свежая), регенерация
  откачена `git checkout`.
- `git diff 09c724f9 -- tests/ --stat` — только новые файлы, существующие
  утверждения не тронуты.

## Предложения системе
- Гейт реестра (`approved` только при всех `accepted`) не оставляет места
  для minor-наблюдений «на усмотрение»: их приходится выносить из
  «Замечаний» в текст вердикта. Стоит либо разрешить `minor` со статусом
  вроде `wontfix`, либо явно описать в review-checklist, куда писать
  неблокирующие наблюдения.
