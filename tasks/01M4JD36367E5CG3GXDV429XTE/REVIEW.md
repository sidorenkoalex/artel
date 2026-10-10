---
task: 01M4JD36367E5CG3GXDV429XTE
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: amend-tests и plank-run работают с планкой, импортирующей помощник `_pult.py`

## Что поменялось с итерации 1
Итерация 1 одобрила ветку на e803b034. После этого в ветку добавлен один
коммит — подтяжка main e8e4a054 (merge e803b034 + 1f3a0413) по ANSWER-1.
- `git diff 1f3a0413 e8e4a054 --stat` (merge против main) показывает ровно
  семь файлов задачи и больше ничего: `orchestrator/acceptance.py`,
  `amend.py`, `plank_run.py`, `tests/test_plank_run_edges.py`, два
  долгоживущих файла и `docs/codebase-map.md`. Значит, конфликт разрешён
  без посторонних правок, а изменения main перенесены как есть.
- Код и тесты задачи этим коммитом не менялись: `git diff e803b034 HEAD` по
  файлам задачи пустой (в коммите подтяжки только изменения из main и
  карта). Это соответствует ANSWER-1: «код и тесты задачи не менять».
- Подтянутый main (zone_lock, appendix_tree, advance_gates/acceptance и
  другие) не задевает узлы задачи: в его диффе по `orchestrator/` нет
  ни одного вхождения `PLANK_HELPER`, `_pult`, `plank_in_code_copy`,
  `materialize_`, `_tests_snapshot`, `drop_from_code_copy`.

## Фаза A — гейт плана
- Покрытие требований прежнее и полное: требования 1–4 — шаги 1–3,
  требование 5 — «—» (существующие методы `tests/` не меняются). Шаг 4
  честно описывает возврат по ANSWER-1 и называет прогон тестов задачи.
- «Влияние на систему» сходится с диффом. Путь отката — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | Без изменений с итерации 1: `acceptance.plank_helper_laid_out` оборачивает оба пути `_cmd_amend_tests`; `--from-branch` выкладывает через `plank_in_code_copy` → `materialize_from_branch`. AC-1…AC-3 зелёные на слитом дереве. |
| 2 | OK | `_is_plank_helper` исключает помощник из `_tests_snapshot` и `_artifact_tests_snapshot`. AC-4 и AC-5 зелёные. |
| 3 | OK | `plank_run._drift_from_ref` срабатывает до выкладки и fail-closed, если ссылка не прочитана. AC-6, AC-7 и углы `PlankRunDriftEdgesTest` зелёные. |
| 4 | OK | Сухой сбор в простом пути, разбор маркеров красноты прежний. AC-8 и AC-9 зелёные. |
| 5 | OK | Существующие утверждения `tests/` не тронуты: подтяжка не меняла тестов задачи, дифф `tests/test_plank_run_edges.py` относительно main — только новый класс. |

## Замечания
Замечаний уровня blocker, major или minor нет.

Наблюдение из итерации 1 остаётся в силе: `--from-branch` по-прежнему стирает незафиксированную
правку в рабочей копии. Это вне SPEC, оно вынесено в «Предложения системе» PLAN.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Реестр пуст: замечаний нет ни в итерации 1, ни в итерации 2.

## Вердикт
approved

## Проверено исполнением
- `git diff 1f3a0413 e8e4a054 --stat` — 7 файлов, все из задачи: merge не
  принёс посторонних правок.
- `git diff e803b034 HEAD -- orchestrator/acceptance.py orchestrator/amend.py orchestrator/plank_run.py tests/test_plank_run_edges.py tests/test_01m4jd36367e5cg3gxdv429xte_*.py`
  — пусто, код задачи после одобрения итерации 1 не менялся.
- `python3 scripts/codebase_map.py` (Python 3.13.12) + `git diff -- docs/codebase-map.md`
  без строк `built_at_sha` — расхождений нет, карта на слитом дереве свежая.
  Регенерацию откатил `git checkout`, `git status` чистый.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m4jd36367e5cg3gxdv429xte_amend_pult.py tests/test_01m4jd36367e5cg3gxdv429xte_plank_run_drift.py tests/test_plank_run_edges.py tests/test_01m42nbcadgsgtcbzb8nkbvdvh_amend_cleanup.py`
  — 21 passed, 4 subtests passed (56,6 с) на HEAD e8e4a054.
- `python3 /Users/al.sidorenko/projects/artel/orchestrator/artel.py plank-run 01M4JD36367E5CG3GXDV429XTE`
  — отказ «планки нет … нет файлов test_*.py». Это ожидаемо: зафиксированная
  планка задачи — только `long_lived.sha256.txt`, а её свойства держат
  долгоживущие файлы `tests/`, прогнанные выше.
- Временные мутации `plank_run.py` (три штуки, все тесты покраснели)
  выполнены в итерации 1 на том же коде. С тех пор код не менялся, поэтому
  повторно их не гонял.
- CI коммита e8e4a054 — зелёный (16 проверок, из пакета).

## Предложения системе
- Пакет ревью итерации 2 сообщает, что «базу сравнения … определить не
  удалось», и показывает полный дифф от main. Это вероятно потому, что
  итерация 1 уже стояла `approved` и вердикт был учтён. Для возврата после
  подтяжки main по ANSWER пакету стоит брать базой sha прошлого
  одобренного вердикта (здесь e803b034) и показывать дифф
  `<sha>..HEAD` без merge-части main
  (`orchestrator/` — сборка ревью-пакета).
