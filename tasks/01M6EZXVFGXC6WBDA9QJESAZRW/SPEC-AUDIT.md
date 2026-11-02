---
task: 01M6EZXVFGXC6WBDA9QJESAZRW
type: spec_audit
author_role: spec_auditor
status: ready
verdict: concerns
signals: в) пути-признаки (тесты): tests/, tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py; в) пути-признаки (гейты): orchestrator/fsm_merge_gate.py; д) ТЗ ссылается на ADR: ADR-0029.
spec_sha: 0616c5dfcab1582a79bdecda3068b53c9a16b81d
schema_version: 5
---

# SPEC-AUDIT: GitLab Б2.3-1: отказ при сбое вместо пропуска

Проверен SPEC с sha содержимого 0616c5dfcab1582a79bdecda3068b53c9a16b81d
(`git hash-object` файла в каталоге документов совпал). ANSWER-n.md у
задачи нет. Учтено решение Оператора на гейте SPEC №1 (пп. 1–5 прошлого
аудита). Рабочий каталог — ветка задачи на main `df354e409`.

## ТЗ и SPEC
Все пункты «Требуется» ТЗ есть в SPEC:
- people_entry и гейт мержа → требование 1;
- точка отправки → 2;
- `_awaiting_limit_refuses` → 3;
- три места `gitcmd` → 4, 5, 6;
- `github_adapter.py:173` → 7;
- `_mr_incident_stops` → 8;
- признак (а) `mr_sync` → 9;
- реестр хостингов → 10;
- запрет литералов и `EXEMPT` → 11.

Критерии ТЗ:
- устройство тестов → требование 12;
- `github` + `operator` → AC-2;
- `in_repo` артели → AC-11;
- мутация `mr_sync` → AC-14;
- прежнее поведение → AC-17.

Зоны, `merge_after` и рамка $40 совпадают с ТЗ.

Решение Оператора №1 перенесено полностью:
- п. 1 → требование 12, третий пункт;
- п. 2 → требования 1, 3, 12 и AC-1, AC-3, AC-6;
- п. 3 → требование 7, AC-12;
- п. 4 → требование 2, AC-4, AC-5;
- п. 5 → требования 4–6, AC-7, AC-8, AC-10, AC-11.

Расхождение с ТЗ в требованиях 4–5. ТЗ исключает «артель и `operator`»
только в `in_repo`. SPEC, следуя п. 5 решения, исключает в 4–6 только
артель. Для `in_repo` (требование 6) проект `operator` получил отказ
при сбое БД. По ТЗ там «отправки артели и проектов `operator` при сбое
БД идут как прежде». Решение п. 5 («исключение только артель для
требований 4–6») прямо меняет букву ТЗ. Значит, это решение Оператора, а
не отклонение. Отмечаю, чтобы смена была видна на гейте.

Требований сверх ТЗ и решений нет.

## Факты против кода
Подтвердилось:
- `fsm_merge_gate.py:1508-1514`: `repo_context.resolve` и `sys.exit` при `ctx is None`.
- `fsm_merge_gate.py:1514`: `_profile_refusal_exit`.
- `fsm_merge_gate.py:1516`: `people_entry(target) is not None`.
- `fsm_merge_gate.py:1572`: `PEOPLE_REFUSED_ACTION = "approve отклонён"`.
- `fsm_merge_gate.py:1635-1639`: `_people_refusal` = `store.journal` + `print`.
- `fsm_merge_gate.py:1661-1702`: `_mr_incident_stops`, проход на `:1695-1698`.
- `fsm_merge_gate.py:1789-1808`: `_awaiting_limit_refuses`, `except TargetsError: return False` на `:1796-1797`.
- `github_adapter.py:173`: `IN_FLIGHT_LIMIT_REASON in (push.stderr or "")`.
- `github_adapter.py:347-355`: `people_entry`, `TargetsError` → `None`.
- `gitcmd.py:758-775`: `in_flight_refusal`, `except (TargetsError, sqlite3.Error): return None`.
- `gitcmd.py:812-816`: при `entries is None` URL не сопоставляется, проект = `DEFAULT_TARGET`.
- `gitcmd.py:884-886` и `:928-932`: отказ «гейт мержа неизвестен — targets.yaml не читается».
- `gitcmd.py:956-961`: `waiting = None`.
- `gitcmd.py:975-978`: `_refused`, код `1`.
- `gitcmd.py:1242-1245`: `refusal = None`.
- `gitcmd.py:215-220`: `_project_tasks` без перехвата.
- `repo_context.py:85-89`, `:93-96`.
- `ci.py:28`, `targets.py:1098`, `mr_sync.py:356`.
- `amend.py:857`.
- `tests/test_mr_delivery_units.py:149-166`.
- `EXEMPT` в `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:416-421`.

Смена входа заглушки в `test_in_flight_refusal_is_not_an_incident`
(`tests/test_mr_delivery_units.py:155-157`) — не утверждение. Гейт
неослабления сравнивает только утверждения метода
(`scripts/guard.py:2286-2302`, `:5909-5921`), так что это верно, раздел
«Меняемое поведение» не нужен.

