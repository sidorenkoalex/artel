---
task: 01M545EB0A9F191WTDSPCH36GA
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: D2-1: проектные скилы и меры для роли внешнего проекта

Родительская задача: 01M53B45XW3J56RJHGD70TD8A2 — D2: подключение внешнего проекта со стороны пульта — токен проекта, проектные скилы, проверки doctor, меры для роли
Зоны: orchestrator/brief.py, orchestrator/runner.py, orchestrator/providers/claude.py, orchestrator/providers/base.py, orchestrator/providers/codex.py, tests/
Порядок: первая, без зависимостей
Рамка: $25

Часть 1 задачи 01M53B45XW3J56RJHGD70TD8A2 (D2). Требования и критерии —
SPEC родителя: требования 5, 6 (без проверки `doctor`), 7, 10, 11, 12;
критерии AC-1 (бриф, окружение и белый список роли артели), AC-6, AC-7
(без пункта про `doctor`), AC-11.

1. `project_skills` записи проекта — имена скилов пульта
   (`skills/<имя>.md`). В бриф роли задачи этого проекта они добавляются
   после скилов из `roles.yaml`, в порядке поля.
2. Имя вне `skills/` или несуществующий файл — отказ сборки брифа. В
   тексте отказа названы проект, поле `project_skills` и скил.
   «Существующий файл» — файл на диске пульта (`config.ROOT/skills/<имя>.md`),
   один источник для брифа и `doctor`.
   `orchestrator/targets.py` не меняется: сломанное поле одного проекта
   не делает `targets.yaml` негодным. Проверку допустимости имени
   оформить так, чтобы её мог вызвать `doctor` (часть 2).
3. Для артели (`project_skills: []`) бриф роли не меняется.
4. Окружение роли задачи внешнего проекта содержит `GIT_CONFIG_NOSYSTEM=1`.
5. Белый список роли Claude для задачи внешнего проекта:
   `Bash(python3:*)` убирается, вместо него — только
   `Bash(python3 <абсолютный корень пульта>/orchestrator/artel.py:*)`;
   путь в правиле посимвольно равен строке миссий шага
   `config.ROOT / "orchestrator" / "artel.py"` (`orchestrator/role_prompt.py:238`,
   `orchestrator/knowledge_cards.py:953`). `Bash(git:*)` остаётся. Для артели белый список и окружение роли не
   меняются. Чтобы провайдер знал проект задачи, в
   `orchestrator/providers/base.py` и `orchestrator/providers/codex.py`
   меняется только сигнатура метода `command` (решение Оператора 17.10,
   О-4); поведение Codex не меняется.
6. Тесты детерминированы и не ходят в сеть.

Не входит: обходы через `git -c alias`/`core.fsmonitor` и через код,
исполняемый командами пульта, — принятый остаточный риск (ADR-0023,
вторая поправка, п.5). Правка `skills/`, `roles.yaml`, `targets.py` в эту
часть не входит.