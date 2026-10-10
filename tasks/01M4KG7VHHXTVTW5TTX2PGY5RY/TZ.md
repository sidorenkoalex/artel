---
task: 01M4KG7VHHXTVTW5TTX2PGY5RY
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: suite-run доступен роли на Codex (песочница workspace-write)

# ТЗ: suite-run доступен роли на Codex (песочница workspace-write)

Источник: строка бэклога «suite-run доступен роли с любым провайдером»
(приоритет 1, анализ 07.10) и строка копилки 07.10 «Роль на Codex не может
запустить suite-run: PermissionError на .artel/logs/suite-run/lock.json»;
очередь критичных 10.10, пункт 6; решение Оператора 10.10.2026 — брать
после 01M4K2767FXKZ8EW7AME81SZ9N (слита 10.10).

Случаи: 06.10 — разработчик 01M49B90T1 («Предложения системе» PLAN) и
01M48WTP12 (эскалация: замер полного набора невозможен); 07.10 — A3.
Обход Оператора 07.10 — ручные прогоны во временных клонах.

Факты (main 71c0a6a9, сверка 10.10):
- Роль на Codex идёт под `codex exec --sandbox workspace-write`
  (`orchestrator/providers/codex.py`: `SANDBOX_MODE` ~133, сборка argv
  ~417): запись разрешена только в рабочий каталог шага и в каталог
  документов задачи (`--add-dir`, `ADD_DIR_FLAG` ~220).
- `suite-run` (`orchestrator/suite_run.py`) пишет замок полных прогонов
  машины `config.LOGS / "suite-run" / "lock.json"`
  (`orchestrator/suite_lock.py::path` ~38), своё хозяйство в
  `config.LOGS / "suite-run"` (~88) и логи `config.LOGS /
  "<id>-suite-run-<n>.log"` (~116) — всё в `.artel/logs/` главной копии,
  вне разрешённых корней песочницы → PermissionError.
- `suite-run` читает БД пульта (`store.db()`, ~429, ~608); после
  01M4K2767FXKZ8EW7AME81SZ9N полный прогон у предела пишет журнал задачи и
  алерт (`acceptance.run_full_suite`).
- Роль на Claude песочницы ОС не имеет и `suite-run` запускает (каталоги
  `.artel/logs/suite-run/` есть только от задач с ролями Claude).
- Защита главной копии: 01M4G8KPP8DVNBCPGCAPSVMAKZ — сторож пульта после
  шага сверяет рабочее дерево главной копии; песочница Codex — второй
  рубеж, его не ослаблять сверх нужного.

Требуется:
1. Роль на Codex запускает `suite-run <id>` (и `--failed`, `--wait`) из
   своего шага так же, как роль на Claude: прогон идёт под тем же замком
   машины, отчёт и лог доступны роли, итог тот же.
2. Песочница роли расширяется минимально: на запись открываются только
   каталоги, без которых `suite-run` не работает (замок и хозяйство
   `suite-run`, его логи). Рабочее дерево главной копии и БД пульта на
   запись роли не открываются. Если `suite-run` без записи в БД не
   обходится — запись в БД из процесса роли не должна валить прогон
   (итог прогона роль получает), а журнал задачи досылает процесс пульта;
   если и так нельзя — эскалация с вариантами, не расширение песочницы
   на `.artel/` целиком.
3. Поведение для ролей на Claude и для Оператора не меняется.
4. Ослабления нет: замок не обходится, пределы прогона те же, сторож
   главной копии и прочие ограничения песочницы Codex остаются.
5. Смена поведения существующих тестов — только разделом SPEC
   «Меняемое поведение» (инвариант 38).

Критерии приёмки (направление; планку пишет test_author):
- argv шага Codex несёт ровно нужные дополнительные корни записи (по
  одному `--add-dir` на каталог), рабочего дерева главной копии и
  каталога `.artel/` целиком среди них нет; мутация «каталог замка не
  выдан» ловится.
- `suite-run` в процессе без права записи в БД (подменённое открытие БД
  на запись) доводит прогон до итога и отчёта, сбой записи журнала не
  меняет итог.
- Замок: прогон из процесса роли и гейт пульта не идут одновременно
  (тот же файл замка).
- Шаг роли на Claude: argv и окружение прежние.

Зоны: orchestrator/providers/codex.py, orchestrator/suite_run.py,
orchestrator/suite_lock.py, docs/codebase-map.md, tests/.

Только чтение (не менять): orchestrator/acceptance.py, orchestrator/runner.py,
orchestrator/providers/claude.py, orchestrator/store.py, orchestrator/config.py,
orchestrator/checkpoint.py, orchestrator/liveness.py, orchestrator/notes.py,
orchestrator/fsm_advance.py, orchestrator/advance_gates/, scripts/,
.github/workflows/ci.yml, tests/test_invariants.py, docs/invariants.md,
docs/triggers.md, docs/adr/, docs/roadmap.md, docs/backlog.md,
docs/operator-session.md, templates/, skills/, CLAUDE.md, models.yaml,
model_sets.yaml, roles.yaml, targets.yaml, .artel/.

Не входит: зависание настоящего git в песочнице Codex (строка копилки
07.10, RealGitSandbox); изоляция ролей Claude песочницей ОС (строка
копилки 07.10 об асимметрии); выборочный прогон тестов; замер полного
набора с заданным числом рабочих; перевод ролей на Codex.

Рамка: $30.

Набор моделей: по умолчанию.
