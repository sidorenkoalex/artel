---
task: 01M44ENW1B73Z80PR73HP1C9CG
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: answer отказывает на ключ вместо файла; approve эскалации «нужен шаг роли» без нового ANSWER — только с флагом `--no-answer`

## Подход

Три точки правки, все — в существующих местах разбора и перехода, без
нового состояния FSM.

1. **Разбор `answer` в диспетчере** (`orchestrator/artel.py`): новая
   функция `_answer_args(rest)` проверяет аргументы ДО вызова
   `answer.cmd_answer` — значит, до lease, журнала, чтения и коммита.
   Отказ (`sys.exit` с текстом) при: нет аргумента файла; второй
   аргумент начинается с «--»; файла по пути нет (`Path.is_file()`);
   аргументов после `answer` больше двух. Текст называет полученный
   аргумент (ключ/путь/лишние) и синтаксис
   `artel.py answer <id> <файл-с-ответом>`. Проверка не зависит от
   состояния задачи (оно не читается вовсе).
2. **Флаг `--no-answer` у `approve`** (`orchestrator/artel.py`):
   `NO_ANSWER_FLAG`; `_approve_sha_arg` пропускает его так же, как
   `--accept-red`/`--fixes-main`; диспетчер передаёт
   `no_answer=True` в `fsm.cmd_approve`.
3. **Проверка в `fsm.py`**:
   - `ROLE_STEP_REQUIRED_MARKERS` переезжает в `fsm.py` единым
     источником (`pull.PULL_CONFLICT_ROLE_STEP_MARKER`,
     `ARTIFACT_ESCALATION_ROLE_STEP_MARKER`);
     `auto._ROLE_STEP_REQUIRED_MARKERS` ссылается на него (значение
     прежнее) — определение термина SPEC и проверка approve не могут
     разойтись.
   - `unanswered_role_step_escalation(conn, task_id) -> str | None` —
     detail последней записи «state -> escalated», если после неё в
     журнале есть метка «нужен шаг роли» и нет записи, начинающейся с
     «ANSWER создан» (её пишут `answer` и `zones-extend`); иначе `None`.
     Записи «state -> escalated» нет — `None` (прежнее поведение).
     Дополнительно новым ANSWER считается файл, попавший в документы
     задачи мимо команд (ручной коммит): `ANSWER-*.md` больше, чем записей
     «ANSWER создан» ДО последней эскалации. Причина — существующие
     `tests/test_pull_conflict_marker_states.py` (`approve()` кладёт
     `ANSWER-n.md` без записи журнала: «Оператор ответил») и
     `tests/test_answer_gate.py` (то же для `answer_baseline`) иначе
     краснели бы; ответ, положенный файлом, — тоже ответ. AC-3 (старый
     ANSWER до эскалации не засчитывается) держится: старый файл
     сопровождён записью до эскалации, разность нулевая.
   - `_cmd_approve`: флаг вне `escalated` — именованный отказ (`sys.exit`
     «флаг --no-answer допустим только в состоянии escalated»), переход не
     выполняется; проверка стоит до сверки sha, чтобы отказ был
     одинаковым на любом состоянии.
   - `_approve_escalated(..., no_answer=False)`: прежняя сверка
     `answer_baseline` идёт ПЕРВОЙ и флагом не обходится (требование 4).
     Затем: эскалация с меткой без ANSWER после неё и без флага —
     журнал `fsm` «approve отклонён: нет ANSWER после эскалации» и
     печать текста (ANSWER после эскалации нет; `artel.py answer <id>
     <файл-с-ответом>`; `artel.py approve <id> --no-answer`), возврат
     без перехода (тем же приёмом, что прежний отказ baseline). С флагом —
     запись `operator` «эскалация снята без ответа» с detail эскалации,
     затем прежний переход с прежним текстом. Запись не начинается с
     «state -> » и не является меткой — `auto._role_step_since_state_entry`
     по-прежнему делает возврат анкером, шаг developer идёт до
     предварительного advance (AC-4).
4. **Подсказки** (`orchestrator/auto.py`, `orchestrator/config.py`):
   `config.AUTO_STOP_ESCALATED_ROLE_STEP` — подсказка для эскалации с
   меткой без ANSWER: команда `answer <id> <файл-с-ответом>` и
   `approve <id> --no-answer`, без голого `approve <id>`.
   `auto_stop_advice` в `escalated` (без потолка бюджета) выбирает её,
   когда `fsm.unanswered_role_step_escalation` не `None`; без метки —
   прежняя `AUTO_STOP["escalated"]`. Подсказка остановки серии
   конфликтов подтяжки (`_pre_advance_step`) — тот же текст через ту же
   константу (на этой остановке эскалация только что поднята, ответа
   после неё нет по построению).
5. **Справка и документ**: строка команд `approve … [--no-answer]`,
   абзац о флаге; абзацы `answer` — указание Оператора в
   `in_dev`/`review`, отказ на ключ/отсутствующий файл/лишние аргументы;
   абзац в `docs/operator-session.md`.

