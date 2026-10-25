"""Тесты гейта исходов у записи из нескольких компонентов: компоненты по
диффу с потребителями, запись на компонент, граница по компоненту, строки
пакета ревьювера; выход из `tests_writing` и `in_dev` задачи на один
компонент; планка чужого компонента на выходе из `tests_writing` — отказ
FAIL_TO_PASS в границе, прежнее поведение вне её (волна 2а-2б сведения
тестов, SPEC 01M5RH875Q1JMVRM1TXNE6HNMW; ADR-0027 п. 8, ADR-0020 п. 8).

Свод долгоживущего `tests/test_01m5jgsaanr1nzyqd4fcsve48y_outcome_components.py`
(SPEC 01M5JGSAANR1NZYQD4FCSVE48Y: `for_task` по зонам задачи, гейт исходов
по `select_components` диффа с потребителями — прогон и запись на компонент
в границе, строки «вне границы», запись пропуска при всех вне границы;
`review_lines` по записям всех компонентов головы, мандат по компоненту
находки, отказ «файл планки <имя> — компонента <X>, задача — компонента
<Y>»). Долгоживущий файл удалён решением Оператора (ADR-0020 п. 8), его
свойства перенесены сюда. Доказательство неослабления — таблицы
`mutation-run` «до» и «после» в PLAN задачи.

Стенд `box` — песочница гейта исходов по компонентам
(`tests.components_outcome_sandbox.ComponentsOutcomeSandbox` поверх
`tests.merge_outcome_sandbox.MergeOutcomeSandbox` и песочницы G3а-1а),
стенд `foreign_box` — `tests.components_outcome_sandbox.ForeignPlankSandbox`
(планка чужого компонента): настоящий git, раннеры pytest и Vitest — шпион
`subprocess.Popen` без Node и сети, сторона прогона — по метке `app.py`
выписки. Учебный проект — запись из двух компонентов: `backend` —
`junit-xml` на поддельном `pytest`, `frontend` — `pult-vitest`,
`depends_on` вида `files` на `backend/seed/`; варианты — без поля `report`
у одного или обоих компонентов (вне границы гейта исходов). Задача заводится
с зонами своего компонента и проходит настоящий выход из `tests_writing`
(планка критерия по правилу планки компонента задачи), шаг developer —
коммит правки и `fsm.cmd_advance`; зоны строки задачи — изменённые файлы
(как у песочницы G3а-1а).

Компонент записи гейта различается числом тестов базы («тестов базы N»):
у `backend` и `frontend` оно разное. Имена файлов, тестов и их число — из
`random`; зерно печатается и входит в текст каждого провала. Методы
подготовки с утверждениями тесты зовут через стенд; помощники бывших
тестовых классов — функции модуля (первый параметр — стенд).
"""
import contextlib
import io

import pytest

from orchestrator import answer, project_profile
from orchestrator.advance_gates import mandate, outcome_integrity
from tests.components_outcome_sandbox import (
    BROKEN_ACTION, COUNTS, FOREIGN, NOT_RUN, OUT_OF_BOUNDS, OUTCOME_ACTION,
    PASSED_ACTION, PREPARE_ACTION, SKIP_RECORD, ComponentsOutcomeSandbox,
    ForeignPlankSandbox)
from tests.fixtures import _sandbox
from tests.outcome_gate_sandbox import MATRIX_HEADERS


@pytest.fixture
def box():
    """Стенд ComponentsOutcomeSandbox после setUp."""
    yield from _sandbox(ComponentsOutcomeSandbox)


@pytest.fixture
def foreign_box():
    """Стенд ForeignPlankSandbox после setUp."""
    yield from _sandbox(ForeignPlankSandbox)


# ---------------------------------------------------------- Ac16DiffComponentsTest


def test_ac23_seed_change_runs_both_components(box):
    """Задача на `backend` с правкой под `backend/seed/`: гейт исходов гоняет `backend` и потребителя `frontend`, профиль задачи — `backend`.

    Сценарий: правка `backend/seed/data.py`; выход из `in_dev` проходит
    в `verifying`. Полные прогоны базы и головы — у раннера pytest и у
    Vitest; записей пройденного гейта две, по числу тестов базы —
    `backend`, затем `frontend`; `for_task` задачи — профиль `backend`.

    Ловит мутацию: гейт берёт только компонент задачи (`for_task`) —
    Vitest не гоняется, запись одна; `select_components` без
    потребителей `depends_on` — то же.
    """
    project = box.training()
    t = box.component_task(project, "backend")
    rows, output = box.developer_advance(t, {"backend/seed/data.py": "SEED = 2\n"})
    assert box.state(t) == "verifying", box.explain(rows, output)
    assert project_profile.for_task(box.conn, t.id).profile.component == \
        "backend", box.note("профиль задачи")
    for kind in ("pytest", "vitest"):
        sides = {r["side"] for r in box.runners(kind)}
        assert sides == {"base", "head"}, \
            box.explain(rows, output) + f"\nраннер {kind}"
    passed = box.records(rows)
    assert len(passed) == 2, box.explain(rows, output)
    assert passed[0].startswith(COUNTS.format(n=len(project.back_names))), \
        box.note(passed[0])
    assert passed[1].startswith(COUNTS.format(n=len(project.front_names))), \
        box.note(passed[1])


