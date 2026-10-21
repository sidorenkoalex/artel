---
task: 01M5FRYVP4NF81VT00FYPHPWJH
type: review
author_role: reviewer
status: changes_requested
iteration: 1
schema_version: 5
---

# REVIEW: G3а-2б-2: запрет повторов через плагины pytest и переносы из приёмок

## Фаза A — план
- Таблица покрытия полна: требования 1–11 → шаги 1–8.
- Шаги проверяемые, размер MR. Подход (общее условие `_bans_rerun_plugins` для argv и ключа, без импорта `in_outcome_bounds`) с архитектурой не конфликтует.
- «Влияние на систему» соответствует диффу: 9 файлов зоны + новый `tests/test_targets_rerun_ban_wrapper.py`; вне зоны ничего нет. Путь отката указан.
- Шаг 8 плана («тесты затронутых модулей») не закрывает требование долгоживущего сторожа — см. R1-F1.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `acceptance.py:763-766` — флаги дописываются к `head = list(profile.command)` до `extra`/`tail`; ветка Vitest и `_pytest_command` не тронуты. Условие `_bans_rerun_plugins` (`acceptance.py:728`) = `reported` ∧ `from_components` (+ не Vitest, + pytest), импорт внутри функции. Сторожа в `tests/` нет — R1-F1 |
| 2 | OK | `acceptance.py:3211-3213`, поле ставится только по тому же условию. Сторожа в `tests/` нет — R1-F1 |
| 3 | OK | `targets.py:418-458`: равенство и префикс `flag=`, пара `-p`/имя и слитная `-p<имя>` со `strip()`, `shlex.split` с переводом `ValueError` в `TargetsError` «PYTEST_ADDOPTS не разбирается», `PYTEST_PLUGINS` по запятой со `strip`. Вызывается только из `_check_components` — `test_profile` не проверяется. Обёртка не проверяется (граница «Не входит»). Хвостовой `-p` — без `IndexError` |
| 4 | OK | `fsm.py:1264-1268` — импорт внутри функции, литерала нет; `auto.py` не тронут |
| 5 | OK | `outcome_integrity.py:570-573` (внутри `try`, сбой записи → отказ подготовки через `except Exception`), `two_sided.py:455-463` (сбой → `_failed`); оба до `worktree add`, при любом профиле. Сторожа в `tests/` нет — R1-F1 |
| 6 | OK | `orphans.py:88-93` — ветка выписок до маркера канарейки; префиксы в `_orphan_temp_dirs`; prune в каждом `_project_clones()` (имя модуля) только при `gate_removed`. Сторожа в `tests/` нет — R1-F1 |
| 7 | OK | Ветка вне границы не менялась; планка AC-9 зелёная |
| 8 | OK | `mandate.py:404-407, 514-518` — `fullmatch` после `strip("*_")`, `_TOKEN_SPLIT_RE` и правило `*.py` прежние. Сторожа в `tests/` нет — R1-F1 |
| 9 | OK | `refusal_classes.py:93, 132` |
| 10 | OK | `outcome_integrity.py:68-69`; `refusal_classes` без импортов пакета (долгоживущий тест зелёный) |
| 11 | OK | Существующие тесты не правились (в диффе `tests/` только новый файл); тесты детерминированы, без сети и Node |

## Замечания

