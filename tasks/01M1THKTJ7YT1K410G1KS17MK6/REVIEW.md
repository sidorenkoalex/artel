---
task: 01M1THKTJ7YT1K410G1KS17MK6
type: review
author_role: reviewer
status: approved
iteration: 4
schema_version: 4
---

# REVIEW: ADR-0014, часть 1 — потолок ролей и обязательный budget_usd в SPEC

## Фаза A: проверка плана

PLAN не менялся по существу подхода/шагов/покрытия с итерации 1–3.
Единственное изменение этой итерации — добавлен раздел «## Расширение
зон» (PLAN.md:265-281) по прямому указанию ANSWER-1.md: пути
`templates/{SPEC,PLAN,REVIEW,TEST_REPORT}.md`, `skills/spec-authoring.md`
и обоснование («приложение применено Оператором прямо на кодовой ветке
задачи коммитом `979023a8` — без немедленного подъёма schema_version
`TemplatesCarryTheVersionTest` красил бы CI»). Формулировка соответствует
тому, что реально попросил Оператор в ANSWER-1 («добавить раздел
«## Расширение зон» со строкой `Пути: ...` и обоснованием») — сделано
дословно. Замечаний по плану нет.

## Соответствие SPEC

Инкрементальный diff пакета (от sha `63e3e3977bd8d47e73537180d2d3486db5d33151`
до HEAD той же ревизии) пуст — это ТОТ ЖЕ коммит, а не «ветка не
менялась»: `prev_sha` пакета совпал с текущим HEAD, потому что
предыдущий одобренный REVIEW.md (итерация 3, `status: approved`) не был
закоммичен в кодовую ветку (артефакты не коммитятся сюда — см. отказ
advance «вердикт... уже учтён»). Свёл дельту вручную по коммиту, на
котором сам текст REVIEW.md итерации 3 фиксирует HEAD на момент своей
проверки (`82f2d06e`, указано в теле итерации 3): `git diff --stat
82f2d06e 63e3e3977bd8d47e73537180d2d3486db5d33151` — 25 файлов, но из
них 21 файл/1500+ строк это чужая, уже смerженная и одобренная задача
`01M1SG9WPVN8P3S4X7975N9T69` (та же ловушка merge-подтяжки, что итерация
3 уже описала в «Предложения системе» для случая между `5b9ff7cd` и
`82f2d06e` — здесь тот же класс повторился между `82f2d06e` и HEAD).
Собственные коммиты задачи в этом диапазоне — ровно два:

- `979023a8` — диф-приложение к защищённым путям (templates/*.md,
  skills/spec-authoring.md), применённое Оператором согласно ANSWER-1;
- `e75603c0` — разработчик пересмотрел `tests/test_spec_budget.py` под
  новую семантику (шаблон `SPEC.md` теперь несёт `budget_usd`
  раскомментированным) + регенерация карты.

Оба сверены построчно с их заявленным содержанием (см. «Проверено
исполнением»): `979023a8` посимвольно совпадает с unified-диффами из
приложения PLAN.md (сверено `templates/SPEC.md` полностью и `diff
main...HEAD` для остальных трёх шаблонов + skills/spec-authoring.md);
`e75603c0` — новый тест `test_v5_spec_without_the_field_is_refused_by_guard`
и переписанный `test_spec_without_the_field_keeps_the_default_silently`
оба несут точную и правдоподобную заявку «Ловит мутацию: …», сверенную
построчно с `requires_budget_field`/`spec_budget_field_errors`
(scripts/guard.py:1002-1052) — заявки верны.

`git diff --stat main...HEAD` (весь код задачи целиком, не
инкремент) — 14 файлов, 404 insertions/98 deletions, ровно зоны SPEC
(`orchestrator/config.py, scripts/guard.py, orchestrator/budget.py,
orchestrator/artel.py, docs/invariants.md, tests/`) плюс расширенная
зона из ANSWER-1 (`templates/*.md`, `skills/spec-authoring.md`) плюс
`docs/codebase-map.md` (обязательный реген после правки `*.py`,
COMMON_ZONES). Side effects вне зон нет.

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `ROLE_BUDGET_CAP = 100.0` с комментарием-ссылкой на ADR-0014, `DEFAULT_BUDGET_USD` не тронут (orchestrator/config.py). Без изменений с итерации 3. |
| 2 | OK | `SUPPORTED_SCHEMA_VERSION = 5`; `requires_budget_field`/`spec_budget_field_errors` версия-гейтингованы на `>= 5`, только `type: spec` (scripts/guard.py:1002-1052). Подтверждено новым тестом `test_v5_spec_without_the_field_is_refused_by_guard`. |
| 3 | OK | `role_budget_cap_errors` без версии-гейтинга, `type in (spec, plan)` (scripts/guard.py:1060-1072). Без изменений с итерации 3. |
| 4 | OK | `budget.spec_budget` сравнивает с `ROLE_BUDGET_CAP`, применяет в обе стороны; потолок Оператора не перебивается — `SpecCeilingRespectsRoleBudgetCapTest` зелёный. |
| 5 | OK | `orchestrator/artel.py` — справка разводит «мусор в поле» и «выше потолка ролей». Без изменений с итерации 3. |
| 6 | OK | Исчерпание потолка/эскалация/`budget`/стоп-лосс — код не тронут, `ExhaustedBudgetIsNotBypassableTest`, `test_step_cost.py` (57 тестов) зелёные. |
| 7 | OK | `docs/invariants.md`, инвариант 10, переформулирован буквально. Без изменений с итерации 3. |
| 8 | OK | `SPLIT_SIGNAL_BUDGET_USD = 60`, строго между 45 и 70. Без изменений с итерации 3. |
| 9 | OK | Диф-приложение реально применено Оператором коммитом `979023a8` (ANSWER-1) — все четыре шаблона несут `schema_version: 5`, `templates/SPEC.md` содержит новую формулировку поля `budget_usd` дословно как в приложении PLAN.md; `skills/spec-authoring.md` — калибровка дословно как в приложении. Сверено построчно, расхождений нет. `TemplatesCarryTheVersionTest` теперь зелёный (было красным в итерации 3 как ожидаемое временное состояние). |
| 10 | OK | Добавлен `test_v5_spec_without_the_field_is_refused_by_guard` (закрывает AC-2 в `tests/`, ранее закрывался только acceptance-планкой); `test_spec_without_the_field_keeps_the_default_silently` пересмотрен на явную фикстуру `schema_version=4` — сценарий «SPEC из шаблона без поля» для актуального шаблона (v5) больше не существует после применения приложения. Оба докстринга несут точную заявку `Ловит мутацию: …`, сверено с фактическим кодом guard.py. Полный набор `test_spec_budget.py` — зелёный. |

## Замечания

Замечаний нет.

## Реестр замечаний

R1-F1, R1-F2 (итерация 1) и R2-F1 (итерация 2) уже `accepted` с
итерации 3 — не повторяю (восстановимы из git-истории файла), код,
который они закрывали, этой итерацией не менялся. Новых замечаний в
этой итерации не заведено — реестр закрыт целиком.

## Вердикт

approved — реестр закрыт целиком (открытых записей нет), новых
замечаний нет. Все 10 требований SPEC реализованы и подтверждены
исполнением; диф-приложение к защищённым путям реально применено
Оператором и построчно совпадает с заявленным в PLAN.md; PLAN дополнен
разделом «Расширение зон» точно по мандату ANSWER-1.

## Проверено исполнением

- `git log --oneline 82f2d06e..63e3e3977bd8d47e73537180d2d3486db5d33151`
  — выявлены два собственных коммита задачи в этом диапазоне (`979023a8`,
  `e75603c0`), остальное — чужая смерженная задача `01M1SG9WPVN8P3S4X7975N9T69`.
- `git show 979023a8 --stat` и построчное сравнение с unified-диффами
  из «Приложение» PLAN.md (`templates/SPEC.md` — Read полностью;
  `templates/{PLAN,REVIEW,TEST_REPORT}.md` — `grep -n schema_version`;
  `skills/spec-authoring.md` — `git diff main -- skills/spec-authoring.md`)
  — расхождений нет, применено дословно.
- `git show e75603c0 -- tests/test_spec_budget.py` — построчная сверка
  двух докстрингов `Ловит мутацию: …` с `requires_budget_field`/
  `spec_budget_field_errors` (scripts/guard.py:1002-1052) — заявки точны.
- `python3 -m unittest tests.test_spec_budget tests.test_guard_split_signals
  tests.test_invariants tests.test_step_cost tests.test_guard_schema -v`
  — 223 теста, все зелёные (~120s), включая `TemplatesCarryTheVersionTest`
  (было красным в итерации 3, теперь зелёное — приложение применено).
- `python3 -m pytest tasks/01M1THKTJ7YT1K410G1KS17MK6/acceptance_tests -q`
  — 35 тестов, все зелёные.
- `python3 scripts/codebase_map.py` — regen сравнён с закоммиченным
  `docs/codebase-map.md`: расходится только `built_at_sha` (закреплён на
  `e75603c0`, актуальный HEAD — `63e3e397`), содержимое совпадает;
  рабочее дерево восстановлено (`git checkout -- docs/codebase-map.md`).
  Не дефект (skills/review-checklist.md, «built_at_sha не читай как
  признак дефекта»).
- `git diff --stat main...HEAD` — 14 файлов (404 insertions/98
  deletions): 6 файлов заявленных зон SPEC + 5 файлов расширенной зоны
  ANSWER-1 (`templates/*.md`, `skills/spec-authoring.md`) +
  `docs/codebase-map.md` (обязательный реген) — side effects вне зон
  нет.
- Диф `tests/test_guard_split_signals.py` (единственная правка теста
  вне `test_spec_budget.py`) сверен построчно — замена литерала `500`
  на `config.ROLE_BUDGET_CAP` не ослабляет тест, тест по-прежнему
  проверяет ровно версия-гейтинг `split_assessment_errors`, не
  путается с новым правилом.

## Предложения системе

- Подтверждаю наблюдение итерации 3: класс «HEAD отделён от prev_sha
  только merge-коммитом подтяжки main» повторился ЕЩЁ РАЗ, на этот раз
  в форме «prev_sha пакета совпал с текущим HEAD» (потому что
  предыдущий approved REVIEW.md не коммитится в кодовую ветку) — из
  инкрементального diff пакета этой итерации нельзя было увидеть вообще
  ничего, хотя два реальных коммита задачи в диапазоне были. Стоит
  явно назвать этот третий подслучай в review-checklist рядом с уже
  описанными двумя.
