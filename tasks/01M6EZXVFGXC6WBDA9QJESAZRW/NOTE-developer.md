# Записка developer — 01M6EZXVFGXC6WBDA9QJESAZRW

## Выяснено
- Реализовано всё по требованиям 1–13; планка 42/42 зелёная (`plank-run`).
- Читатель записи `people_entry` — `github_adapter._people_entry_record`;
  причина `github_adapter.ENTRY_UNREAD_DETAIL`.
- Код отказа пределом — `gitcmd.IN_FLIGHT_REFUSAL = 75` (`_PushPlan.code`,
  `_refused(..., code=)`); прочие отказы — `PUSH_REFUSAL = 1`.
- Проект назначения без БД — `gitcmd._destination_project`; адрес-URL при
  непрочитанной записи сверяется с `remote.origin.url` корня пульта.
- Реестр хостингов: `targets._hosting_registry()` (ленивый импорт forge),
  строка в `ci.py` убрана.
- `tests/test_mr_delivery_units.py::test_in_flight_refusal_is_not_an_incident` —
  сменён только вход заглушки (код 1 → IN_FLIGHT_REFUSAL), SPEC «Материалы».

## Не сработало
- `sed -i` и составные команды требуют подтверждения — правки через Edit.

- Свои тесты: `tests/test_fail_closed_on_read_failure.py` (15, в т.ч.
  правило признака (а) mr_sync — требование 9); мутации проверены.
- Затронутые модули — 850 passed; `pytest -n` сторож роли отказывает,
  только последовательно.

## Где остановился
- Шаг завершён: код закоммичен (13889418b), карта обновлена, планка 42/42
  после коммита, PLAN.md status: ready, guard ок.

## Чего не хватило
- —
