from pathlib import Path

from adblock_collection.cli import _build_parser, lint_cmd
from adblock_collection.lint import lint_lines, lint_text

SAFE = {"level": "safe", "min_confidence": 0.8, "allow_modifier": True}


def test_valid_rules_have_no_issues():
    report = lint_lines(
        [
            "! comment",
            "[Adblock Plus 2.0]",
            "||ads.example.com^",
            "example.com##.ad-banner",
            "example.com#?#.promo:has-text(Ad)",
            "@@||allowed.example.com^",
        ]
    )
    assert report.errors == []
    assert report.warnings == []


def test_hash_prefixed_comment_is_ignored():
    report = lint_lines(
        [
            "# ||pop.example.com^$subdocument,popup,third-party",
            "# ||bogus.example.com^$not-a-real-option",
        ]
    )
    assert report.issues == []


def test_empty_selector_is_error():
    report = lint_lines(["example.com##"])
    assert [i.level for i in report.issues] == ["error"]


def test_empty_option_is_error():
    report = lint_lines(["||ads.example.com^$"])
    assert any(i.level == "error" for i in report.issues)


def test_unknown_option_is_warning():
    report = lint_lines(["||ads.example.com^$totally-bogus"])
    assert any("未知选项名" in i.message for i in report.warnings)
    assert report.errors == []


def test_dangling_badfilter_is_warning():
    report = lint_lines(["||ads.example.com^$badfilter"])
    assert any("badfilter" in i.message for i in report.warnings)


def test_dangling_legacy_badfilter_is_warning():
    report = lint_lines(["||ads.example.com^,badfilter"])
    assert any("badfilter" in i.message for i in report.warnings)


def test_matched_badfilter_has_no_warning():
    report = lint_lines(["||ads.example.com^", "||ads.example.com^$badfilter"])
    assert not any("badfilter" in i.message for i in report.warnings)


def test_duplicate_is_warning():
    report = lint_lines(["||ads.example.com^", "||ads.example.com^"])
    assert any("重复" in i.message for i in report.warnings)


def test_block_and_exception_conflict_is_warning():
    report = lint_lines(["||ads.example.com^", "@@||ads.example.com^"])
    assert any("阻断与例外" in i.message for i in report.warnings)


def test_dns_and_browser_split():
    text = (
        "||whole.example.com^\n"
        "||typed.example.com^$script\n"
        "||party.example.com^$third-party\n"
        "example.com##.ad"
    )
    report = lint_text(text, policy=SAFE)
    assert report.dns_domains == ["whole.example.com"]
    assert "||typed.example.com^$script" in report.browser_rules
    assert "||party.example.com^$third-party" in report.browser_rules
    assert "example.com##.ad" in report.browser_rules


def test_lint_cli_clean_file(tmp_path, capsys):
    rules = tmp_path / "local.txt"
    rules.write_text("||ads.example.com^\nexample.com##.ad\n", encoding="utf-8")
    args = _build_parser().parse_args(["lint", "--rules", str(rules)])
    assert lint_cmd(args) == 0


def test_lint_cli_error_exit_code(tmp_path):
    rules = tmp_path / "local.txt"
    rules.write_text("example.com##\n", encoding="utf-8")
    args = _build_parser().parse_args(["lint", "--rules", str(rules)])
    assert lint_cmd(args) == 2


def test_lint_cli_strict_promotes_warnings(tmp_path):
    rules = tmp_path / "local.txt"
    rules.write_text("||ads.example.com^$totally-bogus\n", encoding="utf-8")
    args = _build_parser().parse_args(["lint", "--rules", str(rules)])
    assert lint_cmd(args) == 0
    strict = _build_parser().parse_args(
        ["lint", "--rules", str(rules), "--strict"]
    )
    assert lint_cmd(strict) == 2


def test_lint_cli_split_dir(tmp_path):
    rules = tmp_path / "local.txt"
    rules.write_text("||ads.example.com^\nexample.com##.ad\n", encoding="utf-8")
    split = tmp_path / "split"
    args = _build_parser().parse_args(
        ["lint", "--rules", str(rules), "--dns-policy", "safe", "--split-dir", str(split)]
    )
    assert lint_cmd(args) == 0
    assert (split / "lint_dns_domains.txt").read_text(encoding="utf-8").count(
        "ads.example.com"
    ) == 1
    browser = (split / "lint_browser_rules.txt").read_text(encoding="utf-8")
    assert "example.com##.ad" in browser


def test_repo_local_rules_are_clean():
    path = Path("config/local_rules.txt")
    report = lint_text(path.read_text(encoding="utf-8"), source=str(path))
    assert report.errors == [], [i.to_dict() for i in report.errors]
    assert report.warnings == [], [i.to_dict() for i in report.warnings]
