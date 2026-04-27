from app.core.security import decrypt_secret, encrypt_secret, mask_secret


def test_secret_round_trip_and_masking() -> None:
    encrypted = encrypt_secret("sk-test-123456")
    assert encrypted != "sk-test-123456"
    assert decrypt_secret(encrypted) == "sk-test-123456"
    assert mask_secret("sk-test-123456") == "sk-****3456"

