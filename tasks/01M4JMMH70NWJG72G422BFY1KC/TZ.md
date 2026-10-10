---
task: 01M4JMMH70NWJG72G422BFY1KC
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Регенерация карты под интерпретатором пульта, не голым python3

# ТЗ: Регенерация карты кодовой базы — под интерпретатором пульта, не голым `python3`

Источник: строка копилки 10.10 «Причина отказа авторазрешения карты у
01M4JD36367E5CG3GXDV429XTE установлена» (приоритет 1); решение Оператора
10.10.2026 — заводить.

Случай:
- 10.10 10:02Z: `approve` на merge_gate задачи 01M4JD36367E5CG3GXDV429XTE
  из сессии Codex ушёл в escalated «конфликт подтяжки … docs/codebase-map.md»,
  хотя конфликт только в карте, которую пульт разрешает регенерацией (так
  прошли подтяжки 01M4JD3SRN66SD6BM63XAGHB11 и этой же задачи из сессии
  Claude). Диагностика в окружении Codex: `python3` в PATH —
  `/usr/bin/python3` 3.9.6; `python3 scripts/codebase_map.py` падает
  `TypeError: unsupported operand type(s) for |: 'type' and 'NoneType'`
  (`scripts/codebase_map.py` ~251, аннотация `str | None`), код 1.

Факты (main, сверка 10.10):
- Пульт сам перезапускается под `.artel/venv/bin/python` при версии ниже
  `stack.REQUIRED_PYTHON` (3, 11) — `orchestrator/artel.py::_ensure_supported_interpreter`
  (~674); значит, `sys.executable` процесса пульта — пригодный
  интерпретатор.
- Голый `python3` в дочерних вызовах регенерации карты:
  `orchestrator/pull.py::_resolve_map_stage` (~322, авторазрешение
  конфликта подтяжки), `orchestrator/fsm_postmerge.py` (~92, регенерация
  после мержа), `orchestrator/brief.py` (~283). Сбой регенерации в
  `pull.py` молча закрывает авторазрешение (`_auto_resolve_conflict` →
  False) — причина в журнал не попадает.
- Прецедент правильного выбора интерпретатора: прогоны pytest —
  `stack.pytest_python_executable()` (`orchestrator/acceptance.py` ~37,
  ~61), `orchestrator/runner.py` ~897.

Требуется:
1. Все три вызова регенерации карты идут под интерпретатором процесса
   пульта (`sys.executable` или общий помощник пульта), не под `python3`
   из PATH; поведение при PATH с `python3` ниже 3.11 то же, что при
   пригодном.
2. Сбой регенерации или иного шага авторазрешения конфликта подтяжки
   (`pull._auto_resolve_conflict`) пишет в журнал задачи, какой шаг
   отказал, код возврата и хвост stderr (до 500 символов) — до
   эскалации, той же эскалацией, что сегодня (без ослабления).
3. Дочерних вызовов скриптов пульта голым `python3` в коде пульта не
   остаётся (кроме случаев, где это осознанно и названо в PLAN); тест
   держит это свойство.
4. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- PATH, в котором первым стоит подложный `python3`, падающий с кодом 1:
  конфликт подтяжки только в карте разрешается автоматически, эскалации
  нет; мутация «голый python3» — эскалация.
- То же для регенерации после мержа (`fsm_postmerge`) и `brief`.
- Регенерация, падающая по настоящей причине (скрипт карты сломан):
  эскалация, как сегодня, и запись журнала со ступенью, кодом и stderr.
- Тест-сторож: в коде пульта нет `subprocess`-вызовов со списком,
  начинающимся с `"python3"`, вне перечня исключений.

Зоны: orchestrator/pull.py, orchestrator/fsm_postmerge.py,
orchestrator/brief.py, docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/artel.py, orchestrator/stack.py,
orchestrator/acceptance.py, orchestrator/runner.py, orchestrator/liveness.py,
orchestrator/amend.py, orchestrator/plank_run.py, orchestrator/config.py,
scripts/, .github/workflows/ci.yml, tests/test_invariants.py,
docs/invariants.md, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, templates/, skills/, CLAUDE.md, models.yaml,
roles.yaml, targets.yaml, .artel/.

Не входит: совместимость `scripts/codebase_map.py` с Python 3.9 (пульт
требует 3.11+); окружение клиента Codex (PATH) — правило для Оператора, не
код; подсчёт членов группы процессов (01M4JJJF9SCR128A0XJPT2M7QX);
amend-tests (01M4JD36367E5CG3GXDV429XTE).

Рамка: $20.

Набор моделей: по умолчанию.
