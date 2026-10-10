"""Pruebas del hashing de contraseñas: bcrypt directo, compatible con passlib."""

from app.core.passwords import hash_password, verify_password

# Hash generado con passlib 1.7.4 + bcrypt 4.0.1 (implementación anterior),
# para garantizar que los usuarios existentes siguen pudiendo iniciar sesión.
_LEGACY_HASH = "$2b$12$rPa2oMfjHPnvs/kHaLvscul1HOc49xsrsY3KBzA4NoTBmxz3Tr0SS"


def test_hash_and_verify_roundtrip():
    hashed = hash_password("micontraseña-123")
    assert hashed.startswith("$2b$")
    assert verify_password("micontraseña-123", hashed)
    assert not verify_password("otra-contraseña", hashed)


def test_legacy_passlib_hashes_still_verify():
    assert verify_password("secret123", _LEGACY_HASH)
    assert not verify_password("incorrecta", _LEGACY_HASH)


def test_verify_never_raises_on_malformed_hash():
    assert not verify_password("algo", "")
    assert not verify_password("algo", "no-es-un-hash")
    assert not verify_password("algo", None)
    assert not verify_password("", _LEGACY_HASH)


def test_long_passwords_are_truncated_like_passlib():
    largo = "x" * 100
    hashed = hash_password(largo)
    assert verify_password("x" * 100, hashed)
    # Los primeros 72 bytes definen la contraseña (mismo comportamiento que passlib).
    assert verify_password("x" * 72, hashed)
    assert not verify_password("y" + "x" * 71, hashed)
