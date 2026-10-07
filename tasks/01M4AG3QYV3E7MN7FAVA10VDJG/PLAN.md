---
task: 01M4AG3QYV3E7MN7FAVA10VDJG
type: plan
author_role: developer
status: ready
schema_version: 5
---

# PLAN: Рост долгоживущих тестов

## Подход

Существующий совместный прогон планки и долгоживущих файлов остаётся одним вызовом pytest. Его JUnit XML даёт время каждого test case; суммы по модулю дают время файла. Результат рубежа сохраняется отдельной записью журнала независимо от зелёного или красного исхода. Карточка приёмки и ревью-пакет читают последнюю запись. Порог сравнивается строго через `config.LONG_LIVED_FILE_WARN_SEC`, предупреждение не участвует в решении гейта.

Защищённый `skills/test-authoring.md` предлагается приложением ниже; файл кода роли не меняется.

## Шаги

1. Добавить замер в общий раннер приёмки, запись журнала рубежа и константу порога. Проверить время по каждому файлу, границу порога и неизменность исхода.
2. Вывести последнюю запись замера в карточке приёмки и ревью-пакете; проверить модульными тестами и залоченными тестами задачи.
3. Подготовить приложение правила test_author и замер топ-20 долгоживущих файлов текущего `main`; проверить `git apply --check`, guard и планку задачи.

## Покрытие требований

| Требование SPEC | Шаг |
|---|---|
| 1 | 3 |
| 2 | 1 |
| 3 | 1 |
| 4 | 1, 3 |
| 5 | 2 |
| 6 | 2 |
| 7 | 3 |
| 8 | 1, 2 |

## Влияние на систему

Схема БД, исходы перехода и предел `ACCEPTANCE_TIMEOUT_SEC` не меняются. Замер добавляет временный JUnit XML внутри системного временного каталога, который убирается после прогона. При красном прогоне сохраняются прежние отказ и подсказка. Предупреждение остаётся информационной строкой журнала. Откат — revert одного merge-коммита задачи; приложение защищённого пути снимается вместе с ним.

## Риски

JUnit XML суммирует время выполненных тестов файла, не сборку и импорт. Если pytest оборвётся до записи XML, журнал прямо называет время неизмеренным; красный исход сохраняется.

Полный набор через штатную команду `suite-run` в песочнице роли не стартовал: после освобождения замка `suite_lock.acquire` получил `PermissionError` при создании `.artel/logs/suite-run/lock.json` вне разрешённых корней записи. Выходы затронутых модулей проверены отдельно; полный набор и планку после шага прогоняет пульт по решению Оператора в `ANSWER-2.md`.

## Замер файлов main

Замер Оператора 07.10.2026 на голове текущего `main`
`37b20d5cc5b49419b33e87d980afda20a626d4f4`: отдельный локальный клон,
один полный прогон `tests/` с `-p no:cacheprovider -p timeout -o timeout=120
-n auto -p xdist` (14 процессов) и `--junitxml`. Итог: 4 625 тестов
прошли за 626 с по часам; load average 3–7 без посторонней нагрузки.
Время файла — сумма времени его `testcase` из JUnit XML. Долгоживущий файл
отобран по строке «Группа: долгоживущий» в начале файла. Таблица — топ-20
по убыванию времени из 104 долгоживущих файлов.

| № | Файл | Методов | Сумма, с | Самый долгий метод, с |
|---|---|---|---|---|
| 1 | `tests/test_01m462qaceh29rprd2rzhghqfm_suite_run.py` | 26 | 286.7 | 28.0 |
| 2 | `tests/test_01m45fjd46bx45vhc36s4vs9qn_declared_change.py` | 42 | 274.5 | 16.6 |
| 3 | `tests/test_01m42pencs26d0656x8fr7dfa7_project_area.py` | 30 | 189.2 | 36.2 |
| 4 | `tests/test_01m46d5t8sz9d6s34tzfx8s46v_full_suite_lock.py` | 17 | 112.5 | 19.7 |
| 5 | `tests/test_01m46c776szemypbqgpnjn1txy_appendix_gates.py` | 14 | 109.9 | 32.4 |
| 6 | `tests/test_01m3sf7dpfgez7vyeggxgtx49e_main_ci.py` | 20 | 102.5 | 18.3 |
| 7 | `tests/test_01m48wre8bhfdy011q0hqgq91b_full_suite_limit_runs.py` | 7 | 86.4 | 17.8 |
| 8 | `tests/test_01m45fk56dwmnbrka1vwm12h19_in_dev_gates.py` | 7 | 79.0 | 46.0 |
| 9 | `tests/test_01m44enqcrk02t2mwzb9hc3xhh_origin_push.py` | 11 | 73.4 | 11.7 |
| 10 | `tests/test_01m484rnv3qbdy3b0m16j916zp_external_flow.py` | 16 | 66.6 | 10.7 |
| 11 | `tests/test_01m45fk56dwmnbrka1vwm12h19_merge_gate.py` | 6 | 65.7 | 17.1 |
| 12 | `tests/test_01m48frd9rjdbbvt2sn0fy5g2a_seed_repeats.py` | 6 | 63.6 | 12.4 |
| 13 | `tests/test_01m446wn0v7jw4nsyqfktbj05c_zone_mandate_commit.py` | 11 | 63.4 | 20.7 |
| 14 | `tests/test_01m46c776szemypbqgpnjn1txy_suite_run_appendix.py` | 9 | 49.8 | 14.9 |
| 15 | `tests/test_01m3ychp14179r32sfjvkqb32g_model_sets.py` | 13 | 44.4 | 5.8 |
| 16 | `tests/test_01m41vtse5n15p5p2wzf4gf2bq_docs_command.py` | 12 | 43.2 | 9.1 |
| 17 | `tests/test_01m409ynswacnfknje2x263zsd_project_docs_ref.py` | 13 | 40.5 | 4.6 |
| 18 | `tests/test_01m41ab597b330p2rcxcmvrzpe_docs_ref_refixation.py` | 18 | 38.5 | 7.7 |
| 19 | `tests/test_01m443bpqea9zmj3r50thnb1mf_developer_step.py` | 4 | 37.7 | 10.6 |
| 20 | `tests/test_long_lived_step_end_to_end.py` | 4 | 37.1 | 21.7 |

