"""Подполе `full_suite_timeout_sec` профиля тестов проекта и его строка в `doctor`.

Группа: долгоживущий
Красен до реализации: подполя full_suite_timeout_sec в профиле тестов нет — targets.load отказывает «неизвестное подполе» на любом значении (AC-1), причина отказа на неверном значении не называет test_profile.full_suite_timeout_sec (AC-2), doctor строки о пределе полного прогона не печатает (AC-8).

Песочница — `tests/sandbox.py::TmpRootTest`: `config.TARGETS` — временный
файл, в который сценарий пишет записи проектов сам (запись артели —
`ARTEL_TEST_PROFILE` песочницы). Значения предела и имена проектов — от
зерна, зерно печатается и входит в текст провала.

`doctor` — настоящая команда `doctor.cmd_doctor`; подменены только
живой вызов CLI исполнителя ролей (`subprocess.Popen` программы `claude`
отвечает «не найден») и токен из keychain — они вне предмета и в песочнице
не нужны. Код выхода `doctor` не проверяется: остальные проверки в
песочнице вправе быть красными.
"""
import contextlib
import io
import random
import re
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from orchestrator import (config, doctor, project_profile, repo_context, store,
                          targets)
from tests.sandbox import ARTEL_TEST_PROFILE, TmpRootTest

LETTERS = "abcdefghijkmnpqrstuvwxyz"
SUBFIELD = "test_profile.full_suite_timeout_sec"
UNREAD = "не прочитан"

ENTRY = """  {name}:
    forge: github
    url: file:///nonexistent/{name}
    base: {base}
    token_slot: {name}-token
    no_paths: []
    project_skills: []
    merge_gate: operator
"""

EXTERNAL_PROFILE = """    test_profile:
      command: [python3, -m, pytest]
      long_lived_dir: tests
      long_lived_name: test_<id>_<name>.py
      weakening_scope: [tests/**/*.py]
      mutation_claim_scope: [tests/test_*.py]
"""

REAL_POPEN = subprocess.Popen


def with_limit(profile: str, raw: str) -> str:
    """Профиль с подполем `full_suite_timeout_sec: <raw>` (сразу за
    заголовком поля)."""
    head = "    test_profile:\n"
    assert profile.startswith(head), profile
    return f"{head}      full_suite_timeout_sec: {raw}\n{profile[len(head):]}"


def standalone(number: int, text: str) -> bool:
    return re.search(rf"(?<![\d.]){number}(?![\d.])", text) is not None


class LimitFieldSandbox(TmpRootTest):

    def setUp(self):
        super().setUp()
        self.seed = random.randrange(1 << 30)
        print(f"зерно: {self.seed}")
        self.rng = random.Random(self.seed)

    def note(self, text: str) -> str:
        return f"{text}\nзерно: {self.seed}"

    def word(self) -> str:
        return "p" + "".join(self.rng.choice(LETTERS) for _ in range(8))

    def write_targets(self, entries: dict) -> str:
        text = "targets:\n" + "".join(
            ENTRY.format(name=name, base=config.MAIN_BRANCH) + profile
            for name, profile in entries.items())
        Path(config.TARGETS).write_text(text, encoding="utf-8")
        return text


class ValidLimitTest(LimitFieldSandbox):

    def test_ac1_positive_integer_limit_is_accepted(self):
        """Целое > 0 в подполе — запись проходит `targets.load`, профиль читается.

        Сценарий: несколько значений (1 и случайные до сотни тысяч, от
        зерна); для каждого — запись артели и запись внешнего проекта с
        подполем `full_suite_timeout_sec: <N>` в профиле. `targets.load` не
        отказывает; `repo_context.profile_of` обоих проектов — «профиль
        есть»; `project_profile.decide` артели — профиль без отказа.

        Ловит мутацию: подполе не внесено в перечень известных подполей
        профиля — `targets.load` отказывает «неизвестное подполе
        'full_suite_timeout_sec'», профиль «не прочитан»; либо граница
        проверки сдвинута (`> 1` вместо `> 0`) — значение 1 отклоняется.
        """
        values = [1] + [self.rng.randint(2, 100000) for _ in range(4)]
        for value in values:
            external = self.word()
            text = self.write_targets({
                config.DEFAULT_TARGET: with_limit(ARTEL_TEST_PROFILE,
                                                  str(value)),
                external: with_limit(EXTERNAL_PROFILE, str(value))})
            context = self.note(f"значение {value}; targets.yaml:\n{text}")
            try:
                targets.load()
            except targets.TargetsError as exc:
                self.fail(self.note(f"targets.load отказал: {exc}\n{context}"))
            for name in (config.DEFAULT_TARGET, external):
                answer = repo_context.profile_of(name)
                self.assertEqual(answer.outcome, repo_context.PROFILE_PRESENT,
                                 self.note(f"{name}: {answer}\n{context}"))
            decision = project_profile.decide(config.DEFAULT_TARGET)
            self.assertEqual(decision.refusal, "", context)
            self.assertIsNotNone(decision.profile, context)


