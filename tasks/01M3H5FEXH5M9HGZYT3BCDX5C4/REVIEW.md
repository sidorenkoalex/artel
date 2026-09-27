---
task: 01M3H5FEXH5M9HGZYT3BCDX5C4
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Тесты манифеста стека не зависят от ярусов настоящего roles.yaml

## Фаза A: гейт плана

1. **Покрытие SPEC полно.** Таблицы PLAN несут все шесть требований и все
   пять критериев; шагов два, каждый — проверяемая единица (шаг 1 —
   помощник плюс перевод трёх песочниц, шаг 2 — регрессионный файл).
   Микрооперациями шаги не дроблены, «сделать всё» одним пунктом нет.
2. **Требование 5 проверил не по слову PLAN, а грепом.** Перечень
   потребителей в PLAN сходится с фактом: свой локальный слой поверх
   НАСТОЯЩЕЙ карты исполнителей пишут ровно три файла (сейчас
   `tests/test_runner_role_model.py:144`,
   `tests/test_runner_model_preflight.py:155`,
   `tests/test_stack_optional_tools.py:114`), остальные писатели
   `config.MODELS_LOCAL` (`tests/test_models_doctor.py:73`,
   `tests/test_canary_sets.py:130`, `tests/test_stack.py:514`,
   `tests/test_model_tariffs.py:113`) кладут рядом СВОЙ синтетический
   `roles.yaml` и от ярусов боевого файла не зависят вовсе.
   `tests/test_providers.py` берёт `_roles_yaml_text`, но слой не пишет —
   остаётся на шаблонном (все ярусы). Пропущенных экземпляров класса нет.
3. **Конвенциям и архитектуре подход не противоречит.** Зона — только
   `tests/`; защищённые пути (`roles.yaml`, `skills/`, `gates.yaml`,
   `.github/`) в диффе отсутствуют; карта кодовой базы регенерирована тем
   же коммитом. Отказ от второго варианта ТЗ обоснован в PLAN и
   подтверждается кодом: `tests/test_providers.py:499` действительно
   передаёт вторым аргументом `_roles_yaml_text` идентификатор модели, а
   не ярус.

Замечаний по плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `tests/test_runner_role_model.py:70` `_tiers_text(model)` называет модель у каждого яруса `models.TIERS`; на него переведены все три песочницы, пишущие слой поверх боевой карты (`test_runner_role_model.py:144`, `test_runner_model_preflight.py:155`, `test_stack_optional_tools.py:114`). Перечень не продублирован литералом — идёт из `models.TIERS`, и это свойство держит отдельный тест. |
| 2 | OK | Обоснование в PLAN «Подход» повторяет четыре аргумента SPEC и добавляет проверяемый: `tests/test_providers.py:499`. Кода требование не касается. |
| 3 | OK | Оба сценария-исключения не тронуты по существу: `test_runner_model_preflight.py:393` по-прежнему пишет слой одним ярусом `cheap` поверх `set_model`, `test_stack_optional_tools.py:183` — `tiers:\n  cheap: nothing`. У каждого дописана причина, почему однорядный слой намеренный. Чувствительность сохранена: мутация «цепочка берёт не ярус роли» (подмена `roles.model_tier` на `models.TIERS[-1]`) валит `TierWithoutModelTest::test_step_refuses_before_the_agent` — см. «Проверено исполнением». |
| 4 | OK | Ни один `assert` и ни один сценарий в диффе `tests/` не изменён и не удалён — правки касаются только записи слоя, докстрингов и снятого параметра `tier` у `set_tier_model`. Число тестовых методов прежнее (8/15/15 по `guard.qualified_test_methods` против базы `6fd97017`), маркеров пропуска нет ни одного. Проверил и то, что покрытие всех ярусов одной моделью не увело различающую силу из набора целиком: мутация «читается не тот ярус» ловится в пяти местах (`test_runner_model_preflight.py`, `test_stack.py` ×4, `test_models_doctor.py`) плюс новым файлом. |
| 5 | OK | См. пункт 2 Фазы A: перечень PLAN сверен грепом по `tests/`, пропусков нет. |
| 6 | OK | `tests/test_stack_roles_tier_spread.py` ставит карту с одной agent-ролью на свободном ярусе `models.TIERS` и проверяет не только отсутствие `fail`, но и наличие зелёной строки на КАЖДУЮ agent-роль — отсутствие строки тоже не было бы `fail`. Ярус-одиночка вычисляется от боевого файла, литералом не прибит. |

