---
task: 01M2XJKQNFTWHYAY4KBBQ1NVY7
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Зоны сверяет пульт: new --tz и гейт SPEC отказывают по неклассифицированному пути

Ревью-пакет не показал SPEC.md/PLAN.md («не существует в кодовой ветке»
— артефакты по SPEC 01M1NKTF173WV5CPDZ1C3WW69K в кодовую ветку и не
коммитятся); оба прочитаны из материализованного `tasks/<id>/` рабочего
каталога (голова артефактной ветки `artifact/01m2xjkqnftwhyay4kbbq1nvy7`,
коммит ede92843). Прошлого REVIEW.md и ANSWER-файлов у задачи нет —
итерация 1. Diff пакета (712b7cfa…HEAD, 7 файлов) прочитан целиком, все
три части.

## Фаза A: гейт плана

1. **Покрытие требований.** Таблица PLAN покрывает требования 1–9 без
   пропусков; каждое требование адресовано шагом, шаг 4 (карта, планка,
   guard) закрывает требование 9 и AC-10.
2. **Размер шагов.** Три шага по модулям (`scripts/guard.py`,
   `orchestrator/catalog.py`, `orchestrator/fsm.py`) плюс регенерация
   карты — единицы размера MR, не микрооперации; фактический diff
   (945 строк, из них 669 — тесты) совпадает с прогнозом SPEC (45 КиБ).
3. **Конвенции и архитектура.** Подход переиспользует
   `zone_lock._covered_by`/`_is_common_zone` и `guard.section_body`, как
   велят SPEC (требование 2) и «Только чтение» ТЗ; отказ `new` — тем же
   `sys.exit`, что соседний «ТЗ не прочитано», отказ гейта — тем же
   `store.journal(..., "approve отклонён", ...)` + `print` + `return`,
   что узлы `_approve_sha_ok`/`_read_branch_text_or_refuse`
   (orchestrator/fsm.py:632-657, :300-302). PLAN «Влияние на систему»
   соответствует diff: затронуты ровно три модуля из `zones:`, `tests/`
   и общая зона `docs/codebase-map.md`; путь отката — revert одного
   merge-коммита, новые функции guard зовутся только из двух точек
   (проверено grep: `spec_unclassified_paths`/`mentioned_paths` вне
   `catalog.py`/`fsm.py`/тестов не вызываются).

