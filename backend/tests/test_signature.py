from app.meta.signature import is_valid_signature, sign

# Reference value computed outside the app:
#   printf '%s' '{"object":"instagram","entry":[]}' | openssl dgst -sha256 -hmac 'test-app-secret'
BODY = b'{"object":"instagram","entry":[]}'
EXPECTED = "sha256=bb441adf604237753804d2f51dbef920e26f17e8c1155dbe818684eb2b577890"


def test_signature_matches_an_independently_computed_value() -> None:
    assert sign(BODY, "test-app-secret") == EXPECTED
    assert is_valid_signature(BODY, EXPECTED, "test-app-secret")
    assert is_valid_signature(BODY, EXPECTED.upper().replace("SHA256=", "sha256="), "test-app-secret")


def test_signature_rejects_tampering_and_an_empty_secret() -> None:
    assert not is_valid_signature(BODY + b" ", EXPECTED, "test-app-secret")
    assert not is_valid_signature(BODY, EXPECTED, "other-secret")
    assert not is_valid_signature(BODY, sign(BODY, ""), "")
    assert not is_valid_signature(BODY, None, "test-app-secret")
