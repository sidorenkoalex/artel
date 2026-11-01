---
task: 01M5XZ9Z68XE2EKPDHYCAK25KF
type: review
author_role: reviewer
status: approved
iteration: 1
schema_version: 5
---

# REVIEW: Б2.1б — гейт мержа `target-human` открывает MR, черновой MR и `max_in_flight` через `forge`

## Фаза A: план

- Таблица покрытия PLAN полна: требования 1–8 → шаги 1–6.
- Шаги размером в MR (по модулю на шаг), не микрооперации.
- Подход опирается на имена Б2.1а (`delivery_policy`, `set_mr_link`/`mr_link`,
  `AWAITING_HUMAN`), своих полей не вводит — как требует «Контекст» SPEC.
  Расширение зон на `orchestrator/amend.py` покрыто мандатом ANSWER-3 с матрицей.
- Приложение к `tests/test_invariants.py` проверено мной: `git apply --check`
  на чистом дереве проходит (AC-19).

## Соответствие SPEC

| Требование | Вердикт | Комментарий |
|---|---|---|
| 1 | OK | `fsm_merge_gate._approve_for_project_people`: ветвь стоит сразу за `_profile_refusal_exit`, внутри цикла с мьютексом. Документы, защищённые пути, неослабление по тексту и по исходам, лок планки, CI головы через `_ci_ready_or_wait`/цикл ожидания, публикация, канарейка до MR — на месте. Сверка подтверждённой головы с локальной (`_local_head_unconfirmed`) и с сервером (`_server_head_unconfirmed`). Слияния, отправки base, закрытия, `_await_main_ci` и `_refuse_if_main_red` нет (AC-3/AC-4 зелёные, планка AC-3 зелёная). |
| 2 | OK | `_base_moved_returns`: `fetch_ref_sha` + `is_ancestor`, переход `in_dev` с причиной `BASE_MOVED_DETAIL`, подтяжки нет. |
| 3 | OK | `_appendices_refuse` — отказ с точным текстом; ошибка разбора тоже считается приложением (fail-closed). |
| 4 | OK | `open_forge_mr`/`mr_assignee`: исполнитель только целое число, иначе запись журнала; при существующей ссылке `undraft_mr` + `assign_mr` (без `assign_mr` для нечислового — ANSWER-2 п. 3); 409 по `_HOSTING_CODE` → `escalated`; иной отказ — задача остаётся на гейте. |
| 5 | OK | `_awaiting_limit_refuses` считает задачи своего проекта внутри тела под мьютексом; `catalog._delivery_suffix` выводит «очередь: предел awaiting_human». AC-20 (параллельные approve) зелёный. |
| 6 | OK | `_forge_draft_mr_gate` идёт после публикации при любом её исходе, повтор работает и когда голова уже на сервере (AC-21); на `amend-tests` черновика нет; `gh` для `target-human` выключен (ANSWER-2 п. 1); описание — только изменённые защищённые пути (`mr_description`). |
| 7 | OK | `gitcmd._in_flight_refusal` в `_push_plan` (единая точка отправки): обе формы записи «ветка отправлена», отбор по проекту и незакрытым состояниям (`_dead_states`), повторная отправка не отказывается; `amend._refuse_in_flight` срабатывает до коммита (ANSWER-3); отказ на `ensure_draft_mr` GitHub — без инцидента (ANSWER-2 п. 4). |
| 8 | OK | Приложение PLAN: применяется к дереву, два теста `TargetHumanDeliveryInvariantTest` зелёные на наложенном дереве. |

## Замечания

Замечаний уровня blocker/major/minor нет.

## Реестр замечаний

| id | статус | файл/строка | суть | последствие | решение |
|---|---|---|---|---|---|

Записей нет: за итерацию 1 замечаний не заведено.

## Вердикт

approved

Системная целостность: существующие тесты в diff не изменены, добавлен только
`tests/test_mr_delivery_units.py`. Гейты не ослаблены: ветвь `operator` идёт
прежним телом (ветвление по `github_adapter.people_entry`). Пропущенные на ветви
`target-human` шаги совпадают с матрицей неослабления SPEC. Защищённые пути
(`skills/`, `templates/`, `gates.yaml`, `.github/`) не тронуты. Заявки
«Ловит мутацию» в `tests/test_mr_delivery_units.py` наблюдаемы: каждая называет
утверждение, которое покраснеет. Положительная половина AC-15, которую сквозной
путь проверить не может (ANSWER-1), закрыта юнит-тестом `MrDescriptionTest` в `tests/`.

## Проверено исполнением

- `python3 -m pytest tests/test_01m5xz9z68xe2ekpdhycak25kf_mr_delivery.py tests/test_mr_delivery_units.py -p no:cacheprovider -q` на HEAD b0dc14c71 — 47 passed, 8 subtests passed (50 с).
- `artel.py plank-run 01M5XZ9Z68XE2EKPDHYCAK25KF` — 2 passed, код выхода pytest 0.
- Приложение PLAN к `tests/test_invariants.py`: `git apply --check -v -` — применяется. Затем временно наложил его и прогнал `pytest tests/test_invariants.py -k TargetHumanDeliveryInvariantTest` — 2 passed, 5 subtests. После этого вернул файл (`git checkout -- tests/test_invariants.py`), `git status` чистый.
- Временную мутацию «счёт `max_in_flight` по всем проектам» поставить не удалось: права шага отклонили и правку файла через `sed`, и запуск pytest с переменной окружения перед командой. Заявку AC-16 проверял только чтением теста: ветвь «другой проект» с N−1 своими задачами и ≥1 чужой при такой мутации получила бы отказ.

## Предложения системе

- Шаг ревью не может поставить временную мутацию, которой требует review-checklist: правка кода через `sed`/`cp` и `PYTHONPATH=… pytest -p плагин` ждут подтверждения, а `pytest.main` из `python -c` сторож принимает за полный прогон. Стоит назвать в скиле способ, разрешённый правами роли.
