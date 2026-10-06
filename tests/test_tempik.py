"""Unit test OTP extraction from the Tempik provider without internet access."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from grokforge.tempmail.providers.tempik import TempikEmail

HTML_FILE = "html lang=enhead.txt"


def load_html() -> str:
    if not os.path.exists(HTML_FILE):
        return ""
    with open(HTML_FILE, encoding="utf-8") as f:
        return f.read()


def test_data_otp(html: str) -> None:
    tm = TempikEmail("77bgvgwh@neroism.web.id")
    code = tm._extract_from_text(html)
    assert code == "338277", f"expected 338277, got {code}"
    print(f"[PASS] data-otp -> {code}")


def test_subject_pattern() -> None:
    tm = TempikEmail("x@neroism.web.id")
    assert tm._extract_from_text("SpaceXAI sign-in code: 338-277") == "338277"
    assert tm._extract_from_text("SpaceXAI confirmation code: 810-245") == "810245"
    print("[PASS] subject pattern OK")


def test_reject_alpha_6() -> None:
    tm = TempikEmail("x@neroism.web.id")
    for word in ("FOOTER", "HEADER", "NAVBAR", "BUTTON", "SCRIPT"):
        assert tm._extract_from_text(f"<div>{word}</div>") is None, f"must reject {word}"
    print("[PASS] 6-letter all-alpha strings rejected")


def test_banner_pattern() -> None:
    tm = TempikEmail("x@neroism.web.id")
    html = '<div class="otp-banner-code" id="otpBannerCode">999-111</div>'
    assert tm._extract_from_text(html) == "999111"
    print("[PASS] banner pattern OK")


def test_generic_hyphen() -> None:
    tm = TempikEmail("x@neroism.web.id")
    assert tm._extract_from_text("code is 512-877 here") == "512877"
    print("[PASS] generic hyphen pattern OK")


def test_message_dict() -> None:
    tm = TempikEmail("x@neroism.web.id")
    msg = {"subject": "SpaceXAI sign-in code: 338-277", "body": "..."}
    assert tm._extract_from_payload(msg) == "338277"
    print("[PASS] dict extraction OK")


if __name__ == "__main__":
    html = load_html()
    if html:
        test_data_otp(html)
    test_subject_pattern()
    test_reject_alpha_6()
    test_banner_pattern()
    test_generic_hyphen()
    test_message_dict()
    print("\nAll tests passed")