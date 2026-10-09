---
task: 01M4G8KPP8DVNBCPGCAPSVMAKZ
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Роль не пишет в главную копию пульта

# ТЗ: Роль не пишет в главную копию пульта — корень генератора карты и сторож после шага роли

Источник: строка бэклога «Роль не пишет в главную копию пульта»
(приоритет 1, решение Оператора 05.10); решение Оператора 09.10.2026 —
заводить параллельно с 01M4FYTB8QWJNHYCP35K8QC4E3, зоны сузить до
непересекающихся.

Факты (main af5e1111, сверка 09.10):
- 05.10 разработчик 01M46D5ZZQ запустил `python3 <worktree>/scripts/codebase_map.py`
  из каталога документов задачи `.artel/projects/artel/tasks/<id>`,
  который лежит внутри главной копии. `scripts/codebase_map.py::repo_root`
  (~304) берёт корень через `git rev-parse --show-toplevel` от текущего
  каталога (`main` ~349: `repo_root(Path.cwd())`) и переписал
  `docs/codebase-map.md` главной копии, а не рабочей копии задачи.
  Главная копия ~70 минут оставалась грязной незамеченной; `pin-update`
  отказал (`git merge --ff-only`), Оператор откатил файл вручную.
- Чекпоинты шага роли — `orchestrator/checkpoint.py`
  (`commit_timeout_checkpoint` ~152, `commit_abnormal_checkpoint`,
  `_wip_checkpoint` ~83); их зовёт `orchestrator/runner.py`
  (`_finish_timeout` ~1707, `_finish_failed` ~1731 и нормальное
  завершение). Алерты — `orchestrator/alerts.py::raise_alert` (~93).
- Родственный случай 08.10: шаг роли оставил пустой `.artel/state.db` в
  рабочей копии задачи — закрывается задачей
  01M4FYTB8QWJNHYCP35K8QC4E3, сюда не входит.

Требуется:
1. Генератор карты кода определяет корень по расположению самого
   сценария (дерево, в котором лежит вызванный `scripts/codebase_map.py`),
   а не по текущему каталогу: вызов сценария рабочей копии пишет только в
   рабочую копию, из какого бы каталога он ни был запущен.
2. Сторож пульта: после каждого шага роли (нормальное завершение,
   таймаут, сбой — в том же месте, где ставится чекпоинт шага) пульт
   сверяет рабочее дерево главной копии. Появились изменения, которых не
   было до шага (`git status` главной копии), — алерт Оператору в момент
   обнаружения: задача, роль, пути. Изменения, бывшие до шага, роли не
   приписываются. Сторож ничего не откатывает и не меняет состояние
   задачи.

Критерии приёмки (направление; планку пишет test_author):
- Генератор, вызванный из подкаталога другого git-репозитория, пишет
  карту в дерево сценария; дерево текущего каталога не меняется.
- Шаг роли, во время которого в главной копии появился изменённый файл,
  поднимает алерт с задачей, ролью и путём; шаг без таких изменений —
  без алерта; изменения, бывшие до шага, алерт не поднимают.
- Сторож срабатывает и на таймауте шага.

Зоны: scripts/codebase_map.py, orchestrator/checkpoint.py,
orchestrator/runner.py, orchestrator/alerts.py, docs/codebase-map.md,
tests/.

Только чтение (не менять): orchestrator/artel.py, orchestrator/store.py,
orchestrator/schema.py, orchestrator/acceptance.py, orchestrator/doctor/,
orchestrator/fsm.py, orchestrator/auto.py, orchestrator/lease.py,
orchestrator/providers/, docs/operator-session.md, docs/adr/,
docs/invariants.md, tests/test_invariants.py, AGENTS.md, CLAUDE.md,
docs/backlog.md, .artel/.

Не входит: лишняя база в рабочей копии задачи (01M4FYTB8QWJNHYCP35K8QC4E3);
запрет ролям запускать пульт из главной копии (права и песочница роли);
автоматический откат изменений главной копии.

Рамка: $40.

Набор моделей: по умолчанию.
