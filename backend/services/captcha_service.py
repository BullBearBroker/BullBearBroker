from backend.utils.config import Config


class CaptchaVerificationError(Exception):
    """Raised when the CAPTCHA challenge is missing or invalid."""


def verify_captcha(token: str | None) -> None:
    expected = Config.LOGIN_CAPTCHA_TEST_SECRET or "pass"
    if not token:
        raise CaptchaVerificationError("captcha_required")
    if token != expected:
        raise CaptchaVerificationError("captcha_invalid")
