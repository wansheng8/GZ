"""预处理器指令（!#if / !#else / !#endif / !#include）单元测试。"""

from __future__ import annotations

from adblock_collection.preprocess import (
    TARGET_TOKENS,
    evaluate_condition,
    preprocess,
)


def test_evaluate_simple_tokens():
    assert evaluate_condition("ext_ublock", TARGET_TOKENS) is True
    assert evaluate_condition("adguard", TARGET_TOKENS) is True
    assert evaluate_condition("env_mobile", TARGET_TOKENS) is False
    assert evaluate_condition("false", TARGET_TOKENS) is False


def test_evaluate_operators_and_parens():
    assert evaluate_condition("!env_mobile", TARGET_TOKENS) is True
    assert evaluate_condition("env_mobile || ext_ublock", TARGET_TOKENS) is True
    assert evaluate_condition("env_mobile && ext_ublock", TARGET_TOKENS) is False
    assert (
        evaluate_condition("(env_firefox || env_chromium) && !env_mobile", TARGET_TOKENS)
        is False
    )
    assert evaluate_condition("!(env_mobile || env_firefox)", TARGET_TOKENS) is True


def test_evaluate_malformed_is_false():
    assert evaluate_condition("env_mobile &&", TARGET_TOKENS) is False
    assert evaluate_condition("(env_mobile", TARGET_TOKENS) is False
    assert evaluate_condition("", TARGET_TOKENS) is False


def test_preprocess_if_else_endif():
    lines = ["! head", "!#if ext_ublock", "keep", "!#else", "drop", "!#endif", "tail"]
    assert preprocess(lines) == ["! head", "keep", "tail"]


def test_preprocess_unknown_token_excludes_block():
    lines = ["!#if env_mobile", "mobile-only", "!#endif", "always"]
    assert preprocess(lines) == ["always"]


def test_preprocess_nested_conditions():
    lines = [
        "!#if ext_ublock",
        "a",
        "!#if env_mobile",
        "b",
        "!#else",
        "c",
        "!#endif",
        "d",
        "!#endif",
    ]
    assert preprocess(lines) == ["a", "c", "d"]


def test_preprocess_inactive_include_not_resolved():
    calls: list[str] = []

    def resolver(target: str) -> tuple[list[str], str] | None:
        calls.append(target)
        return ["inc"], target

    lines = ["!#if env_mobile", "!#include x.txt", "!#endif", "a"]
    assert preprocess(lines, resolve_include=resolver) == ["a"]
    assert calls == []


def test_preprocess_include_relative_and_nested():
    def resolver(target: str) -> tuple[list[str], str] | None:
        if target == "https://example.com/dir/a/list.txt":
            return ["!#include sub/b.txt", "||a.com^"], target
        if target == "https://example.com/dir/a/sub/b.txt":
            return ["||b.com^"], target
        return None

    out = preprocess(
        ["!#include a/list.txt", "||root.com^"],
        base_url="https://example.com/dir/",
        resolve_include=resolver,
    )
    assert out == ["||b.com^", "||a.com^", "||root.com^"]


def test_preprocess_include_cycle_guard():
    def resolver(target: str) -> tuple[list[str], str] | None:
        if target == "https://x/a.txt":
            return ["!#include https://x/a.txt"], target
        return None

    out = preprocess(
        ["!#include https://x/a.txt"],
        base_url="https://x/",
        resolve_include=resolver,
    )
    assert out == []


def test_preprocess_include_without_resolver_skipped():
    assert preprocess(["!#include a.txt", "keep"]) == ["keep"]


def test_preprocess_condition_applies_to_included_content():
    def resolver(target: str) -> tuple[list[str], str] | None:
        return ["!#if env_mobile", "mobile", "!#else", "generic", "!#endif"], target

    out = preprocess(
        ["!#include list.txt"],
        base_url="https://example.com/",
        resolve_include=resolver,
    )
    assert out == ["generic"]
