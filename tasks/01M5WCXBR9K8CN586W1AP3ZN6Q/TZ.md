---
task: 01M5WCXBR9K8CN586W1AP3ZN6Q
type: tz
author_role: operator
status: draft
schema_version: 2
---

# ТЗ: GitLab А1.2: doctor, проверочная команда forge-probe и песочница без живого HTTP

Родительская задача: 01M5W670PHF08VPZWDRM5BY56W — GitLab А1: адаптер хостинга — общий интерфейс, реализация GitLab, проверочная команда только на чтение
Зоны: orchestrator/doctor/misc_checks.py, orchestrator/doctor/cli.py, orchestrator/doctor/__init__.py, orchestrator/artel.py, tests/sandbox.py
Порядок: после части 1, 01M5W27CY7K7NR9347NKD8F0NX
Рамка: $25

Часть 2 деления задачи 01M5W670PHF08VPZWDRM5BY56W (ADR-0029 п. 8, шаг
А1). Часть только потребляет функции `orchestrator/forge.py` и
`orchestrator/gitlab_adapter.py` из части 1, в том числе сведения
проекта, последний конвейер ветки и константы `TOKEN_EXPIRY_WARN_DAYS`/
`TOKEN_NO_EXPIRY_TASKS_WARN`. Требования и критерии взяты из SPEC
родителя с учётом ANSWER-1 родителя и решений его гейта SPEC 26.10
(О-1): требования 11–13 и 15; AC-12 (вывод `doctor`/`forge-probe`),
AC-16, AC-17, AC-18, AC-21.

Требуется:
1. `doctor/misc_checks.py:check_base_branch` для `forge: gitlab` сверяет
   базу записи с `default_branch` из сведений проекта (вместо `skip`).
   Совпадает — `ok`, расходится — `warn`. Если сверка невозможна (нет
   токена, ошибка HTTP, сеть недоступна, адрес сервера не строится из
   `url`) — `skip` с именованной причиной адаптера.
2. Строка `doctor` о сроке токена GitLab:
   - до истечения `TOKEN_EXPIRY_WARN_DAYS` (14) дней или меньше — `warn`;
   - токен без срока: при числе задач проекта меньше
     `TOKEN_NO_EXPIRY_TASKS_WARN` — информационная строка, при числе не
     меньше порога — `warn`. «Число задач проекта» — все задачи проекта в
     БД пульта, кроме `killed`;
   - без токена — `skip` с причиной.

   Строка регистрируется в `doctor/cli.py`; новые коллаборанты
   `misc_checks` идут через фасад `doctor/__init__.py`. Реализация
   выбирается через `forge`, без сравнения `forge` с литералами.
3. Команда `forge-probe <проект> [--job <имя>]` в `orchestrator/artel.py`
   работает только на чтение и печатает:
   - пользователя токена и его уровень доступа в проекте;
   - срок токена;
   - защищённые ветки и теги;
   - последний конвейер базовой ветки: sha, итог, задания;
   - при `--job` — сводку отчёта тестов задания (число тестов по исходам).

   Команда ничего не создаёт и не меняет.
4. `forge-probe` и `doctor` работают и для записи с неподдержанным
   хостингом. Токен не появляется в выводе `doctor`/`forge-probe`.
5. Песочница тестов без живого HTTP.
   `tests/sandbox.py::isolate_keychain_and_role` подменяет транспорт
   `gitlab_adapter` по умолчанию. Подмена не обращается к сети и отдаёт
   отказ соединения, который адаптер превращает в именованную причину.
   Тест, который получил токен песочницы (`fake_keychain_token`) и не
   подменил транспорт сам, живого HTTP-обращения не делает. Подмена,
   которую тест ставит сам, имеет приоритет. Это усиление изоляции; правка
   общего помощника идёт по мандату Оператора 26.10 с матрицей
   неослабления SPEC родителя.

Существующие тесты `doctor` для GitHub остаются зелёными без правки.
`tests/test_doctor.py::BaseBranchCheckTest::test_non_github_forge_is_skipped`
(запись gitlab без `token_slot`, `url: file:///nonexistent/sled`)
ожидается зелёным без правки: токена нет, поэтому `skip` с причиной.
Тест А0 `tests/test_01m5w27cy7k7nr9347nkd8f0nx_unsupported_project.py` в
этой части не правится. В его `test_ac7_doctor_project_support_line`
фикстура `initialized_tmp_root` через `isolate_keychain_and_role` отдаёт
непустой токен `test-token-<слот>`, а у записи `url:
https://localhost/…`. После подмены из п. 5 строки `doctor` для gitlab
там дают `skip` с причиной, без живого HTTP. Если понадобится иная правка
этих тестов — эскалация.

Не входит: изменения `forge.py`/`gitlab_adapter.py` (их делает часть 1;
нехватка — эскалация); расширение `SUPPORTED_FORGES` (Б2).