Косметические расхождения PLAN с кодом, замечанием не являются: PLAN
называет `_TZ_SECTION_RE`, в коде — фабрика `_tz_section_re(label)` +
`_TZ_ANY_LABEL_LINE`; PLAN обещает тест отказа `cmd_new` «в
`LightTransitionSandbox`», фактически он на `InitializedTmpRootTest`
(достаточно: `_new_task_row` и `idgen.new_task_id` замоканы, побочные
эффекты до них и проверяются).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `guard.PATH_MENTION`/`mentioned_paths` (scripts/guard.py:1546-1592): кандидаты `каталог/…/файл.расш` с перечнем `PATH_MENTION_EXTENSIONS` ровно из SPEC и `каталог/` с завершающим слэшем; фильтр существования относительно `config.ROOT` (читается в вызове), каталог обязан быть каталогом, файл — файлом. `ZONE_PATH`/`_zone_paths` не тронуты (diff их не касается; `tests/test_guard_split_signals.py` зелёный). |
| 2 | OK | `catalog._tz_path_check` (orchestrator/catalog.py:157-174): «Зоны:» через `guard.zone_items`, покрытие `_classified` = `zone_lock._is_common_zone` ∨ `_covered_by` по зонам и объявленным путям; объявляющие метки «Не входит», «Только чтение[^:\n]*» (хвост «(не менять)» учтён), «Приложением». |
| 3 | OK | Вызов в `cmd_new` сразу после чтения ТЗ и ДО `idgen.new_task_id()`/`_new_task_row` (orchestrator/catalog.py:321-326); текст — перечень путей + `UNCLASSIFIED_PATH_HINT` буквально из SPEC. Планка AC-2/AC-3 и `test_refusal_happens_before_id_row_and_branch` (моки `_new_task_row`/`new_task_id` не вызваны) зелёные. |
| 4 | OK | `guard.protected_zones` по элементам «Зоны:» с вложенностью против `config.PROTECTED_PATHS`; текст `PROTECTED_ZONE_REFUSAL` = «защищённый путь только приложением»; защищённость сверяется только по «Зоны:» — путь в «Приложением:» проходит (AC-6/AC-7 зелёные). Обе причины отказа собираются в один текст. |
| 5 | OK | `guard.spec_unclassified_paths` зовётся из `_approve_spec_gate` после чтения SPEC с ветки-источника и ДО `store.update_task(zones=…)` (orchestrator/fsm.py:729-734 → :739); классифицируют `meta["zones"]` (с вложенностью/общими зонами через тот же `_classified`) и «## Не входит»/«## Материалы». |
| 6 | OK | Проверяемые разделы — `SPEC_PATH_CHECKED_SECTIONS` = Контекст/Требования/Критерии приёмки; отказ тем же `unclassified_paths_refusal`, что и в `new`; журнал «approve отклонён», `return` без смены состояния (AC-8: состояние `spec_gate`, колонка `zones` с меткой-часовым; юнит-тест проверяет путь из «Критерии приёмки» отдельно). |
| 7 | OK | Функция отдельная; `_content_errors`/`check()`/`main()` в diff не тронуты. `python3 scripts/guard.py --all` зелёный на 926 файлах при исторических SPEC с путями вне зон; `test_check_content_does_not_call_the_spec_path_check` и AC-10 зелёные. |
| 8 | OK | Обратные кавычки/скобки/«ёлочки» — вне класса символов пути (тест с четырьмя вариантами обрамления); каталог-зона покрывает вложенный файл (AC-5, `test_directory_zone_covers_the_nested_file_on_the_gate`); несуществующий `orchestrator/nosuch.py` отбрасывается (AC-1). |
| 9 | OK | Тесты в `tests/` (три новых файла); пять названных существующих файлов прогнаны — зелёные (см. «Проверено исполнением»). |

## Корректность и целостность (Фаза B, п.2, 5, 6)

- **Регулярка.** Прогнал вручную классы ложных кандидатов: `and/or`,
  `input/output`, `N/A`, `TCP/IP`, `1/2` — не совпадают (после `каталог/`
  обязан идти либо `файл.расш`, либо конец слова); `tasks/<id>/`,
  `orchestrator/*.py` — не каталоги (`<`/`*` после слэша); `a/b.py:12`,
  `a/b.py::fn`, `a/b.py.` — путь без хвоста; `a/b.py.bak`,
  `mirror.old/scripts/guard.py` — отбрасываются. Абсолютные пути
  (`/Users/…`) кандидатами не становятся (перед первым сегментом слэш).
  Катастрофического бэктрекинга нет: класс сегмента не содержит `/`,
  итерации детерминированы.
- **Разделы ТЗ.** Граница `_TZ_ANY_LABEL_LINE` шире прежней
  `_TZ_LABEL_LINE` (допускает многословную метку) — старый `_TZ_ZONES_RE`
  калибровки не менялся (требование 1 ТЗ: калибровка вне зоны), PLAN
  честно вынес это в предложения. Метка ищется в колонке 0 (`^Метка:`),
  поэтому «Зоны:»/«Не входит:» в прозе с отступом или в «ёлочках»
  раздел не открывают.
- **Гейт SPEC.** Отказ стоит после узла чтения SPEC с ветки и до
  `update_task(zones)`, `apply_spec_budget`, подсказки калибровки и
  деления — ни один побочный эффект approve до отказа не выполняется.
  Ветка «не foreign» (`spec_text = ""`) сверки не даёт — PLAN «Риски»
  называет её недостижимой (`artifact_source.resolve` всегда foreign);
  поведение прежнее, не ослабление.
