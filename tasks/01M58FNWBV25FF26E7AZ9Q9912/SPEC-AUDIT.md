---
task: 01M58FNWBV25FF26E7AZ9Q9912
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/test_acceptance_suite_profile.py; г) budget_usd 45 ≥ 45; д) ТЗ ссылается на ADR: ADR-0026.
spec_sha: a4898611e2ce5069c858039ac66204cb0dfb7f00
schema_version: 5
---

# SPEC-AUDIT: G1а (часть 1) — компоненты проекта в записи targets.yaml: схема, profile_of, выбор по путям

## ТЗ и SPEC
Сверено в обе стороны с ТЗ, ANSWER-1 и решением Оператора на гейте SPEC №1.

- ТЗ п. 1 (поле `name`, `depends_on` списком `{component, via, paths}`) → SPEC треб. 2–3: ключ отображения вместо `name`, `depends_on` — отображение. Основание — ANSWER-1 п. 1. Расхождения нет.
- ТЗ п. 2 → треб. 4, AC-4. ТЗ п. 3 → треб. 6–8, AC-6, AC-7. ТЗ п. 4 → треб. 5, 9, 10, AC-5, AC-8, AC-9. ТЗ п. 7 → треб. 11.
- ТЗ п. 5 (`doctor`) и п. 6 (ключ кэша) вынесены в «G1а-2» по ANSWER-1 п. 9 («Не входит»). Зона `orchestrator/doctor/cli.py` из ТЗ снята там же. Перехват в `doctor/cli.py:94` записан в «Не входит», как велит решение гейта п. 3.
- Решение гейта №1: п. 1–2 → треб. 5, 10 (признак `multi`, `_task_own_profile` отказывает только при нём, `test_acceptance_suite_profile.py` не правится). П. 3 → «Не входит». П. 4 → AC-2 (но см. ниже, «Проверяемость», отклонение 2). П. 5 → AC-7. П. 6 → треб. 3 (`workdir`/`env`, `repo`). П. 7 → треб. 6. П. 9 → «Не входит» (повтор имени), треб. 3 (`paths: []`, `long_lived_imports` у артели). Все пункты отражены.
- Требований сверх ТЗ и ответов нет. Расширения перечислены в «Материалах» как прямые следствия: имя без `:`, UNREAD у единственного компонента без обязательного подполя, вид исключения, `repo` у любого компонента. Каждое выведено из ТЗ или ADR, не новое.
- Следствие треб. 5, которое в SPEC прямо не названо (отклонение 4): у единственного компонента с новой формой `long_lived` нет пары `long_lived_dir`/`long_lived_name`. Проверку записи такой компонент проходит (треб. 3 разрешает `long_lived` как замену пары), а `profile_of` даёт UNREAD, то есть `decide` отказывает. Значит, запись с одним компонентом в форме ADR-0026 п. 1 до G2 не исполняется. С ТЗ п. 4 («ведёт себя как `test_profile`») это согласуется, но не названо явно.

## Факты против кода
Подтверждено:
- `targets.py:43-73`: `PROFILE_FIELD` :43, `PROFILE_FIELDS` :44-60, `PROFILE_OPTIONAL` :63, `PROFILE_EXTERNAL_ONLY` :66, `PROFILE_REPORTS` :67, `PROFILE_OWN_RUNNER_ONLY` :73.
- `targets.py:182-190`: ветка `test_profile` в `check` и правило «не у артели». `_check_profile` — :290-319, правило `workdir`/`env` — :310-318. `_profile_value_error` — :334-394. `KNOWLEDGE_*` — :80-81.
- `project_profile.py`: `mask_matches` :46-61, `Profile` :65-121, `decide` :143, `for_task` :175, `full_suite_limit` :179-187 (на UNREAD бросает `TargetsError(answer.reason)`, :182-183).
- `repo_context.py`: `ProfileAnswer` :129-137, `profile_of` :139-151. `profile_of` — единственный читатель `test_profile`: grep `PROFILE_FIELD|"test_profile"` по `orchestrator/` и `scripts/` других читателей не находит. Поэтому треб. 5 закрывает все пути чтения.
- `acceptance.py`: `drop_from_code_copy` :1285-1301 (`_task_own_profile` :1298), вызов в `run_full_suite` :2372, `_task_own_profile` :2380-2400.
- `suite_run._profile_command` :271-297, ветка UNREAD :279-281. `_run` зовёт `full_suite_limit` (:559) только после `_profile_command` (:556-558), значит до необработанного `TargetsError` дело не доходит. Утверждение «`suite_run.py` не меняется» верно.
- `yamlmini.py`: :16-20, :145 (блочные списки), :146 (ключ режется по первому `:`), :155/:159 (повтор ключа перезаписывает), :174-195 (потоковые списки, кавычки внутри — отказ :189-195).
- `docs/codebase-map.md` и `tests/` входят в `config.COMMON_ZONES` (`config.py:803`).