Бюджет SPEC ($25) не переоцениваю: объём совпадает с прогнозом SPEC.

## Шаги

1. `orchestrator/artel.py`: `_answer_args`, `NO_ANSWER_FLAG`,
   `_approve_sha_arg`, диспетчер, справка.
2. `orchestrator/fsm.py`: `ROLE_STEP_REQUIRED_MARKERS`,
   `unanswered_role_step_escalation`, `cmd_approve`/`_cmd_approve`/
   `_approve_escalated` с `no_answer`.
3. `orchestrator/auto.py`, `orchestrator/config.py`: подсказки.
4. `docs/operator-session.md`: абзац о флаге и журнале.
5. Тесты: долгоживущий файл задачи (не правится) + свой
   `tests/test_approve_no_answer_units.py` на свойства, которые он не
   держит: sha рядом с флагом в обоих порядках; «--no-answer» как
   основание `--accept-red` флагом не считается; каталог вместо файла
   у `answer` — отказ разбора; флаг на эскалации без метки не пишет
   записи «снята без ответа»; detail берётся из последней эскалации.
6. `python3 scripts/codebase_map.py`; прогон планки `plank-run`, тестов
   затронутых модулей; guard на PLAN.md.

## Покрытие требований

| Требование | Шаг |
|---|---|
| 1 | 1, 5 |
| 2 | 2, 5 |
| 3 | 1, 2, 5 |
| 4 | 2, 5 |
| 5 | 1, 2, 5 |
| 6 | 2, 5 |
| 7 | 3, 5 |
| 8 | 1, 4, 5 |
| 9 | 5 |

## Влияние на систему

- FSM: новых состояний и переходов нет; `escalated -> <возврат>`
  получает дополнительную ветку отказа и, при флаге, одну запись журнала
  перед прежним переходом. `tests/test_invariants.py` не затрагивается.
- Сверка `answer_baseline` не меняется и стоит раньше новой проверки —
  флаг её не обходит (требование 4, AC-5).
- `auto._ROLE_STEP_REQUIRED_MARKERS` сохраняет имя и значение (ссылка на
  `fsm.ROLE_STEP_REQUIRED_MARKERS`) — чтение меток и анкер рубежа
  переделки не меняются.
- Эскалации без метки (провал агента, лимиты, инциденты, merge_gate и
  др.) идут прежним путём: функция возвращает `None`.
- Канарейка (`canary.py::_pass_escalated_with_synthetic_answer`) и
  `budget` через `approve` не идут — не задеты.
- Существующие тесты не меняются; `test_cmd_approve_dispatch` проверяет
  позиционные аргументы обработчика — `partial(..., no_answer=…)` их не
  меняет.
- Откат — revert одного merge-коммита.

Проверено в шаге:
- долгоживущий `tests/test_01m44enw1b73z80pr73hp1c9cg_answer_args_no_answer.py`
  — 12 passed, 17 subtests; планка `plank-run` — 1 passed;
- свой `tests/test_approve_no_answer_units.py` — 5 тестов, каждый
  проверен временной мутацией из его «Ловит мутацию» (все красные,
  код возвращён);
- модули рядом (`test_cmd_approve_dispatch`, `test_approve_acceptance_full_suite`,
  `test_auto_escalated_return_rework_gate`, `test_artifact_escalation_marker`,
  `test_pull_conflict_marker_states`, `test_answer*`, `test_auto_cycle`,
  `test_runner_pre_step_pull`, `test_invariants`, `test_canary*`,
  `test_pull`, `test_git_fixation` и ещё ~50 модулей, импортирующих
  `fsm`/`auto`/`artel`) — зелёные, кроме 19 тестов
  `test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`/`test_main_ci_line.py`,
  которые зовут CLI `approve`/`pin-update` и в шаге роли получают отказ
  «команда недоступна процессу роли developer» (окружение шага, не
  правка; в CI окружения роли нет);
- карта регенерирована `python3 scripts/codebase_map.py`.

## Риски

- Скрипты/привычка Оператора `approve <id>` на конфликте подтяжки без
  ответа теперь получают отказ — это и есть цель; текст отказа называет
  оба выхода.
- `answer <id> <относительный путь>` проверяется относительно cwd — так
  же, как прежнее чтение файла в `answer._read_answer_file`.
- Засчёт ANSWER-файла без записи журнала: файл, положенный руками ДО
  эскалации без записи, засчитается как ответ на неё — редкий путь
  (ручной коммит ANSWER устарел с 01M287TPG0HAVXS8CHBCY679WN).

## Предложения системе

- Тесты, зовущие CLI-подпроцесс `artel.py approve`/`pin-update`
  (`tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py`,
  `tests/test_main_ci_line.py::FixesMainArgTest`), не снимают
  `ARTEL_ROLE` и в шаге роли всегда красные — роль не может прогнать их
  локально; песочнице стоит снимать признак роли так же, как это делает
  долгоживущий файл этой задачи (`mock.patch.dict(os.environ,
  {config.ARTEL_ROLE_ENV: ""})`).