- **Безопасность / защищённые пути.** Diff трогает только
  `orchestrator/{catalog,fsm}.py`, `scripts/guard.py`, три новых файла
  `tests/` и `docs/codebase-map.md` — совпадает с `zones:` SPEC и с
  секцией PLAN «Влияние на систему». `ci/`, `.github/`, `gates.yaml`,
  `roles.yaml`, `templates/`, `skills/`, `orchestrator/zone_lock.py`,
  `orchestrator/budget.py`, `orchestrator/config.py`,
  `orchestrator/advance_gates/zones.py` («Только чтение» ТЗ) не тронуты.
  Секретов нет; недоверенный ввод (текст ТЗ/SPEC) идёт только в
  регулярки и `Path.is_file/is_dir` без исполнения.
- **Неослабление.** `git diff 712b7cfa...HEAD -- tests/ orchestrator/
  scripts/ | grep -c '^-[^-]'` → 0 удалённых строк: существующие тесты,
  гейты, лимиты и инварианты не менялись; новые отказы — ужесточение.
  Приёмочные тесты — без пометок `manual`/`skip` (grep по
  `acceptance_tests/`), автогейт не выключен. ANSWER-файлов нет.
- **Тесты — заявки «Ловит мутацию».** Докстринги есть у всех 24 новых
  тестов и у планки; сверил каждую заявку с кодом — правдоподобны, кроме
  одной половины заявки (см. «Предложения системе», п.1 — проверено
  мутацией исполнением).
- **Карта.** `python3 scripts/codebase_map.py` поверх HEAD меняет только
  строку `built_at_sha` — содержимое актуально.

## Замечания

Замечаний уровня blocker/major нет. Два наблюдения уровня minor
(не дефекты поведения, мерж не блокируют) вынесены в «Предложения
системе» п.1–2 с адресами; реестр оставлен пустым, чтобы вердикт
`approved` прошёл гейт `review -> verifying`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет — замечаний в итерации 1 не заведено.

## Вердикт

approved

## Проверено исполнением

- `python3 -m pytest tasks/01M2XJKQNFTWHYAY4KBBQ1NVY7/acceptance_tests
  tests/test_guard_path_mentions.py tests/test_catalog_tz_path_check.py
  tests/test_fsm_spec_gate_path_check.py
  tests/test_catalog_tz_zones_parsing.py tests/test_new_argv_parsing.py
  tests/test_guard_zones.py tests/test_guard_split_signals.py
  tests/test_guard_division_section.py tests/test_zones_approve.py
  tests/test_zones_gate.py -p no:cacheprovider -q` — 146 passed,
  16 subtests passed, 2.25s (планка AC-1..AC-10 целиком, три новых
  файла, пять файлов требования 9 и два соседних набора зон).
- `python3 scripts/guard.py tasks/01M2XJKQNFTWHYAY4KBBQ1NVY7/SPEC.md
  tasks/01M2XJKQNFTWHYAY4KBBQ1NVY7/PLAN.md` — «GUARD: ок (2 файлов)».
- `python3 scripts/guard.py --all` — «GUARD: ок (926 файлов)»; два
  предупреждения про `_sandbox.py` задач 01M1RA0R…/T067 —
  предсуществующие, к задаче не относятся.
- `python3 scripts/codebase_map.py` + `git diff -- docs/codebase-map.md`
  — 1 insertion/1 deletion, только `built_at_sha`; файл возвращён
  `git checkout`.
- `git diff 712b7cfa...HEAD -- tests/ orchestrator/ scripts/ |
  grep -c '^-[^-]'` — 0.