| Критерий | Вердикт | Комментарий |
|---|---|---|
| AC-1 | OK | Планка `test_ac1_*` (прогон `test_stack_optional_tools.py` подпроцессом в копии дерева с разведёнными ярусами) зелёная. |
| AC-2 | OK | Планка `test_ac2_*` зелёная. |
| AC-3 | OK | На настоящем `roles.yaml`: 86 passed на четырёх файлах критерия плюс `test_providers.py` и новый файл. |
| AC-4 | OK | Планка `test_ac4_*` зелёная; независимо повторил `guard.qualified_test_methods`/`test_skip_markers` против `6fd97017`. |
| AC-5 | OK | Планка `test_ac5_*` зелёная; независимо воспроизвёл мутацию «слой одним ярусом» — новый файл даёт 3 failed, остальные три файла остаются зелёными (на боевой карте все agent-роли на одном ярусе), то есть свойство несёт именно регрессионный тест. |

Заявки «Ловит мутацию» у трёх новых тестов проверил исполнением, а не
чтением: однорядный слой валит все три, а выпадение роли из перебора
`stack._model_checks` валит ровно
`test_every_agent_role_of_the_spread_map_gets_a_green_model_line` и НЕ
валит `test_a_role_on_its_own_tier_leaves_no_red_model_line` — то
различие, которое второй тест и заявляет. Планка задачи с момента шага
test_author (`95ce9543`) не правилась: ослабления зафиксированной планки
нет, основание ADR-0012 не требуется.

## Замечания

Замечаний нет.

Рассмотрел и сознательно не завожу: при карте, где agent-роль осталась бы
ровно одна, `test_a_role_on_its_own_tier_leaves_no_red_model_line`
покраснел бы ассертом «предмет сценария — разброс ярусов, а их один»
(`tests/test_stack_roles_tier_spread.py:82`). Разброс при одной роли
невозможен по определению, отказ внятный и громкий, а конфигурация
пульта с единственной agent-ролью ломает саму FSM задачи — сценария
поломки, ради которого стоит итерация, тут нет. Обратный случай (роли
заняли все три яруса) закрыт ветвью `if not free` — карта берётся как
есть, разброс в ней уже есть.

## Реестр замечаний

Пусто: ни одного замечания не заведено, прошлых итераций у задачи нет.

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

## Вердикт

`approved`.

## Проверено исполнением

Все прогоны — в переднем плане, таймаут команды 10 минут; полный набор
`tests/` в шаге не гонялся (решение Оператора 05.09, CI коммита
`110043f8` зелёный).

1. Планка задачи: `python3 -m pytest
   tasks/01M3H5FEXH5M9HGZYT3BCDX5C4/acceptance_tests -q` — **5 passed,
   10 subtests passed**.
2. Затронутые модули на настоящем `roles.yaml`: `python3 -m pytest
   tests/test_stack_optional_tools.py tests/test_runner_role_model.py
   tests/test_runner_model_preflight.py tests/test_models_doctor.py
   tests/test_stack_roles_tier_spread.py tests/test_providers.py -q` —
   **86 passed, 13 subtests**. Новый файл в одиночку: **3 passed,
   4 subtests**.
3. Соседние модули: `python3 -m pytest tests/test_stack.py
   tests/test_invariants.py tests/test_agent_prompt.py
   tests/test_canary_sets.py tests/test_models.py
   tests/test_model_tariffs.py tests/test_guard_mutation_claim.py
   tests/test_guard_test_ast.py tests/test_yaml_parsing.py -q` —
   **266 passed, 277 subtests** (130 с).