Не учтено в SPEC: между `resolve` (`:1508`) и `people_entry` (`:1516`)
запись `targets.target` читается ещё дважды:
- `_profile_refusal_exit` → `project_profile.for_task_target` → `decide` → `repo_context.resolve` (`orchestrator/project_profile.py:201`);
- `repo_context.profile_of` (`orchestrator/repo_context.py:170`).

`TargetsError` в этих чтениях отказывает уже там: `sys.exit` и журнал
`MERGE_PROFILE_REFUSAL_ACTION` (`orchestrator/fsm_merge_gate.py:1441-1448`).
См. вердикт п. 1.

`forge.MergeRequest.state` по умолчанию `None` (`orchestrator/forge.py:71`),
а не `""`. См. вердикт п. 3.

## Проверяемость критериев

| Критерий | Проверяем | Ловимая мутация |
|---|---|---|
| AC-1 | частично | Ловит: `people_entry` снова глотает `TargetsError` и задача идёт путём слияния. Но названный шов «`TargetsError` в `targets.target` после `repo_context.resolve`» первым срабатывает в `_profile_refusal_exit` (`fsm_merge_gate.py:1514`, `sys.exit` + `MERGE_PROFILE_REFUSAL_ACTION`). Ожидаемых `("stopped",)` и `PEOPLE_REFUSED_ACTION` при таком шве не будет (вердикт п. 1) |
| AC-2 | частично | Ловит: ветка `operator` снова сливает при сбое. Оговорка про шов та же, что у AC-1 |
| AC-3 | да | `people_entry` снова возвращает `None` при `TargetsError` |
| AC-4 | да, сторож | Удалён отказ `gitcmd.py:928-932`. На main уже зелёный — так и заявлено |
| AC-5 | да | URL при `entries is None` по-прежнему считается артелью (`gitcmd.py:815`). Вторая половина ловит отказ и для `origin` артели |
| AC-6 | частично | Нужная мутация — `except TargetsError: return False` оставлен на `:1796-1797`. Тест её не поймает, если сбой не ограничен чтением внутри `_awaiting_limit_refuses`. Тогда раньше откажет `people_entry` (`:1516`, требование 1), и причина та же: «запись проекта не прочитана:» (вердикт п. 2) |
| AC-7 | да | `except … return None` оставлен для `TargetsError` или для `sqlite3.Error` |
| AC-8 | да | Отказ при сбое распространён на артель — `amend-tests` артели откажет |
| AC-9 | да | `waiting = None` оставлен |
| AC-10 | да | `refusal = None` оставлен для одного из трёх видов записи |
| AC-11 | да | Отказ при сбое распространён на артель |
| AC-12 | да | Ловит три мутации: отказ пределом с кодом `1`; новый код у прочих отказов; `github_adapter` снова сверяет stderr |
| AC-13 | да, частично | Ловит возврат прохода для `locked` и `""`. Не назван `None` — значение по умолчанию `MergeRequest.state`. Пропустит проверку вида `mr.state in ("locked", "")` (вердикт п. 3) |
| AC-14 | да | `state == "merged"` → `True` даёт `MERGED_THIS` вместо отказа `BY_DIFF` |
| AC-15 | да | Подстановка реестра оставлена в `ci.py`, или проверка при `hosting_registry is None` пропускается |
| AC-16 | да | Новое сравнение литералом вне `targets.py` или новый элемент `EXEMPT` |
| AC-17 | да | Регрессия пути артели или `operator` при читаемых записи и БД. Держат существующие тесты |

## Зоны
Зоны SPEC покрывают требования 1–11:
- требования 1, 3, 8 — `fsm_merge_gate.py` и `github_adapter.py`;
- требования 2, 4–7 — `gitcmd.py` и `github_adapter.py`;
- требование 10 — `ci.py` и `targets.py`;
- тесты — `tests/`.

`amend.py` и `project_profile.py` не правятся. `amend.py` меняет поведение
только через требование 4. Защищённых путей задача не трогает, песочница
ролей не расширяется. `mr_sync.py`, `gitlab_adapter.py` и ADR-0029 — только
чтение. Отклонений нет.

## Матрица неослабления