- Зонд (временный скрипт в `tasks/<id>/`, удалён после прогона):
  `catalog._tz_path_refusal` на ТЗ самой задачи и
  `guard.spec_unclassified_paths` на её SPEC против реального дерева
  пульта — ТЗ отказало бы по `docs/adr/, docs/backlog.md,
  docs/reference/role-home.md, tasks/, tasks/01M2XFSE8G3MBRHHQR38H53J1M/`,
  SPEC — по `docs/adr/, docs/reference/role-home.md,
  orchestrator/answer.py, tasks/` (см. «Предложения системе» п.3);
  `guard.unclassified_paths("Правим ./orchestrator/catalog.py.",
  {"orchestrator/catalog.py"})` → `['./orchestrator/catalog.py']`
  (п.2); граничные входы «Только чтение:» без скобок и строка-продолжение
  вида «Решил Оператор: …» внутри «Не входит:» — `([], [])`.
- Мутация (временный скрипт, исходник восстановлен, `git diff --stat
  scripts/guard.py` пуст): левая граница `(?<![A-Za-z0-9_./-])` снята из
  `PATH_MENTION` → `pytest tests/test_guard_path_mentions.py -k
  url_and_dotted` — 1 passed (мутант не пойман, п.1).
- CI коммита 01cadd17 — зелёный (14 проверок, по пакету).

## Предложения системе

1. **Заявка теста ловит только половину.**
   `tests/test_guard_path_mentions.py:105-118`
   (`test_url_and_dotted_suffix_are_not_confused_with_repo_paths`)
   заявляет, что снятие левой границы `(?<![A-Za-z0-9_./-])` вернёт
   `scripts/guard.py` из `mirror.old/scripts/guard.py` — не вернёт:
   `findall` уже поглотил кандидата целиком с позиции `m`, и без
   lookbehind результат тот же (мутант зелёный, см. выше). Левая граница
   в сегодняшней регулярке фактически срабатывает лишь после `//` (все
   прочие символы класса сами входят в сегмент). Правая половина заявки
   (`\.bak`) честная. Стоит либо сузить докстринг до правой границы,
   либо взять вход, где левая граница действует (`dir//scripts/guard.py`).
   Minor, поведение кода верное.
2. **Префикс `./`.** `scripts/guard.py:1553` — `_PATH_SEGMENT` допускает
   сегмент `.`/`..`, поэтому `./orchestrator/catalog.py` собирается как
   кандидат `./orchestrator/catalog.py`, существует
   (`Path(root)/"./…"`) и НЕ покрывается зоной `orchestrator/catalog.py`
   (`_covered_by` сравнивает строки) — ложный отказ при написании пути
   через `./`. Класс не назван SPEC; лечится нормализацией кандидата
   (`os.path.normpath` или `removeprefix("./")`) в `mentioned_paths`.
   Minor.
3. **Строгость по факту (не дефект — код следует SPEC).** Собственные ТЗ и
   SPEC этой задачи новую сверку не проходят: пути-примеры в «Требуется»/
   AC (`orchestrator/answer.py` в AC-2, `docs/adr/` в требовании 8,
   `tasks/` в AC-10) и пути-факты в «Контекст» (`docs/reference/
   role-home.md`, `docs/backlog.md` в «Источник») требуют строки в
   «Материалы»/«Не входит». Требование 6 включает «## Контекст»
   намеренно (инцидент 06.09 с `answer.py` был именно там), так что это
   заявленная цена; но первые ТЗ/SPEC после мержа упрутся в отказ по
   примерам и ссылкам на чужие `tasks/<id>/…`. Адрес: `skills/analyst*.md`
   / шаблон ТЗ Оператора — правило «каждый существующий путь в тексте
   классифицируй, примеры — в Материалы» стоит записать явно, иначе урок
   будет оплачен отказами на гейте.
4. **Форма команд в шаге ревью.** Оболочка шага отклоняла составные
   команды (`; echo "exit=$?"`, `${PIPESTATUS[0]}`), а `cat`/`ls`/`rm`/`cp`
   в ней недоступны — временные пробники пришлось класть внутрь
   `tasks/<id>/` и удалять через `python3 -c os.remove`. Адрес:
   `skills/review-checklist.md` — стоит подсказать ревьюверу простые
   одиночные команды и `python3` вместо coreutils.
