---
task: 01M2DTT96FS25SHXP0HDTWARQH
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: Модель роли из roles.yaml: флаг --model в команде запуска и модель в журнале шага

Источник: бэклог docs/backlog.md, строка «Явная модель роли, своя в каждом
пульте» (П2, $70, решения Оператора 06.09) — эта задача выделяет из неё
ПЕРВЫЙ слой, минимальный и срочный. Решение Оператора 13.09: приоритетно,
до утверждения состава волны 5. Копилка 06.09: «Модель ролей никем не
выбрана: все шаги всех ролей идут на Sonnet 5 (100 % событий с 28.08)».

Факты:
- `runner.role_cmd` (orchestrator/runner.py:~773–785) собирает команду
  `claude -p --permission-mode acceptEdits … --allowedTools …` без флага
  модели; `ANTHROPIC_MODEL` в окружении роли (`role_env`) не задаётся;
  `model` в docs/reference/role-home/claude/settings.json нет. Процесс
  роли аутентифицирован токеном без кэша аккаунта, CLI берёт дефолт
  Sonnet 5.
- roles.yaml (защищённый путь, `config.PROTECTED_PATHS`) читается
  `orchestrator/roles.py` (`load()` через `yamlmini.mapping`, `skills()`
  и др.); у agent-ролей поля модели нет.
- Журнал шага: `agent run started` (runner.py:~938) несёт попытку, лог,
  промпт, окружение (python/git/claude), модель — нет.
- Данные недели 06–13.09 (анализ Оператора 13.09): developer — 70 % задач
  с повторным шагом, переделки $461/нед.; reviewer — 5 промахов на 68
  задач, шаг $2; test_author 21 %, analyst 8 %. Решение Оператора: Opus 5
  для developer и reviewer, остальные на Sonnet 5 явно.

Требуется:
1. roles.yaml: у каждой agent-роли (analyst, test_author, developer,
   reviewer) необязательное поле `model` — точный идентификатор модели
   CLI (например `claude-opus-5`, `claude-sonnet-5`). Правка roles.yaml —
   ТОЛЬКО приложением unified diff к PLAN.md (защищённый путь, применит
   Оператор): developer и reviewer — `claude-opus-5`, analyst и
   test_author — `claude-sonnet-5`.
2. `orchestrator/roles.py`: функция `model(role) -> str | None` — значение
   поля, `None` если не задано; нечитаемое значение (не строка, пустая
   строка) — `RolesError` тем же приёмом, что у скилов.
3. `runner.role_cmd` (или место сборки argv шага): если `roles.model(role)`
   задан — в команду добавляется `--model <идентификатор>`; если не задан —
   команда как сегодня (без флага), но в журнал шага пишется
   предупреждение «модель роли не задана — дефолт CLI» одной записью на
   шаг (не остановка: слой fail-closed — следующая задача из строки $70).
4. Журнал: запись `agent run started` несёт `model=<идентификатор|дефолт CLI>`;
   записи `agent cost KNOWN/PARTIAL` — тот же `model=` (для будущей
   группировки стоимости по модели).
5. `status`/`report` не меняются (вне рамки). Канарейка использует тот
   же runner — модель ролей применяется и к синтетическим задачам
   автоматически, отдельной правки canary.py не требуется; проверить,
   что прогон канарейки не ломается отсутствием поля.
6. Тесты (tests/): roles.model читает поле и None; RolesError на мусоре;
   role_cmd с полем несёт `--model X` ровно один раз и в прежнем порядке
   остальных флагов; без поля — флага нет и есть запись предупреждения;
   `agent run started` содержит `model=`. Существующие тесты runner
   (101 патч по именам модуля) без изменения ассертов.

Зоны: orchestrator/runner.py, orchestrator/roles.py, tests/.

Приложением: roles.yaml (unified diff в PLAN.md — защищённый путь),
docs/reference/role-home/claude/settings.json (не трогать: модель задаётся
флагом, не настройками дома), orchestrator/canary.py (только сверка, что
работает без правок).

Не входит: ярусы model_tier и локальное отображение `.artel/models.yaml`;
тарифы по модели и группировка `report`; fail-closed отказ без модели;
переопределитель на задачу (отклонён 06.09); бейзлайны канарейки по
набору моделей. Всё это — остаток строки бэклога $70.

Рамка: $20.
