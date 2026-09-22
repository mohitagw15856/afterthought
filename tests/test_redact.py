from afterthought.redact import redact


def test_emails_and_allowlist() -> None:
    text, rep = redact("mail me at a.b+c@example.co.uk or keep@ok.org", allow_emails=("keep@ok.org",))
    assert "[REDACTED:email]" in text and "keep@ok.org" in text
    assert rep.emails == 1


def test_tokens() -> None:
    samples = [
        "key sk-ant-api03-abcdefghijklmnopqrstuvwxyz0123456789",
        "9f8e7d6c5b4a39281706f5e4d3c2b1a0",
        "ghp_abcdefghijklmnopqrstuvwxyz0123456789",
        "xoxb-1234567890-abcdefghij",
        "AKIAABCDEFGHIJKLMNOP",
        "Authorization: Bearer abcdefghijklmnopqrstuvwxyz.0123456789",
        "api_key = 'abcdefghijklmnop1234'",
    ]
    for s in samples:
        text, rep = redact(s)
        assert rep.tokens >= 1, s
        assert "[REDACTED:token]" in text, s
    assert redact("api_key = 'abcdefghijklmnop1234'")[0].startswith("api_key = '")


def test_cards_need_luhn() -> None:
    ok, rep = redact("card 4111 1111 1111 1111 please")
    assert rep.cards == 1 and "[REDACTED:card]" in ok
    bad, rep2 = redact("order 1234 5678 9012 3456")
    assert rep2.cards == 0 and "1234 5678" in bad


def test_idempotent() -> None:
    once, _ = redact("x@y.com 9f8e7d6c5b4a39281706f5e4d3c2b1a0 4111111111111111")
    twice, rep = redact(once)
    assert once == twice and rep.total == 0


def test_key_in_prose() -> None:
    text, rep = redact("and my API key is 9f8e7d6c5b4a39281706f5e4d3c2b1a0 in case that matters")
    assert rep.tokens == 1 and "9f8e7d6c" not in text and "API key is [REDACTED:token]" in text
    assert redact("the token is invalid")[1].tokens == 0
