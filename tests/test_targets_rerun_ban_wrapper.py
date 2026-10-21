"""Граница запрета повторов в `targets.check`: команда-обёртка компонента
(голова не pytest) не проверяется (SPEC 01M5FRYVP4NF81VT00FYPHPWJH, «Не
входит»), а `-p` с безобидным плагином в конце списка — не отказ.
"""
import unittest

from orchestrator import targets


def entry(command: list, **extra) -> dict:
    comp = {"command": command, "long_lived_dir": "tests",
            "long_lived_name": "test_<id>_<name>.py",
            "weakening_scope": ["tests/**/*.py"],
            "mutation_claim_scope": ["tests/test_*.py"],
            "report": "junit-xml", "runner": "pytest-own",
            "report_args": ["--junitxml", "{path}"]}
    comp.update(extra)
    return {"forge": "github", "url": "http://127.0.0.1/demo.git",
            "base": "main", "token_slot": "demo-token", "no_paths": [],
            "project_skills": [], "merge_gate": "operator",
            "components": {"web": comp}}


class RerunBanBoundaryTest(unittest.TestCase):

    def test_wrapper_command_not_checked(self):
        """Компонент с командой-обёрткой `sh -c …` и `--reruns` в аргументах — без отказа; та же запись с командой pytest — отказ.

        Ловит мутацию: проверка запрета применяется к любой команде, не
        только к pytest (обёртка, которую пульт не разбирает, получает
        ложный отказ); проверка не применяется и к команде pytest.
        """
        targets.check("demo", entry(["sh", "-c", "run-tests"],
                                    report_args=["--junitxml", "{path}",
                                                 "--reruns", "2"]))
        with self.assertRaises(targets.TargetsError):
            targets.check("demo", entry(["python3", "-m", "pytest"],
                                        report_args=["--junitxml", "{path}",
                                                     "--reruns", "2"]))

    def test_trailing_p_and_prefix_lookalikes_not_refused(self):
        """`-p` последним элементом и флаги, лишь начинающиеся с запрещённого (`--reruns-only`), — без отказа.

        Ловит мутацию: запрещённый флаг сверяется префиксом без `=`
        (`--reruns-only` получает ложный отказ); `-p` в конце списка
        роняет проверку `IndexError`.
        """
        targets.check("demo", entry(["python3", "-m", "pytest",
                                     "--reruns-only", "-p"]))


if __name__ == "__main__":
    unittest.main()