4. Мутация «слой называет модель у ОДНОГО яруса» (плагин прогона
   подменяет `_tiers_text` на `tiers:\n  strong: <model>`, состояние до
   задачи): **3 failed, 39 passed** — красные ровно три новых теста
   (`model-analyst: ярус standard не назван в 'tiers:'`,
   `['strong'] != ['cheap','standard','strong']`), а
   `test_stack_optional_tools.py`/`test_runner_role_model.py`/
   `test_runner_model_preflight.py` остаются зелёными: на боевой карте
   все agent-роли сегодня на одном ярусе — подтверждение и AC-5, и того,
   что старая песочница краснела бы только от поворота крутилки
   Оператора.
5. Мутация «роль выпадает из перебора `stack._model_checks`» (обёртка
   отбрасывает строки ролей не с `models.TIERS[0]`): **1 failed,
   2 passed** — красный только
   `test_every_agent_role_of_the_spread_map_gets_a_green_model_line`
   (`model-analyst` пропала из списка строк), первый тест мутацию не
   видит. Заявка второго теста подтверждена.
6. Мутация «цепочка берёт не ярус роли, а последний ярус перечня»
   (подмена `roles.model_tier`): **7 failed** —
   `test_runner_model_preflight.py::TierWithoutModelTest`,
   `test_stack.py::CheckStackModelLinesTest` (4 теста),
   `test_models_doctor.py::RoleProvidersChainTest`,
   `test_stack_roles_tier_spread.py::test_a_role_on_its_own_tier_…`.
   Свойство «читается тот ярус, который просили» из набора не ушло —
   требование 4 держится не только на неизменности ассертов.
7. Гейты формы по изменённым файлам против базы `6fd97017`
   (`scripts/guard.py`): `test_functions_without_mutation_claim` — пусто
   в каждом из четырёх файлов; `test_skip_markers` — пусто;
   `qualified_test_methods` — 15/15, 8/8, 15/15, 0→3. Совпадает с
   заявленным в PLAN.
8. Карта: `python3 scripts/codebase_map.py` + `git diff --
   docs/codebase-map.md` — единственная изменённая строка
   `built_at_sha` (`b03fb38e` → `110043f8`), содержимое совпадает;
   по скилу это не дефект. Дерево после проверок возвращено в чистое
   состояние (`git checkout -- docs/codebase-map.md`, временные плагины
   мутаций удалены, `git status --porcelain` — только `tasks/<id>/`).
9. Состав изменений: `git diff --stat 6fd97017 HEAD` — четыре файла
   `tests/` и сгенерированная `docs/codebase-map.md`. Защищённых путей
   (`roles.yaml`, `skills/`, `templates/`, `gates.yaml`, `.github/`) в
   диффе нет; «Влияние на систему» PLAN фактическому диффу соответствует.
   Откат — revert одного merge-коммита, как и заявлено.

## Предложения системе

- Подтверждаю наблюдение PLAN: `tests/test_runner_role_model.py` стал
  де-факто общим модулем песочницы (`_roles_yaml_text`, теперь
  `_tiers_text` — четыре импортёра). Адрес для такого кода —
  `tests/sandbox.py`; сейчас общий приём лежит в файле про флаг
  `--model` и находится только грепом. Перенос — отдельная задача, в
  этой был бы объёмом сверх предмета.
- Курируемый слой роли ревьювера мешает мутационной проверке заявок:
  Write вне рабочего каталога отклоняется, а `ls`/`rm` в шелле шага
  недоступны (`command not found`), поэтому плагин-мутацию приходится
  писать временным файлом В рабочую копию и удалять его питоном. Приём
  рабочий, но след временного файла в рабочем дереве ревьювера — риск
  попадания в автокоммит; стоит либо разрешить запись в `/tmp`, либо
  описать в `skills/review-checklist.md` канонический способ ставить
  мутацию (`-p` плагин из каталога вне дерева).
