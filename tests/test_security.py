from app.security import password_hash, password_valid, token_hash

def test_password_is_argon2_hashed_and_verifiable():
    encoded = password_hash("a-long-enough-test-password")
    assert encoded.startswith("$argon2")
    assert password_valid("a-long-enough-test-password", encoded)
    assert not password_valid("wrong-password-value", encoded)

def test_session_token_hash_is_stable_and_not_plaintext():
    assert token_hash("example") == token_hash("example")
    assert token_hash("example") != "example"
