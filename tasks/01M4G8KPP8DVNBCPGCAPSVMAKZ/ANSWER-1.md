---
task: 01M4G8KPP8DVNBCPGCAPSVMAKZ
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: ответ Оператора

## Ответы

---
task: 01M4G8KPP8DVNBCPGCAPSVMAKZ
type: answer
author_role: operator
status: ready
schema_version: 2
---

# ANSWER-1: CI ветки красный — что чинить

## Ответы

Эскалация 09.10 16:41Z вызвана обрывом сети машины (GitHub недоступен,
потолок ожидания CI в verifying), а не задачей; она снята. Но CI коммита
46c5f338 (pull_request, 09.10 15:08Z) красный по двум долгоживущим
тестам — это дефекты кода шага, их нужно исправить:

1. `tests/test_01m42pencs26d0656x8fr7dfa7_gitcmd_explicit_repo.py::GitcmdWithoutRepoOnlyFromAllowListTest::test_ac8_every_call_without_repo_is_in_the_allow_list`
   — `orchestrator/checkpoint.py:1669: gitcmd.git (в _main_copy_status)`:
   вызов git без явного репозитория. Сторож главной копии должен звать git
   с явно переданным репозиторием (корень главной копии пульта), как
   остальные вызовы вне перечня.
2. `tests/test_review_package.py::CmdRunReviewPackageTest::test_developer_step_has_no_package`
   — в записанной тестом последовательности git-вызовов шага появился
   лишний `['status', '--porcelain']` сторожа. Сторож не должен менять
   последовательность git-вызовов шага, которую фиксируют существующие
   тесты: например, сверка главной копии идёт через отдельную точку
   вызова, а не через тот же путь, что пишет тест.

Долгоживущие тесты не править: их утверждения не меняются, мандата на
ослабление нет. Если без смены утверждения обойтись нельзя — эскалация
с обоснованием, а не правка. Перед сдачей прогони оба файла и
`tests/test_01m4g8kpp8dvnbcpgcapsvmakz_*.py`.