Неточности:
- **Отклонение 1.** Треб. 10 (SPEC, абзац «Прочие вызывающие…») утверждает, что `plank_run.py:220` при отказе `decide` недостижим. Это не так. `cmd_plank_run` (`plank_run.py:148-220`) доходит до `acceptance._task_own_profile` без проверки отказа `decide`. Единственное чтение `decide` в нём — `_long_lived_arg` (`plank_run.py:87`), и оно берёт `.profile`, а отказ не смотрит. Шаг `tests_writing` отказом профиля не блокируется: `runner.py:1323-1333` у `test_author` лишь пишет отказ в журнал. Миссия автора тестов велит гонять `plank-run`. На задаче проекта с двумя компонентами `plank-run` в `tests_writing` упадёт необработанным `targets.TargetsError` с трассировкой, хотя должен дать отказ `sys.exit`, как прочие отказы этой команды (`plank_run.py:157-216`). Решение гейта п. 2 велело так и записать, но фактическое основание для `plank_run.py` неверно. Остальные места SPEC недостижимыми названы обоснованно: `runner.py:1218`, `checkpoint.py:1237`, `fsm_advance.py:607` и `amend.py:765` идут через `drop_from_code_copy`, а его треб. 10 делает безопасным.
- `targets.load` — `targets.py:100`; :111 — это вызов `yamlmini.mapping` внутри неё. На суть не влияет.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | да | `targets.check` отвергает `components:` или одно из полей (`depends_on`, `paths_source`, `tools`, `long_lived`); `components()` теряет порядок записи; `via` не доходит до вызывающего |
| AC-2 | частично | проверка любого из перечисленных полей удалена → допуск. Не ловится: проверка `depends_on.paths` (не компилируется, `,`/`[`/`]`) удалена; `depends_on` не отображение принимается; `paths` с `"`/`'` принимается (треб. 3 это запрещает, AC-2 — нет); элемент `paths` не строка (`yamlmini` даёт `int` из `1`) роняет `re.compile` исключением `TypeError` вместо отказа — отклонение 2 |
| AC-3 | да | проверка «оба поля» удалена |
| AC-4 | да | `PROFILE_REPORTS` расширено значением `pult-vitest` для `test_profile`; правка текстов отказа `decide`; `components`/`select_components` не дают `default` |
| AC-5 | да | единственный компонент читается как multi или ABSENT; `KeyError` из `Profile.from_values` вместо отказа |
| AC-6 | да | `test_support` не учтён; потребитель по `depends_on` не добавлен; путь без попадания даёт пустой выбор; набор «backend + docs» даёт только backend; порядок не тот, что в записи |
| AC-7 | да | разделитель `:`/`::`/`#` другой; `parse_test_id` режет полное имя по первому `::` после пути неверно |
| AC-8 | да | `multi` не выставлен; читатель возвращает предел `config` или `skip` |
| AC-9 | частично | `acceptance_suite` зовёт `full_suite` прежней формой; `drop_from_code_copy` падает. Не ловится: перехват в `drop_from_code_copy` шире отказа (`except Exception`), хотя треб. 10 это запрещает («Перехват не шире отказа») — отклонение 3 |

