---
task: 01M3V4ZPB6HFDJ36MTDAQG5VNT
type: review
author_role: reviewer
status: approved
iteration: 2
schema_version: 5
---

# REVIEW: Канарейка Codex: авторизация при изолированном доме без записи в боевой профиль

## Фаза A — план

- PLAN дополнен разделом «Замечания ревью, итерация 1» с описанием исправления R1-F1/R1-F2; таблица покрытия (1–5 → шаги 1, 2; 6 → 2, 3) по-прежнему полна, шаги размера MR.
- «Влияние на систему» соответствует инкрементальному diff `f3446b2e..c6f15838`: затронуты только `docs/stack.md` (абзац о профиле), docstring/комментарии `orchestrator/canary.py` (без изменения логики) и один метод `tests/test_stack_codex_section.py` (строже прежнего). Замечаний к плану нет.

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 (AC-1) | OK | Без изменений с итерации 1: `CODEX_HOME=~/.artel-canary-codex/.codex`, клоны эфемерные; долгоживущий `test_ac1_…` зелёный. |
| 2 (AC-2, AC-3, AC-5) | OK | Без изменений; `test_ac3_…`, `test_ac5_…` зелёные. |
| 3 (AC-4, AC-6) | OK | Без изменений; `test_ac4_…`, `test_ac6_…` зелёные. |
| 4 (AC-7, AC-8) | OK | Без изменений; `test_ac7_…`, `test_ac8_…` зелёные. |
| 5 (AC-5, AC-9) | OK | Без изменений; `test_ac9_…` зелёный. Перенос комментария «Требование 5» внутрь блока `with` (`orchestrator/canary.py:2637–2641`) — только отступ, код не тронут. |
| 6 (AC-10, AC-11, AC-12, AC-13) | OK | AC-11/AC-13: в `docs/stack.md:258–266` возвращено объяснение «запись подписочного входа ChatGPT клиент ищет в связке ключей по ПУТИ `CODEX_HOME`» с выводом о постоянстве пути; в `tests/test_stack_codex_section.py:69` возвращён `assertIn("ПУТИ", self.body)`, прежние проверки метода сохранены и дополнены — тест строже, не слабее. AC-10 — `test_ac10_…` зелёный. AC-12 — ручная приёмка Оператора на наборе с ролью Codex (ANSWER-5 п.3). |

## Замечания

Новых замечаний нет.

Проверено и замечанием не является:
- Докстринг `test_section_says_the_login_record_is_keyed_by_the_codex_home_path` описывает сценарий и несёт наблюдаемую заявку «из раздела исчезает причина постоянства профиля»; временная мутация («по ПУТИ» → «по адресу» в `docs/stack.md`) красит метод — заявка исполнима.
- `_codex_clone_auth` в `orchestrator/` больше не вызывается (только определение `canary.py:896`), docstring честно помечает её прежней формой.
- Карта `docs/codebase-map.md`: diff `f3446b2e..HEAD` за вычетом `built_at_sha` пуст по содержимому (правки `canary.py` — только комментарии).

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|
| R1-F1 | accepted | tests/test_stack_codex_section.py:64; docs/stack.md:258 | Снят якорь `"ПУТИ"` без мандата ANSWER-5 и удалено объяснение привязки входа к пути `CODEX_HOME` | Сторож документа зелёный при утрате обоснования постоянного профиля | Исправлено в c6f15838: объяснение возвращено в `docs/stack.md`, `assertIn("ПУТИ", …)` возвращён рядом с новым утверждением; мутация документа красит метод (проверено ревьювером) |
| R1-F2 | accepted | orchestrator/canary.py:2460, 2612 | Устаревшие docstring/комментарий ссылались на `_codex_clone_auth` как на штатный путь | Вводило в заблуждение при сопровождении | Исправлено в c6f15838: ссылки на `_locked_canary_profile`/`_canary_profile_auth`, `_codex_clone_auth` помечена прежней формой, комментарий «Требование 5» на отступе блока `with` |

## Вердикт

approved: R1-F1 и R1-F2 исправлены по сути, новых дефектов в инкрементальном diff нет. AC-12 остаётся ручной приёмкой Оператора (прогон канарейки на наборе с ролью Codex после первоначального входа в `~/.artel-canary-codex`).

## Проверено исполнением

- `timeout 600 python3 -m pytest -q -p no:cacheprovider tests/test_stack_codex_section.py tests/test_01m3v4zpb6hfdj36mtdaqg5vnt_canary_profile.py tests/test_canary_profile_safety.py tests/test_canary_codex_clone_auth.py tests/test_canary_drive.py tests/test_canary.py tests/test_codebase_map.py tasks/01M3V4ZPB6HFDJ36MTDAQG5VNT/acceptance_tests` — 189 passed, 17 subtests passed.
- Временная мутация: в `docs/stack.md` «по ПУТИ `CODEX_HOME`» → «по адресу `CODEX_HOME`»; `tests/test_stack_codex_section.py` — 1 failed (`test_section_says_the_login_record_is_keyed_by_the_codex_home_path`), 2 passed; документ восстановлен `git checkout -- docs/stack.md`, дерево чистое.
- `grep -rn "_codex_clone_auth(" orchestrator` — только определение `canary.py:896`.
- `git diff f3446b2e HEAD -- docs/codebase-map.md` без строки `built_at_sha` — содержательных изменений нет.
- CI коммита c6f15838 зелёный (14 проверок, по пакету).

## Предложения системе

- Ревью-пакет: запись в `/tmp` для временной мутации отклоняется правами шага — приём «временная мутация» из review-checklist стоит описать через `git checkout -- <файл>` для восстановления, а не через копию вне рабочего каталога.