class InvalidLimitTest(LimitFieldSandbox):

    def bad_values(self) -> list:
        """Ноль, отрицательное целое, строка в кавычках и дробное — от зерна."""
        n = self.rng.randint(1, 5000)
        return ["0", f"-{n}", f'"{self.rng.randint(1, 5000)}"',
                f"{self.rng.randint(1, 5000)}.{self.rng.randint(1, 9)}"]

    def test_ac2_bad_limit_refuses_targets_load_naming_subfield(self):
        """Неверное значение подполя — `TargetsError` с именем подполя.

        Сценарий: для каждого из значений 0, -N, "N" (в кавычках) и N.M
        (от зерна) в профиле внешнего проекта `targets.load` поднимает
        `targets.TargetsError`, и её текст содержит
        `test_profile.full_suite_timeout_sec`.

        Ловит мутацию: проверка вида берёт `>= 0` вместо `> 0` (0
        принимается); строка в кавычках приводится к числу `int(value)`;
        дробное принимается проверкой `isinstance(value, (int, float))`;
        отрицательное не отсекается — `targets.load` проходит молча.
        """
        for raw in self.bad_values():
            text = self.write_targets({
                config.DEFAULT_TARGET: ARTEL_TEST_PROFILE,
                self.word(): with_limit(EXTERNAL_PROFILE, raw)})
            context = self.note(f"значение {raw}; targets.yaml:\n{text}")
            with self.assertRaises(targets.TargetsError, msg=context) as ctx:
                targets.load()
            self.assertIn(SUBFIELD, str(ctx.exception),
                          self.note(f"причина: {ctx.exception}\n{context}"))

    def test_ac2_bad_limit_refuses_profile_gate_like_other_profile_errors(self):
        """Гейт, читающий профиль, отказывает «не прочитан» с именем подполя.

        Сценарий: профиль артели с неверным `full_suite_timeout_sec` (0, -N,
        "N", N.M — от зерна). `repo_context.profile_of` артели — «не
        прочитан», причина называет подполе; решение проверок тестов
        `project_profile.decide` — отказ без профиля, тем же видом, что у
        контрольной ошибки профиля (неизвестный формат отчёта `report`):
        оба отказа несут «не прочитан», ни один не «контекст не разрешён».

        Ловит мутацию: неверное значение подполя не поднимает
        `TargetsError` из проверки записи, а молча заменяется умолчанием
        config — `profile_of` отдаёт «профиль есть», `decide` пропускает
        гейт вместо отказа.
        """
        control_profile = ARTEL_TEST_PROFILE.replace(
            "report: junit-xml", f"report: {self.word()}")
        self.write_targets({config.DEFAULT_TARGET: control_profile})
        control = project_profile.decide(config.DEFAULT_TARGET)
        self.assertIn(UNREAD, control.refusal, self.note(
            f"контрольная ошибка профиля не дала «не прочитан»: {control}"))

        for raw in self.bad_values():
            text = self.write_targets({
                config.DEFAULT_TARGET: with_limit(ARTEL_TEST_PROFILE, raw)})
            context = self.note(f"значение {raw}; targets.yaml:\n{text}")
            answer = repo_context.profile_of(config.DEFAULT_TARGET)
            self.assertEqual(answer.outcome, repo_context.PROFILE_UNREAD,
                             self.note(f"{answer}\n{context}"))
            self.assertIn(SUBFIELD, answer.reason, context)
            decision = project_profile.decide(config.DEFAULT_TARGET)
            self.assertIsNone(decision.profile, context)
            self.assertEqual(decision.unresolved, control.unresolved, context)
            self.assertIn(UNREAD, decision.refusal,
                          self.note(f"отказ: {decision.refusal}\n{context}"))
            self.assertIn(SUBFIELD, decision.refusal,
                          self.note(f"отказ: {decision.refusal}\n{context}"))