def test_ac16_component_change_runs_only_its_component(box):
    """Задача на `frontend` с правкой только под `frontend/`: гейт берёт компоненты диффа — один `frontend`, профиль его записи — `component_profiles`.

    Сценарий: правка только `frontend/src/App.jsx` (коммит без метки
    стороны `app.py`); выход в `verifying`. Полные прогоны — только
    Vitest, запись пройденного гейта одна с числом тестов базы
    `frontend`.

    Ловит мутацию: гейт гоняет все компоненты записи без выбора по
    диффу — прогоны pytest и вторая запись; профиль гейта —
    `backend` (первый компонент записи).
    """
    project = box.training()
    t = box.component_task(project, "frontend")
    box.no_marker = True
    rows, output = box.developer_advance(
        t, {"frontend/src/App.jsx": "export const App = 2;\n"})
    box.no_marker = False
    assert box.state(t) == "verifying", box.explain(rows, output)
    assert box.runners_any("pytest") == [], box.explain(rows, output)
    assert box.runners_any("vitest"), box.explain(rows, output)
    passed = box.records(rows)
    assert len(passed) == 1, box.explain(rows, output)
    assert passed[0].startswith(COUNTS.format(n=len(project.front_names))), \
        box.note(passed[0])


def test_ac16_diff_read_failure_refuses_preparation(box):
    """Сбой чтения диффа гейтом — отказ «… — подготовка», задача остаётся в `in_dev`, прогонов нет.

    Сценарий: git отказывает вызовам `diff` из кадров модуля гейта.

    Ловит мутацию: сбой чтения диффа даёт пустой набор путей — гейт
    гоняет «все компоненты» либо молча проходит.
    """
    project = box.training()
    t = box.component_task(project, "backend")
    box.git_fail = lambda args: "diff" in args
    rows, output = box.developer_advance(t, {"backend/seed/data.py": "SEED = 3\n"})
    box.git_fail = None
    assert box.records(rows, PREPARE_ACTION), box.explain(rows, output)
    assert box.state(t) == "in_dev", box.explain(rows, output)
    assert box.records(rows) == [], box.explain(rows, output)


# ---------------------------------------------------------- Ac17PerComponentTest


def test_ac17_first_refusal_names_component(box):
    """Тест `frontend` сломан правкой `backend/seed/`: `backend` проходит со своей записью, отказ гейта называет «компонент frontend: …».

    Ловит мутацию: компоненты гоняются одним прогоном без префикса
    компонента в детали; порядок не по записи — `frontend` первым, у
    `backend` записи нет.
    """
    project = box.training()
    t = box.component_task(project, "backend")
    broken = box.rng.choice(project.front_names)
    box.cases[(project.front_rel, broken)] = {"base": ["passed"],
                                              "head": ["failed"]}
    rows, output = box.developer_advance(t, {"backend/seed/data.py": "SEED = 4\n"})
    assert box.state(t) == "in_dev", box.explain(rows, output)
    refused = (box.records(rows, BROKEN_ACTION)
               or box.records(rows, OUTCOME_ACTION))
    assert refused, box.explain(rows, output)
    assert refused[-1].startswith("компонент frontend: "), box.note(refused[-1])
    assert broken in refused[-1], box.note(refused[-1])
    passed = box.records(rows)
    assert len(passed) == 1, box.explain(rows, output)
    assert passed[0].startswith(COUNTS.format(n=len(project.back_names)))


def test_ac17_out_of_bounds_component_line(box):
    """`backend` вне границы (без `report`), `frontend` в границе: запись гейта несёт строку «компонент backend: вне границы гейта исходов».

    Ловит мутацию: компонент вне границы молча опущен — строки нет;
    компонент вне границы прогоняется ядром — прогоны pytest.
    """
    project = box.training(backend_report=False)
    t = box.component_task(project, "backend")
    rows, output = box.developer_advance(t, {"backend/seed/data.py": "SEED = 5\n"})
    assert box.state(t) == "verifying", box.explain(rows, output)
    assert box.runners("pytest") == [], box.explain(rows, output)
    passed = box.records(rows)
    assert passed, box.explain(rows, output)
    joined = "\n".join(passed)
    assert OUT_OF_BOUNDS.format(name="backend") in joined.splitlines(), \
        box.note(joined)


