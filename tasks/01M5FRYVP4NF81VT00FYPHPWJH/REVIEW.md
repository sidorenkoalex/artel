---
task: 01M5FRYVP4NF81VT00FYPHPWJH
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: G3а-2б-2: запрет повторов через плагины pytest и переносы из приёмок

## Фаза A — план
- Таблица покрытия полна: требования 1–11 → шаги 1–9; шаг 9 (сторожа R1-F1) добавлен к требованиям 1, 2, 5, 6, 8.
- «Влияние на систему» соответствует диффу: в итерации 2 добавлены только три новых файла `tests/`, код не менялся (инкрементальный diff c469fac4…HEAD — `tests/test_gate_owner_marker.py`, `tests/test_mandate_file_path_token.py`, `tests/test_report_argv_rerun_ban.py`).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `acceptance.py:763-766`; сторож — `tests/test_report_argv_rerun_ban.py::test_component_ban_right_after_command`, `::test_no_ban_outside_components` |
| 2 | OK | `acceptance.py:3212-3213`; сторож — `SuiteResultKeyRerunBanTest` (сверка с sha256 прежнего состава + поле) |
| 3 | OK | `targets.py:418-458`; долгоживущий `tests/test_01m5fryvp4nf81vt00fyphpwjh_rerun_ban_check.py` + `tests/test_targets_rerun_ban_wrapper.py` |
| 4 | OK | `fsm.py:1264-1268`, без изменений с итерации 1 |
| 5 | OK | `outcome_integrity.py:570-573`, `two_sided.py:455-463`; сторож — `GateMarkerBeforeWorktreeAddTest` (маркер читается в момент `worktree add`) |
| 6 | OK | `orphans.py:88-150`; сторож — `GateOrphanTempDirsTest`, `GateFixPruneTest` (настоящий git в клоне временного каталога, подмена `orchestrator.doctor.orphans._project_clones`) |
| 7 | OK | Без изменений; планка AC-9 зелёная |
| 8 | OK | `mandate.py:407, 514-518`; сторож — `tests/test_mandate_file_path_token.py` |
| 9 | OK | `refusal_classes.py:93, 132`; долгоживущий тест задачи |
| 10 | OK | `outcome_integrity.py:68-69`; долгоживущий тест задачи |
| 11 | OK | Дифф `tests/` — только новые файлы; существующие тесты не тронуты; новые тесты без сети и Node (git — локальный, во временном каталоге, с `GIT_CONFIG_GLOBAL=/dev/null`) |

Новые тесты не повторяют долгоживущие файлы задачи (те держат AC-4/13/14 и AC-11/12). Каждый метод несёт докстринг со сценарием и заявкой «Ловит мутацию: …»; заявки проверены временной мутацией (см. «Проверено исполнением»).

## Замечания

Нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | orchestrator/acceptance.py:766, :3213; orchestrator/advance_gates/mandate.py:514; orchestrator/doctor/orphans.py:88, :125, :136; orchestrator/advance_gates/outcome_integrity.py:570; orchestrator/advance_gates/two_sided.py:455 | Требования 1, 2, 5, 6, 8 закрыты только разовой планкой | После мержа откат проходил бы CI без сигнала | Закрыто: три файла `tests/` разработчика покрывают (а)–(д); 15 временных мутаций кода по всем пяти требованиям — все красят новые тесты (итерация 2) |

## Вердикт
approved — R1-F1 закрыто, код соответствует SPEC, дефектов не найдено.

## Проверено исполнением
- `python3 -m pytest -q -p no:cacheprovider -p no:xdist tests/test_gate_owner_marker.py tests/test_mandate_file_path_token.py tests/test_report_argv_rerun_ban.py` — 10 passed, 20 subtests.
- Временные мутации (скрипт через stdin, каждая мутация — замена строки, прогон соответствующего нового файла, возврат исходника; `git status` после — чист), все КРАСНЫЕ:
  - acceptance: `head += NO_RERUN_PLUGINS_ARGS` убран (1 failed); условие без `from_components` (2 failed); `data["no_rerun_plugins"] = True` убран (1 failed);
  - mandate: `fullmatch`→`search` (2 failed); без `(?::\d+)?` (1 failed); без `strip("*_")` (2 failed); возврат прежнего `in_weakening_scope(token.strip("*_"))` (4 failed);
  - outcome_integrity: маркер не пишется (1 failed); маркер с содержимым не pid (1 failed); two_sided: маркер не пишется (1 failed);
  - orphans: ветка выписок в `_temp_owner_alive` убрана (4 failed); `GATE_TEMP_PREFIXES` убраны из `_orphan_temp_dirs` (7 failed); prune всегда (1 failed); prune никогда (1 failed); prune через `doctor._project_clones` вместо имени модуля `orphans` (1 failed).
- `python3 …/artel.py plank-run 01M5FRYVP4NF81VT00FYPHPWJH` — 10 passed, код выхода 0.
- `python3 scripts/codebase_map.py` — расхождение с закоммиченной картой без строки `built_at_sha` пустое (файл восстановлен).
- CI коммита 63ad8f6e зелёный (из пакета, 16 проверок).

## Предложения системе
- Мутационную сверку заявок удобно гонять одним скриптом «список (файл, старое, новое, тест)» со stdin; запись во `/tmp` из шага роли требует подтверждения — команде пульта пригодился бы штатный `mutate-run` (orchestrator/artel.py).