## Зоны
- Зоны SPEC: `targets.py`, `project_profile.py`, `repo_context.py`, `acceptance.py`, `tests/` (плюс `COMMON_ZONES`: `config.py`, `docs/codebase-map.md`). Это подмножество зон ТЗ (ANSWER-1 п. 9), требований хватает. В `acceptance.py` ограничение «только ключ кэша» снято для `_task_own_profile` ANSWER-1 п. 2, правка `acceptance_suite`/`drop_from_code_copy` названа в треб. 10.
- Защищённые пути (`skills/`, `templates/`, `gates.yaml`, `roles.yaml`, `.github/`) не затрагиваются. `targets.yaml` и ADR-0026 только читаются. Песочница ролей не расширяется.
- Исправление отклонения 1 потребовало бы `orchestrator/plank_run.py` — вне зон. Это решение Оператора: принять трассировку до G1б или расширить зоны.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `targets.check` принимает `components:` | форма `test_profile`, отказ неизвестного подполя (`targets.py:290-319`) | да, для `test_profile` без изменений | AC-4 (тест задачи) | ок |
| `PROFILE_REPORTS`/значение `report` | у `test_profile` только `junit-xml` (`targets.py:67`, :387-388) | да, `pult-vitest` только у компонента | AC-4 (отказ `test_profile.report: pult-vitest` прежним текстом) | ок |
| правило `workdir`/`env` (`targets.py:310-318`) | только при `pytest-own` | да у `test_profile` и записи с одним компонентом; у записи с несколькими компонентами снято (ANSWER-1 п. 3) | AC-2 (один компонент — отказ), AC-2 «без отказа» (несколько) | ок, решение Оператора |
| `long_lived_imports` не у артели (`targets.py:184-190`) | у `test_profile` артели | да, распространено на компоненты | AC-2 | ок |
| `profile_of` → исход для `components:` | три исхода (`repo_context.py:139-151`); проверки тестов не отключаются у артели без профиля (`project_profile.py:160-164`) | да: запись с несколькими компонентами даёт UNREAD → отказ, а не ABSENT → пропуск | AC-8 | ок |
| `_task_own_profile` (`acceptance.py:2380-2400`) | полный набор не идёт чужой формой | да, строже: отказ при `multi` | AC-9; `tests/test_acceptance_suite_profile.py` без правки | ок |
| `plank_run.cmd_plank_run` при `multi` | отказы `sys.exit` с причиной (`plank_run.py:157-216`) | частично: при `multi` будет трассировка `TargetsError`, хотя отказ по сути остаётся | не покрыто | отклонение 1, решение Оператора |

Раздела «Меняемое поведение» в SPEC нет, смен ожиданий существующих тестов нет («Не входит»). Мандатов не требуется.

## Пути обхода гейтов
- Обход через чтение `test_profile` мимо `profile_of` исключён: других читателей нет (grep выше). Запись с `components:` не может дать ABSENT и «пропуск» проверок.
- `select_components`: путь без попадания даёт все компоненты, а не пустой выбор (треб. 7, AC-6). Обхода «зелёный на пустом выборе» нет.
- Ширина перехвата в `drop_from_code_copy`: SPEC его ограничивает, AC-9 — нет (отклонение 3). Исполнитель может поставить `except Exception: pass` и молча глотать прочие сбои уборки выкладки. Буква AC при этом соблюдена.
- `depends_on.paths` без проверки формы (отклонение 2): некомпилируемое выражение пройдёт `targets.check`, а потом упадёт в `select_components` исключением `re.error` у вызывающего G1б.

## Вердикт
**concerns.** SPEC можно вести дальше, отклонения решаемы Оператором на гейте:

1. `SPEC.md` треб. 10, абзац «Прочие вызывающие…». `plank_run.py:220` назван недостижимым, но достижим в `tests_writing`: `plank_run.py:87` отказ `decide` не смотрит, `runner.py:1323-1333` шаг не блокирует. На записи с двумя компонентами `plank-run` упадёт трассировкой `TargetsError`, а не отказом. Варианты: принять до G1б (записей с `components:` в `targets.yaml` нет) или расширить зоны на `plank_run.py` с перехватом.
2. `SPEC.md` AC-2 (раздел `paths`/`depends_on`). Нет подслучаев на форму `depends_on.paths`, на `depends_on` не отображением, на `"`/`'` в `paths` (треб. 3) и на элемент `paths` не строкой. Мутация «проверка `depends_on.paths` удалена» проходит планку.
3. `SPEC.md` AC-9 при треб. 10 («Перехват не шире отказа»). Ширина перехвата в `drop_from_code_copy` (`acceptance.py:1298`) не проверяется.
4. `SPEC.md` треб. 5 при треб. 3. Единственный компонент с `long_lived` вместо пары `long_lived_dir`/`long_lived_name` проходит проверку записи, но даёт UNREAD и отказ `decide`. Следствие не названо явно; формулировки отказа и AC на это нет.
5. Мелочь: `targets.load` — `targets.py:100`, не :111.