def test_ac17_all_out_of_bounds_skip_record_and_review_lines(box):
    """Оба компонента вне границы: гейт не гоняется, запись пропуска «проверка тестов не выполняется: гейт неослабления по исходам» с «голова <sha>» и строками «вне границы»; `review_lines` головы — «не исполнялся» и строки компонентов.

    Ловит мутацию: пропуск без записи (молча); деталь записи без
    головы или без строк компонентов; `review_lines` не читает запись
    пропуска — только «не исполнялся».
    """
    project = box.training(backend_report=False, frontend_report=False)
    t = box.component_task(project, "backend")
    rows, output = box.developer_advance(t, {"backend/seed/data.py": "SEED = 6\n"})
    assert box.state(t) == "verifying", box.explain(rows, output)
    assert box.records(rows) == [], box.explain(rows, output)
    skips = box.records(rows, SKIP_RECORD)
    assert len(skips) == 1, box.explain(rows, output)
    head = box.head(t)
    lines = skips[0].splitlines()
    assert f"голова {head}" in lines, box.note(skips[0])
    for name in ("backend", "frontend"):
        assert OUT_OF_BOUNDS.format(name=name) in lines, box.note(skips[0])
    got = outcome_integrity.review_lines(box.conn, t.id, head)
    assert got[0] == NOT_RUN.format(head=head[:7]), box.note(str(got))
    for name in ("backend", "frontend"):
        assert f"гейт исходов: {OUT_OF_BOUNDS.format(name=name)}" in got, \
            box.note(str(got))


# ---------------------------------------------------------- Ac18ReviewLinesTest


def review_section(box, t) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        from orchestrator import review
        package = review.review_package(box.conn, t.id, "Задача", t.branch)
    return package["text"]


def test_ac18_package_shows_consumer_records(box):
    """Пакет ревьювера задачи на `backend`, чей гейт прогнал и `frontend`, показывает строки записей гейта обоих компонентов.

    Ловит мутацию: `review_lines` берёт только последнюю запись головы
    — строки `backend` пропадают; пакет фильтрует строки по профилю
    задачи — строк `frontend` нет.
    """
    project = box.training()
    t = box.component_task(project, "backend")
    rows, output = box.developer_advance(t, {"backend/seed/data.py": "SEED = 7\n"})
    assert box.state(t) == "verifying", box.explain(rows, output)
    head = box.head(t)
    got = outcome_integrity.review_lines(box.conn, t.id, head)
    for n in (len(project.back_names), len(project.front_names)):
        assert any(COUNTS.format(n=n) in line for line in got), \
            box.note(f"{n}: {got}")
    text = review_section(box, t)
    assert COUNTS.format(n=len(project.front_names)) in text, box.note(text[-3000:])


def test_ac18_out_of_bounds_task_shows_consumer_lines(box):
    """Задача на `backend` вне границы (без `report`), `frontend` в границе прогнан гейтом: пакет ревьювера показывает строки записи гейта `frontend`.

    Ловит мутацию: строки гейта исходов в пакете отфильтрованы по
    границе профиля задачи — у задачи вне границы раздела строк гейта
    нет.
    """
    project = box.training(backend_report=False)
    t = box.component_task(project, "backend")
    rows, output = box.developer_advance(t, {"backend/seed/data.py": "SEED = 8\n"})
    assert box.state(t) == "verifying", box.explain(rows, output)
    text = review_section(box, t)
    assert COUNTS.format(n=len(project.front_names)) in text, box.note(text[-3000:])


# ---------------------------------------------------------- Ac22FrontendTaskTest


def test_ac22_tests_writing_exit_by_frontend_rule(box):
    """Выход из `tests_writing` задачи на `frontend` с планкой `AC-<n>: ` по правилу `frontend` проходит в `in_dev`, честный FAIL_TO_PASS гоняет Vitest.

    Ловит мутацию: выход на `decide(target)` — отказ «переход
    отклонён: профиль тестов проекта», задача остаётся в
    `tests_writing`.
    """
    project = box.training()
    t, rows, output = box.writing_task(project, "frontend")
    assert box.state(t) == "in_dev", box.explain(rows, output)
    assert [r for r in box.runs if r["kind"] == "vitest" and r["plank"]], \
        box.explain(rows, output)


