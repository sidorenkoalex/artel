---
task: 01M6RN8AMHNX6TVYRNJGMTAKXC
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Служебная строка коммитов пульта по записи проекта: policy.commit_trailer

## Фаза A: план
- Таблица покрытия полна: требования 1–7 разнесены по шагам 1–3; шаги — проверяемые единицы (поле+проверка в `targets.py`, чтение в `gitcmd.py`, карта+прогоны).
- Подход соответствует архитектуре: поле добавлено рядом с образцом `co_author` (`LOCAL_FIELDS`, `DELIVERY_POLICY_FIELDS`, `_check_delivery`); `projects.py` не тронут — `target-set` правит любое поле `LOCAL_FIELDS`.
- «Влияние на систему» соответствует diff: правятся только `orchestrator/gitcmd.py`, `orchestrator/targets.py` и регенерированная `docs/codebase-map.md`; слой репозитория и `snapshot.py` не тронуты; откат — revert.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `orchestrator/targets.py:404` — необязательное поле в `LOCAL_FIELDS["policy"]`; `:436` `COMMIT_TRAILER = [A-Za-z0-9-]+: [^\n\r]*\S[^\n\r]*` с `fullmatch`; `""` допустим явно (`:785`). Пробельное значение после «: » отвергается (нужен `\S`). |
| 2 | OK | `:782-788` — не строка, `"   "`, `NoColon`, `Key:v`, `Key x: v`, `Key_x: v`, `"Key: "`, `"Key:   "`, две строки → `refuse("commit_trailer", …)`; текст содержит `policy.commit_trailer` (проверено долгоживущим тестом по всем образцам). |
| 3 | OK | `orchestrator/gitcmd.py:593-595` — трейлер записи вместо `PULT_ACTOR_TRAILER`, после `co_author` в том же абзаце, последней строкой. |
| 4 | OK | `gitcmd.py:594-598` — пустое значение не добавляется; при пустом `lines` сообщение без пустого абзаца (`message.rstrip("\n") + "\n"`). |
| 5 | OK | `entry.get("commit_trailer", PULT_ACTOR_TRAILER)`: без поля и при `project=None` (`_project_entry` → пустая запись) ветка побайтно прежняя. |
| 6 | OK | Штатный `target-set` по `LOCAL_FIELDS`; AC-5 долгоживущего теста проверяет запись, копию в `config.LOGS` и обратную загрузку. |
| 7 | OK | `git diff d442ca7...HEAD -- tests/` пуст (кроме долгоживущего файла задачи из перечня лока); `rewrite_flow` и прочие связанные тесты зелёные (см. ниже). |

Тесты: долгоживущий `tests/test_01m6rn8amhnx6tvyrnjgmtakxc_commit_trailer.py` — группа «долгоживущий», свойства кода (загрузка поля, отказы, `target-set`); заявки «Ловит мутацию» наблюдаемы (например `re.match` вместо `fullmatch` пропускает `"Key: v\nB: w"` — тест AC-4 краснеет на отсутствии отказа; удаление поля из `DELIVERY_POLICY_FIELDS` — в сведённой записи AC-2 нет ключа). Планка `acceptance_tests/test_commit_message.py` — «разовый» с обоснованием (guard закрывает долгоживущему файлу импорт `orchestrator.gitcmd`), см. «Предложения системе».

Ветка под литералы планки отсутствует — правило общее (регэксп + `get` с умолчанием). Карта `docs/codebase-map.md` свежая (сверка по содержимому без `built_at_sha`).

## Замечания

- minor — orchestrator/targets.py:436 — `[^\n\r]` пропускает прочие разделители строк Unicode (` `, `\x85`): `'Key: v B: w'` проходит проверку. Git делит сообщение только по `\n`, поэтому в коммите это одна строка и требование 2 («несколько строк») по смыслу git не нарушено; замечание вкусовое, в реестр не заносится и вердикт не блокирует. При желании — `[^\n\r\x0b\x0c\x85  ]` или проверка `len(trailer.splitlines()) == 1`.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: blocker/major не найдено; minor выше — вкусовое наблюдение без обязательного исправления.

## Вердикт
approved

## Проверено исполнением
- `python3 orchestrator/artel.py plank-run 01M6RN8AMHNX6TVYRNJGMTAKXC` — `acceptance_tests/test_commit_message.py`, 8 passed, код выхода pytest 0.
- `python3 -m pytest -q -p no:cacheprovider tests/test_01m6rn8amhnx6tvyrnjgmtakxc_commit_trailer.py tests/test_01m5wdb7jy0vjghvkcaba2qc5t_rewrite_flow.py tests/test_01m5wdb7jy0vjghvkcaba2qc5t_role_author.py tests/test_01m5wdb7f14sq30qvwjy2xybg2_record_fields.py tests/test_01m4s24963r9h18an2xdp6r15b_targets_field.py tests/test_01m5wdb7f14sq30qvwjy2xybg2_branch_template.py tests/test_gitcmd_carpentry.py tests/test_gitcmd_reads.py` — 136 passed, 52 subtests passed (420 с).
- Свежесть карты: `codebase_map.build_modules` + `render` в памяти, сравнение с `docs/codebase-map.md` без строк `built_at_sha:` — совпадает.
- Пробы регэкспа `targets.COMMIT_TRAILER` (python, в памяти): `Key: v`, `A-1: x y`, `""` — допустимы; `Key:v`, `Key: `, `Key:   `, `   `, ` Key: v`, `Key: v\nB: w` — отказ; `Key: v B: w`, `Key: v\x85B: w` — проходят (minor выше).
- `git show --stat c33615ffe` — коммит несёт только `gitcmd.py`, `targets.py`, `docs/codebase-map.md`.

## Предложения системе
- Свойство `gitcmd.pult_message` с `policy.commit_trailer` (AC-1/AC-3) после мержа сторожа в `tests/` не имеет: guard закрывает долгоживущему файлу задачи импорт `orchestrator.gitcmd` («git-модуль»), а зона SPEC не даёт другого файла `tests/`, — планка вынужденно «разовая» (ADR-0018 п. 3). Стоит либо разрешить импорт чистых функций `gitcmd` (без вызова git), либо вынести `pult_message` из git-модуля.
- Слой репозитория не проверяет `commit_trailer` (вне ТЗ по SPEC): нестроковое значение в `targets.yaml` дойдёт до `"\n".join(lines)` в `pult_message` и уронит коммит `TypeError` — тот же пробел, что у `co_author`, но там значение фильтруется `isinstance`.
