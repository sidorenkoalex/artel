"""`target-set`: краевые случаи правила комментария и значения, не покрытые долгоживущими файлами задачи 01M6KBD9FC36WARWSY9Z0JDMG5.

Песочница — `initialized_tmp_root` (пути `config` во временном каталоге);
команда зовётся через `artel.main()` с подменённым `sys.argv`.
"""
import sys
from unittest import mock

from orchestrator import artel, config, yamlmini
from tests.sandbox import artel_target_entry

RECORD = ("targets:\n  sandbox:\n"
          "    description:\n      base: main\n      components:\n"
          "        app:\n          runner: pytest-own\n"
          "          command: [python3, -m, pytest]\n"
          "          report: junit-xml\n          paths: ^app/\n"
          "          long_lived: app/tests/test_<id>_<name>.py\n"
          "    policy:\n      no_paths: []\n      project_skills: []\n"
          "      merge_gate: operator\n"
          "    machine:\n      forge: github\n"
          "      url: https://localhost/team/sandbox\n"
          "      token_slot: sandbox-token\n")


def local_file():
    return config.TARGETS.parent / ".artel" / "targets.yaml"


def write_layers(text: str) -> None:
    config.TARGETS.write_text("targets:\n" + artel_target_entry(), encoding="utf-8")
    local_file().parent.mkdir(parents=True, exist_ok=True)
    local_file().write_text(text, encoding="utf-8")


def run(*argv) -> bool:
    with mock.patch.object(sys, "argv", ["artel.py", *argv]):
        try:
            artel.main()
        except SystemExit as exc:
            return exc.code in (0, None)
    return True


def test_comment_after_block_key_refused(initialized_tmp_root):
    """Комментарий сразу после ключа блока (`policy:  # x`) — отказ, файл прежний.

    Ловит мутацию: правило комментария смотрит только хвост после
    непустого значения — `#` в начале значения после `:` пропущен, и
    пересборка молча стирает комментарий.
    """
    text = RECORD.replace("    policy:\n", "    policy:  # note\n", 1)
    write_layers(text)
    before = local_file().read_bytes()
    assert not run("target-set", "sandbox", "policy.sandbox", "box")
    assert local_file().read_bytes() == before


def test_hash_without_space_is_value(initialized_tmp_root):
    """Значение `a#b` (`#` не после пробела) — не комментарий: записано целиком.

    Ловит мутацию: проверка потери текста ищет `#` в любом месте значения
    — `a#b` отвергнут; либо значение записано не той строкой.
    """
    write_layers(RECORD)
    assert run("target-set", "sandbox", "policy.sandbox", "a#b")
    data = yamlmini.mapping(local_file().read_text(encoding="utf-8"))
    assert data["targets"]["sandbox"]["policy"]["sandbox"] == "a#b"