def test_ac22_in_dev_outcome_gate_by_frontend(box):
    """Гейт исходов на выходе из `in_dev` задачи на `frontend` гонит компонент `frontend` и пишет его запись.

    Ловит мутацию: `_bounds` на `decide(target)` — гейта нет, записи
    пройденного гейта нет.
    """
    project = box.training()
    t = box.component_task(project, "frontend")
    rows, output = box.developer_advance(
        t, {"frontend/src/App.jsx": "export const App = 3;\n"})
    assert box.state(t) == "verifying", box.explain(rows, output)
    assert box.records(rows), box.explain(rows, output)


def test_ac22_merge_gate_outcome_by_frontend(box):
    """Гейт мержа задачи на `frontend`: профиль не отказывает, гейт исходов окна мержа исполнен (доказан записью головы либо прогоном).

    Ловит мутацию: `_profile_refusal_exit` на `decide(target)` —
    «merge отклонён: профиль тестов проекта»; гейт исходов мержа
    молчит.
    """
    project = box.training()
    t = box.component_task(project, "frontend")
    rows, output = box.developer_advance(
        t, {"frontend/src/App.jsx": "export const App = 4;\n"})
    assert box.state(t) == "verifying", box.explain(rows, output)
    box.to_merge_gate(t)
    rows, output = box.approve(t)
    refused = [r for r in rows if r["action"] == "merge отклонён: профиль тестов проекта"]
    assert refused == [], box.explain(rows, output)
    gate = [r for r in rows if "гейт исходов" in (r["action"] or "")
            or (r["action"] or "") == PASSED_ACTION]
    assert gate, box.explain(rows, output)


# ---------------------------------------------------------- Ac13Ac14GateMandateTest


def mandate_answer(box, t, marker: str, element: str, matrix_element: str, covered: str) -> None:
    row = (f"`{matrix_element}`", "находка «сломан правкой» компонента frontend",
           "остаётся", covered, "ок")
    text = (f"{marker} {element}\n\n"
            "Независимая проверка: матрица подтверждена\n\n"
            f"Основание: решение Оператора ({box.seed}).\n\n"
            "## Матрица неослабления\n\n"
            "| " + " | ".join(MATRIX_HEADERS) + " |\n"
            + "|" + "---|" * len(MATRIX_HEADERS) + "\n"
            + "| " + " | ".join(row) + " |\n")
    path = box.root / ".artel" / f"answer-{box.word()}.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            answer.cmd_answer(t.id, str(path))
        except SystemExit as exc:
            box.assertIn(exc.code, (None, 0), box.note(
                f"answer отказала: {buf.getvalue()}"))


def broken_consumer(box):
    project = box.training()
    t = box.component_task(project, "backend")
    broken = box.rng.choice(project.front_names)
    box.cases[(project.front_rel, broken)] = {"base": ["passed"],
                                              "head": ["failed"]}
    return project, t, broken


def test_ac13_path_mandate_on_consumer_lifts_finding(box):
    """Задача на `backend`, тест `frontend` сломан правкой: мандат «Ослабление тестов разрешено:» на файл теста `frontend` с матрицей «остаётся / покрыто путём области frontend» принят `answer` и снимает находку на рубеже.

    Ловит мутацию: мандат проверяется по области компонента задачи —
    `answer` отказывает «путь вне области backend/tests/**»; находка
    другого компонента не покрывается мандатом — отказ «сломан
    правкой» на рубеже.
    """
    project, t, _broken = broken_consumer(box)
    mandate_answer(box, t, mandate.TEST_WEAKENING_MANDATE_MARKER,
                   project.front_rel, project.front_rel,
                   f"frontend/src/{box.word()}.test.jsx:1")
    rows, output = box.developer_advance(
        t, {"backend/seed/data.py": "SEED = 9\n"}, finished=True)
    assert box.state(t) == "verifying", box.explain(rows, output)
    assert box.records(rows, BROKEN_ACTION) == [], box.explain(rows, output)


def test_ac14_id_mandate_on_consumer_lifts_finding(box):
    """Задача на `backend`: мандат «Ослабление теста по идентификатору разрешено:» с идентификатором `frontend:…` сломанного теста и матрицей «остаётся, покрыто `frontend:…`» принят `answer` и снимает находку на рубеже.

    Ловит мутацию: компонент идентификатора сверяется с профилем
    задачи — отказ «компонента «frontend» нет в записи components:
    проекта»; находка остаётся непокрытой.
    """
    project, t, broken = broken_consumer(box)
    cid = project_profile.test_id("frontend", project.front_rel, broken)
    other = project_profile.test_id("frontend", project.front_rel,
                                    box.rng.choice(project.front_names))
    mandate_answer(box, t, mandate.TEST_ID_MANDATE_MARKER, cid, cid,
                   f"покрыто `{other}`")
    rows, output = box.developer_advance(
        t, {"backend/seed/data.py": "SEED = 10\n"}, finished=True)
    assert box.state(t) == "verifying", box.explain(rows, output)
    assert box.records(rows, BROKEN_ACTION) == [], box.explain(rows, output)