Медиана всех 104 файлов — 5,5 с; 90-й процентиль — 65,7 с; их суммарное
время `testcase` — 2414 с из 4933 с по всему набору. Это основание порога
`LONG_LIVED_FILE_WARN_SEC = 60`: он намного выше медианы и около 90-го
процентиля полного прогона. В полном параллельном прогоне отдельный метод
занимал в 3–7 раз больше времени, чем в одиночном (46,0 против 6,4 с и
27,6 против 9,1 с в приведённых Оператором примерах). Рубеж задачи гонит
её файлы вместе с планкой, поэтому его нагрузка ближе к одиночному прогону.
В этих условиях 60 с примерно вдвое выше тяжёлого файла git/FSM из
предыдущего последовательного замера (~30 с) и составляет пятую часть
общего предела рубежа в 300 с. Порог предупреждает о существенной доле
предела, не блокируя переход.

## Проверки

- `python3 -m pytest tests/test_acceptance_file_time.py tests/test_acceptance_pycache.py tests/test_fsm_autogate.py tests/test_fsm_autogate_long_lived.py tests/test_review_package.py tests/test_long_lived_transitions.py tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 192 passed, 36 subtests passed.
- `python3 -m pytest tests/test_acceptance_tests_flow.py tests/test_acceptance.py tests/test_review_package.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 242 passed, 2 subtests passed.
- После `ANSWER-2.md`: `python3 -m pytest tests/test_acceptance_file_time.py tests/test_01m4ag3qyv3e7mn7fava10vdjg_file_time_report.py tests/test_01m4ag3qyv3e7mn7fava10vdjg_transition_time.py -p no:cacheprovider -p timeout -o timeout=120 -q` — 10 passed, 12 subtests passed.
- Три новых сторожа `tests/test_acceptance_file_time.py` покраснели на заявленных временных мутациях; после возврата кода зелёные.
- `python3 scripts/codebase_map.py`, `python3 scripts/guard.py <каталог документов>/PLAN.md`, `git diff --check`, `git apply --check /tmp/artel-01m4ag3q-plan-rule.patch` — без ошибок. Локальный `main` — `37b20d5cc5b49419b33e87d980afda20a626d4f4`; `skills/test-authoring.md` в ветке совпадает с ним.

## Предложения системе

- `suite-run`/`suite_lock.py`: команда, выданная роли для полного прогона, создаёт замок в `.artel/logs/` вне writable roots роли и падает `PermissionError`, когда чужой замок исчезает; нужна команда пульта, которая запускает прогон вне песочницы роли или открытый ей каталог состояния.
- `plank-run`/`_pult.artifact_text`: разовая планка AC-1–AC-3/AC-11 читает PLAN из `refs/artifacts/<id>`, а `plank-run` до автокоммита шага не видит только что записанный PLAN.md в каталоге документов; локальный прогон даёт четыре ложных отказа «PLAN.md отсутствует». Нужен режим предпросмотра PLAN из текущего каталога документов задачи либо автокоммит до локальной планки.

## Приложение: правило для skills/test-authoring.md

`git apply --check /tmp/artel-01m4ag3q-plan-rule.patch` на чистом защищённом файле `main`: успешно (07.10.2026).

```diff
diff --git a/skills/test-authoring.md b/skills/test-authoring.md
--- a/skills/test-authoring.md
+++ b/skills/test-authoring.md
@@ -183,6 +183,20 @@
 `self.tdir`. Образец: `tasks/01M2CN465WEDCF6D77V37FJ82E/acceptance_tests/
 test_ac4_invariants_diff_attachment.py`.
 
+## Стоимость и устойчивость долгоживущих тестов
+Свойство, проверяемое без песочницы (чистая функция, разбор, формат текста,
+таблица решений), проверяй модульным тестом без `TmpRootTest`/
+`RealGitSandbox`. Песочница с git/FSM нужна только для свойства самой связки
+«команда — FSM — база — git»; тогда докстринг теста называет, какую связку
+он держит.
+
+Короткий конечный перечень вариантов перебирай целиком в одном тесте через
+`subTest`, не отдельным методом на вариант.
+
+Тест не ждёт по реальному времени: `sleep` и опрос с таймаутом ради
+наступления события не применяются. Время и паузы подменяются. Предел
+времени в тесте — только страховка от зависания, не условие проверки.
+
 ## Чувствительность: у теста — заявленная мутация
 Тест обязан ловить поломку, а не исполнять ритуал покрытия. Для
 каждого тестового метода назови в его докстринге конкретную
```