| Что меняется | Какое свойство сейчас держит (тест, гейт, лимит, проверка — файл:строка) | Остаётся ли свойство после изменения | Чем покрыто после (тест файл:строка) или «не покрыто» | Решение |
|---|---|---|---|---|
| `people_entry`: сбой → исключение; отказ гейта мержа (`github_adapter.py:347-355`, `fsm_merge_gate.py:1516`) | Путь гейта артели и `operator`; тестов на пропуск при сбое нет | Да, усиливается | AC-1, AC-2, AC-3, AC-17 | Усиление |
| `_awaiting_limit_refuses` (`fsm_merge_gate.py:1796-1797`) | Предел `max_awaiting` | Да, усиливается | AC-6 (оговорка, вердикт п. 2) | Усиление |
| `_mr_incident_stops` (`fsm_merge_gate.py:1695-1698`) | Проверка инцидента MR; `tests/test_01m6ab4ve2r0q2v5d4mmjgngh7_mr_sync.py` | Да, усиливается | AC-13 | Усиление |
| Адресат-URL при непрочитанной записи (`gitcmd.py:812-816`) | Единая точка отправки | Да, усиливается | AC-5 | Усиление |
| `in_flight_refusal` (`gitcmd.py:774-775`) | Предел `max_in_flight` до коммита `amend-tests` (`amend.py:857`) | Да, артель прежняя | AC-7, AC-8 | Усиление |
| `_push_plan` `max_in_flight` (`gitcmd.py:956-961`) | Предел `max_in_flight` | Да, усиливается | AC-9 | Усиление |
| `in_repo` (`gitcmd.py:1242-1245`) | Отказ отправки ветки в `awaiting_human` | Да. `operator` при сбое БД теперь отказывает — решение п. 5 | AC-10, AC-11 | Усиление |
| Код отказа пределом (`gitcmd.py:975`, `github_adapter.py:173`) | «Отказ пределом — не инцидент»; `tests/test_mr_delivery_units.py:149-166` | Да | AC-12, тот же тест со сменой входа заглушки | Усиление |
| Подстановка реестра (`ci.py:28`, `targets.py:1098`) | Проверка `full_suite: ci/both` | Да, становится безусловной | AC-15 | Усиление |
| Сторож ac9 (`tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py:416-421`) | Запрет литералов `forge`/`merge_gate` | Да | AC-16 | Без изменений |

Раздела «Меняемое поведение» в SPEC нет, и это верно. Существующих
утверждений, закрепляющих пропуск при сбое, нет. Заглушек с
`state=None`/`""` в тестах гейта не найдено: фейк `mr_status` даёт
`opened` (`tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py:380-387`).

## Пути обхода гейтов
1. **Маскировка AC-6 отказом требования 1.** Тест AC-6 с `TargetsError`, постоянным после `resolve`, получает отказ `("stopped",)` + `PEOPLE_REFUSED_ACTION` «запись проекта не прочитана: …». Отказывает либо `people_entry` (`fsm_merge_gate.py:1516`), либо раньше `_profile_refusal_exit`. До `_awaiting_limit_refuses` (`:1630`) тест не доходит. Исполнитель оставляет `return False` на `:1796-1797` — AC-6 зелёный. Пропуск `max_awaiting` при сбое между `people_entry` и `:1795` остаётся.
2. **Шов AC-1 и AC-2.** Сбой «после `resolve`» срабатывает в `_profile_refusal_exit` (`sys.exit`, `fsm_merge_gate.py:1446`). Тест будет красным и после правной реализации. Тогда автор тестов или разработчик подгоняет устройство: считает вызовы `targets.target` либо переносит отказ `_profile_refusal_exit` в форму `("stopped",)` — правка вне требований. Возможен и вариант, где тест через `_profile_refusal_exit` не доходит до `people_entry` вовсе.

## Вердикт
**concerns.** Пять отклонений прошлого аудита сняты решением Оператора №1
и перенесены в SPEC. Новые отклонения:

1. **AC-1, AC-2: шов «после `repo_context.resolve`» попадает не в `people_entry`.** Ссылки: `fsm_merge_gate.py:1514`, `:1441-1448`, `project_profile.py:201`, `repo_context.py:170`. Требование 12 говорит «чтение внутри `people_entry`», AC-1 — «после `resolve`»; это несогласованно. Нужно уточнить в AC-1, AC-2: сбой только в чтении `targets.target` из `people_entry`, предыдущие чтения записи успешны. Это в рамках решения п. 2 (шов `targets.target`).
2. **AC-6 не ловит оставленный `return False` (`fsm_merge_gate.py:1796-1797`).** Отказ требования 1 (`:1516`) имеет ту же форму и причину. Нужно: сбой только в чтении из `_awaiting_limit_refuses` (`:1795`), и тест подтверждает, что отказал именно предел. Например, предыдущие чтения записи успешны, а `people_entry` вернул запись.
3. **AC-13 не называет `None`** — значение по умолчанию `forge.MergeRequest.state` (`orchestrator/forge.py:71`). Требование 8 («пустой») покрывает его по смыслу, но критерий пропустит реализацию, проверяющую только `""`. Предложение: «`locked`, `""`, `None`».
4. **Задачи артели на гейте мержа при сбое чтения в `people_entry` — без AC.** Требование 1 и ТЗ: «Задачи артели — без изменений»; `people_entry` теперь бросает исключение. Мутация «отказ и для артели» (`config.DEFAULT_TARGET` не исключён) не ловится: AC-17 проверяет только читаемую запись. Малое: ТЗ такого критерия прямо не требует.
5. **Для сведения Оператора, не дефект SPEC.** В требовании 6 проект `operator` при сбое БД отказывает, хотя ТЗ это исключало. Так следует из решения п. 5 («только артель для 4–6»), SPEC его исполняет буквально.

Факты о коде SPEC подтвердились все. Зоны достаточны, защищённых путей
нет. Матрица — только усиления.