# ============================================ планка чужого компонента

# ---------------------------------------------------------- Ac19ForeignPlankTest


def test_ac19_foreign_file_in_bounds_refused(foreign_box):
    """Задача на `frontend`, в планке файл `backend` (в границе): отказ FAIL_TO_PASS «файл планки <имя> — компонента backend, задача — компонента frontend», задача остаётся в `tests_writing`.

    Ловит мутацию: `criterion_files` молча пропускает файл, чьего
    компонента нет среди профилей гейта (профиль задачи один) —
    переход проходит в `in_dev`.
    """
    project = foreign_box.training()
    t, rows, output, name = foreign_box.exit_with_foreign(project, "frontend",
                                                          "backend")
    assert foreign_box.state(t) == "tests_writing", foreign_box.explain(rows, output)
    found = foreign_box.foreign_refusals(rows)
    assert any(FOREIGN.format(name=name, x="backend", y="frontend") in d
               for d in found), foreign_box.explain(rows, output)


def test_ac19_task_out_of_bounds_still_refused(foreign_box):
    """Задача на `backend` без `report` (вне границы), в планке файл `frontend` (в границе): тот же отказ — «… компонента frontend, задача — компонента backend».

    Ловит мутацию: гейт планки чужого компонента добавляется только по
    профилю задачи в границе — под `if in_outcome_bounds(profile)` вместо
    прежнего (`fsm_advance.tests_writing`, добавление
    `_tests_writing_foreign_plank_gate` без условия) — у задачи вне
    границы файл чужого компонента в границе не проверяется.
    """
    project = foreign_box.training(backend_report=False)
    t, rows, output, name = foreign_box.exit_with_foreign(project, "backend",
                                                          "frontend")
    assert foreign_box.state(t) == "tests_writing", foreign_box.explain(rows, output)
    found = foreign_box.foreign_refusals(rows)
    assert any(FOREIGN.format(name=name, x="frontend", y="backend") in d
               for d in found), foreign_box.explain(rows, output)


# ---------------------------------------------------------- Ac25TrainingProjectTest


def test_ac25_backend_file_on_frontend_task(foreign_box):
    """Учебный проект: файл планки `backend` у задачи на `frontend` получает отказ AC-19 с именем файла и обоими компонентами.

    Ловит мутацию: компоненты в тексте отказа перепутаны местами
    (X — компонент задачи); отказ без имени файла.
    """
    project = foreign_box.training()
    _t, rows, output, name = foreign_box.exit_with_foreign(project, "frontend",
                                                           "backend")
    found = foreign_box.foreign_refusals(rows)
    assert found, foreign_box.explain(rows, output)
    assert FOREIGN.format(name=name, x="backend", y="frontend") in \
        "\n".join(found), foreign_box.explain(rows, output)
    assert FOREIGN.format(name=name, x="frontend", y="backend") not in \
        "\n".join(found), foreign_box.explain(rows, output)


# ---------------------------------------------------------- Ac27OutOfBoundsForeignTest


def test_ac27_foreign_out_of_bounds_not_checked(foreign_box):
    """Чужой компонент `backend` без `report` (вне границы): его файл у задачи на `frontend` не проверяется — отказа AC-19 и иного отказа по файлу нет, задача уходит в `in_dev`; тот же файл при `backend` в границе — отказ AC-19.

    Ловит мутацию: отказ AC-19 дан любому файлу чужого компонента без
    условия границы — у `backend` вне границы переход отклонён.
    """
    project = foreign_box.training(backend_report=False)
    t, rows, output, name = foreign_box.exit_with_foreign(project, "frontend",
                                                          "backend")
    assert foreign_box.state(t) == "in_dev", foreign_box.explain(rows, output)
    assert foreign_box.foreign_refusals(rows) == [], foreign_box.explain(rows, output)
    project = foreign_box.training()
    t, rows, output, name = foreign_box.exit_with_foreign(project, "frontend",
                                                          "backend")
    assert foreign_box.state(t) == "tests_writing", foreign_box.explain(rows, output)
    assert any(FOREIGN.format(name=name, x="backend", y="frontend") in d
               for d in foreign_box.foreign_refusals(rows)), \
        foreign_box.explain(rows, output)
