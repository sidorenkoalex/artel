---
task: 01M4AG3QYV3E7MN7FAVA10VDJG
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-2: ответ Оператора

## Ответы

Решение Оператора 07.10 по эскалации разработчика: вариант А — замер снят Оператором вне песочницы роли.

Условия замера: голова main 37b20d5cc5b49419b33e87d980afda20a626d4f4, отдельный локальный клон, полный набор `tests/` одним вызовом pytest с флагами гейта (`-p no:cacheprovider -p timeout -o timeout=120 -n auto -p xdist`, 14 процессов), `--junitxml`; итог — 4 625 тестов, зелёный, 626 с по часам; load average машины 3–7 (посторонней нагрузки нет). Время файла — сумма времени `testcase` из JUnit XML по модулю (как в твоём подходе). Признак долгоживущего файла — строка «Группа: долгоживущий» в начале файла.

Важно для порога: время метода в общем прогоне в 3–7 раз выше, чем в одиночном прогоне того же метода (например, `ExternalPerimeterTest::test_ac1_external_task_perimeter_is_its_no_paths` — 46,0 с в общем прогоне и 6,4 с в одиночном; `LongLivedModeRemovalTest::test_journal_names_removed_path` — 27,6 с и 9,1 с). Рубеж задачи мерит время в совместном прогоне планки и долгоживущих файлов задачи, то есть в условиях, ближе к одиночному прогону. Обоснуй порог `LONG_LIVED_FILE_WARN_SEC` с учётом этого и напиши в PLAN, в каких условиях снята таблица.

Таблица для раздела «Замер файлов main» (внеси как есть):

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

Долгоживущих файлов: 104; сумма 2414 с из 4933 с всего набора; медиана файла 5.5 с; 90-й процентиль 65.7 с.

Полный набор и разовую планку прогоняет пульт после шага — `suite-run` в песочнице Codex недоступен (известная аномалия, в копилке; в этой задаче не чинится). Ложные отказы `plank-run` «PLAN.md отсутствует» до автокоммита шага — тоже не чини, оставь строкой в «Предложения системе» (уже есть). Закрой AC-11 этой таблицей, сдай PLAN со статусом `ready` и заверши шаг.