- major — orchestrator/acceptance.py:766, :3213; orchestrator/advance_gates/mandate.py:514-518; orchestrator/doctor/orphans.py:88-93, :125-126, :136-150; orchestrator/advance_gates/outcome_integrity.py:570-573; orchestrator/advance_gates/two_sided.py:455-463 — **ядро задачи после мержа без сторожа в `tests/`** (ADR-0018 п. 3, review-checklist «Долгоживущие свойства — в `tests/`»). Все четыре файла планки помечены `Группа: разовый` (`test_report_argv_rerun_ban.py`, `test_gate_owner_marker.py`, `test_mandate_coverage_bounds.py`, `test_spec_gate_detail.py`); долгоживущие файлы задачи держат только AC-4/13/14 и AC-11/12; разработчик добавил в `tests/` только `test_targets_rerun_ban_wrapper.py` (граница обёртки). Временной мутацией проверено: убраны `head += NO_RERUN_PLUGINS_ARGS` и `data["no_rerun_plugins"] = True`, `_component_covered` возвращён к прежнему `any(profile.in_weakening_scope(token.strip("*_")) …)`, `*GATE_TEMP_PREFIXES` убраны из `_orphan_temp_dirs` — 9 файлов `tests/` этих модулей (`test_component_report_gates`, `test_01m59z0fw1699sjq2fa5y76cz3_component_plank_layout`, `test_01m4nz5qrb7mneycwgxewvwfp0_mandate_matrix`, `test_01m55vdvvdvww2mtj01f88n5fm_weakening_mandate_scope`, `test_mandate_profile_scope`, `test_mandate_matrix_form`, `test_mandate_test_id`, `test_canary_doctor_owner`, `test_doctor_closed_ref_fix`) — 76 passed, ни одного красного. Сценарий: любая будущая правка `_report_argv` (рефакторинг ветки `else`) или `_component_covered` молча возвращает повторы в прогон компонента / широкое признание «Чем покрыто после», и CI зелёный — главное свойство ADR-0026 п. 4 теряется без сигнала. Ограничение ADR-0020 о закрытых именах касается долгоживущих файлов test_author, не тестов разработчика в `tests/` (ср. существующие `tests/test_component_report_gates.py`, `tests/test_canary_doctor_owner.py`, работающие с закрытыми именами). Предложение: добавить в `tests/` (не повторяя долгоживущие файлы задачи) тесты с заявками «Ловит мутацию: …» минимум на: (а) флаги `-p no:rerunfailures -p no:flaky` сразу за `command` у компонента с `report` и их отсутствие у артели/`test_profile` (требование 1); (б) поле `no_rerun_plugins` ключа итога (требование 2); (в) маркер `.artel-gate-owner` до `worktree add` в `_gate` и `two_sided.run` (требование 5); (г) сирота `artel-outcome-*`/`artel-two-sided-*` без маркера гейта / с живым маркером канарейки и prune только при удалении (требование 6); (д) отказ «`src/`», «src/**», «src/a.test.ts::x», «src/a.test.ts.» при профиле в границе (требование 8). Перенос 11 (литерал в `fsm.py`) и 9–10 сторожем уже закрыты/поведенчески нейтральны — не обязательно.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | fixed | orchestrator/acceptance.py:766, :3213; orchestrator/advance_gates/mandate.py:514; orchestrator/doctor/orphans.py:88, :125, :136; orchestrator/advance_gates/outcome_integrity.py:570; orchestrator/advance_gates/two_sided.py:455 | Требования 1, 2, 5, 6, 8 закрыты только разовой планкой; временная мутация всех пяти оставляет `tests/` зелёными | После мержа откат запрета повторов, сужения мандата или уборки выписок проходит CI без сигнала | Добавить в `tests/` тесты разработчика на (а)–(д) из «Замечаний» с заявками «Ловит мутацию: …», проверенные временной мутацией. Разметка разработчика, итерация 2 — fixed: добавлены `tests/test_report_argv_rerun_ban.py` (а, б: флаги сразу за `command` в полном наборе и подмножестве, их отсутствие у артели/`test_profile`, поле `no_rerun_plugins` ключа), `tests/test_gate_owner_marker.py` (в: маркер до `worktree add` в `_gate` при профиле артели и в `two_sided.run`; г: сирота без маркера/мёртвый pid/только маркер канарейки, живой маркер гейта защищает, prune убирает запись мёртвой выписки через подменённый `_project_clones`, без удалённых выписок git не зовётся), `tests/test_mandate_file_path_token.py` (д: отказ «`src/`», «src/**», «::x», «.», вне области; признание токена, `:12`, выделения, `*.py`, id компонента). Каждая заявка проверена временной мутацией — 12 мутаций кода, все красные, код возвращён `git checkout` |

## Вердикт
changes_requested — закрыть R1-F1: долгоживущие тесты разработчика в `tests/` на требования 1, 2, 5, 6, 8. Код по существу соответствует SPEC, дефектов корректности не найдено.

## Проверено исполнением
- `python3 …/artel.py plank-run 01M5FRYVP4NF81VT00FYPHPWJH` — 10 passed, код выхода 0.
- `python3 -m pytest -q -p no:cacheprovider -p no:xdist tests/test_01m5fryvp4nf81vt00fyphpwjh_outcome_action_texts.py tests/test_01m5fryvp4nf81vt00fyphpwjh_rerun_ban_check.py tests/test_targets_rerun_ban_wrapper.py tests/test_01m5aa5ts90rdj2afxb882wtpd_labelled_gates.py tests/test_01m5cjvb5b5v55pqqvr2qrhwzn_outcome_gate.py` — 59 passed, 223 subtests.
- Временная мутация (см. R1-F1) + прогон 9 файлов `tests/` с `-p no:xdist` — 76 passed, 182 subtests: мутации не пойманы. Код возвращён `git checkout -- orchestrator`, `git status` чист.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой только в строке `built_at_sha` (файл восстановлен).
- `pytest -n 4` со списком файлов — «node down», тесты не шли (не используется как довод).

## Предложения системе
- Планка, где все файлы — `Группа: разовый` из-за закрытых имён (ADR-0020), оставляет ядро задачи без сторожа, и ни шаблон PLAN, ни шаг разработчика этого не напоминают — стоит, чтобы бриф разработчика перечислял AC, закрытые только разовой планкой (skills/test-authoring.md / orchestrator/brief.py).