def popen_without_role_cli(cmd, *args, **kwargs):
    """`subprocess.Popen`, для которого CLI исполнителя ролей не найден:
    живой смок `doctor` в песочнице не вызывает настоящий `claude`."""
    program = cmd if isinstance(cmd, str) else (cmd[0] if cmd else "")
    if "claude" in Path(str(program).split()[0] if program else "").name:
        raise FileNotFoundError(program)
    return REAL_POPEN(cmd, *args, **kwargs)


class DoctorLimitLineTest(LimitFieldSandbox):

    def setUp(self):
        super().setUp()
        store.create_schema(store.db())

    def run_doctor(self) -> str:
        buf = io.StringIO()
        with mock.patch.object(doctor.subprocess, "Popen",
                               side_effect=popen_without_role_cli), \
                mock.patch.object(doctor.runner.keychain, "token",
                                  lambda slot: None), \
                contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            try:
                doctor.cmd_doctor()
            except SystemExit as exc:
                if exc.code not in (None, 0, 1):
                    buf.write(f"\n{exc.code}\n")
        return buf.getvalue()

    def limit_lines(self, out: str, name: str, limit: int) -> list:
        """Строки вывода с именем проекта и числом предела."""
        word = re.compile(rf"(?<![\w-]){re.escape(name)}(?![\w-])")
        return [line for line in out.splitlines()
                if word.search(line) and standalone(limit, line)]

    def test_ac8_doctor_prints_limit_and_source_per_project(self):
        """`doctor` — строка о пределе по каждому проекту с источником.

        Сценарий: `config.FULL_SUITE_TIMEOUT_SEC` подменён значением C (от
        зерна); в `targets.yaml` — артель с `full_suite_timeout_sec: N`
        (N ≠ C), внешний проект с профилем без подполя и внешний проект без
        профиля (имена от зерна). В выводе `doctor` есть строка с именем
        артели, N и «профиль тестов проекта <имя артели>»; для каждого из
        двух внешних — строка с его именем, C и «config», без «профиль
        тестов проекта».

        Ловит мутацию: строка `doctor` берёт предел из config для всех
        проектов (у артели в строке C, а не N); источник всегда «config»;
        проект без профиля пропускается (`continue` по отсутствию поля) —
        строки о нём нет; значение константы взято при импорте, а не в
        момент вызова — в строках не C.
        """
        default = self.rng.randint(600, 999)
        limit = self.rng.randint(1000, 5000)
        with_field, without_field = self.word(), self.word()
        text = self.write_targets({
            config.DEFAULT_TARGET: with_limit(ARTEL_TEST_PROFILE, str(limit)),
            with_field: EXTERNAL_PROFILE,
            without_field: ""})
        with mock.patch.object(config, "FULL_SUITE_TIMEOUT_SEC", default):
            out = self.run_doctor()
        context = self.note(f"C={default}, N={limit}; targets.yaml:\n{text}\n"
                            f"вывод doctor:\n{out[-6000:]}")

        artel = re.compile(rf"профиль тестов проекта\W{{0,3}}"
                           rf"{re.escape(config.DEFAULT_TARGET)}(?![\w-])")
        rows = [line for line in self.limit_lines(out, config.DEFAULT_TARGET,
                                                  limit) if artel.search(line)]
        self.assertTrue(rows, self.note(
            f"нет строки артели с пределом {limit} и источником-профилем\n"
            f"{context}"))
        for name in (with_field, without_field):
            rows = [line for line in self.limit_lines(out, name, default)
                    if re.search(r"\bconfig\b", line)
                    and "профиль тестов проекта" not in line]
            self.assertTrue(rows, self.note(
                f"нет строки проекта {name} с пределом {default} и "
                f"источником config\n{context}"))


if __name__ == "__main__":
    unittest.main()
