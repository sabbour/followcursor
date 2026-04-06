"""Tests for app.credentials — DPAPI encryption for API keys."""

import pytest
from unittest.mock import patch, MagicMock
import base64

from app import credentials


# ── Roundtrip Tests ─────────────────────────────────────────────────


class TestProtectUnprotectRoundtrip:
    """Verify that protect → unprotect recovers the original value."""

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_roundtrip_ascii_string(self) -> None:
        """Encrypt and decrypt a simple ASCII API key."""
        original = "sk-test1234567890abcdef"
        encrypted = credentials.protect(original)
        assert encrypted != original
        assert encrypted.startswith("dpapi:")
        decrypted = credentials.unprotect(encrypted)
        assert decrypted == original

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_roundtrip_unicode_string(self) -> None:
        """Encrypt and decrypt a string with Unicode characters."""
        original = "sk-🔑-test-key-émoji"
        encrypted = credentials.protect(original)
        assert encrypted.startswith("dpapi:")
        decrypted = credentials.unprotect(encrypted)
        assert decrypted == original

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_roundtrip_long_string(self) -> None:
        """Encrypt and decrypt a very long API key (256 chars)."""
        original = "x" * 256
        encrypted = credentials.protect(original)
        assert encrypted.startswith("dpapi:")
        decrypted = credentials.unprotect(encrypted)
        assert decrypted == original


# ── Edge Cases ──────────────────────────────────────────────────────


class TestEdgeCases:
    """Test empty strings, whitespace, and boundary conditions."""

    def test_protect_empty_string(self) -> None:
        """Empty string should return empty string (no encryption)."""
        result = credentials.protect("")
        assert result == ""

    def test_unprotect_empty_string(self) -> None:
        """Empty string should return empty string."""
        result = credentials.unprotect("")
        assert result == ""

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_protect_whitespace_only(self) -> None:
        """Whitespace-only strings should be encrypted normally."""
        original = "   "
        encrypted = credentials.protect(original)
        assert encrypted.startswith("dpapi:")
        decrypted = credentials.unprotect(encrypted)
        assert decrypted == original

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_protect_single_char(self) -> None:
        """Single character should be encrypted."""
        original = "x"
        encrypted = credentials.protect(original)
        assert encrypted.startswith("dpapi:")
        decrypted = credentials.unprotect(encrypted)
        assert decrypted == original


# ── Legacy Plaintext Handling ───────────────────────────────────────


class TestLegacyPlaintext:
    """Verify backward compatibility with old unencrypted values."""

    def test_unprotect_legacy_plaintext(self) -> None:
        """Old plaintext values (no 'dpapi:' prefix) should pass through."""
        plaintext = "old-api-key-from-v1.0"
        result = credentials.unprotect(plaintext)
        assert result == plaintext

    def test_unprotect_legacy_plaintext_with_special_chars(self) -> None:
        """Legacy plaintext with base64-like chars should still pass through."""
        plaintext = "sk-1234+/==567890"
        result = credentials.unprotect(plaintext)
        assert result == plaintext

    def test_unprotect_legacy_plaintext_looks_like_base64(self) -> None:
        """Even if it looks like base64, no 'dpapi:' prefix means plaintext."""
        plaintext = base64.b64encode(b"not-encrypted").decode("ascii")
        result = credentials.unprotect(plaintext)
        assert result == plaintext


# ── Non-Windows Platform Behavior ───────────────────────────────────


class TestNonWindowsPlatform:
    """Test behavior on platforms without DPAPI."""

    def test_protect_on_non_windows_returns_plaintext(self) -> None:
        """On non-Windows, protect() returns plaintext with a warning."""
        with patch.object(credentials, "_HAS_DPAPI", False):
            original = "sk-test-key"
            result = credentials.protect(original)
            # Should return plaintext unchanged
            assert result == original
            assert not result.startswith("dpapi:")

    def test_unprotect_dpapi_blob_on_non_windows_raises(self) -> None:
        """Attempting to decrypt a DPAPI blob on non-Windows must raise."""
        with patch.object(credentials, "_HAS_DPAPI", False):
            fake_blob = "dpapi:VGVzdEJsb2I="
            with pytest.raises(RuntimeError, match="DPAPI is only available on Windows"):
                credentials.unprotect(fake_blob)

    def test_unprotect_plaintext_on_non_windows_works(self) -> None:
        """Legacy plaintext values should work fine on non-Windows."""
        with patch.object(credentials, "_HAS_DPAPI", False):
            plaintext = "old-api-key"
            result = credentials.unprotect(plaintext)
            assert result == plaintext


# ── DPAPI Decryption Failures ───────────────────────────────────────


class TestDecryptionFailures:
    """Test error handling when DPAPI decryption fails."""

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_unprotect_invalid_base64_raises(self) -> None:
        """Invalid base64 in 'dpapi:' blob should raise RuntimeError."""
        bad_blob = "dpapi:not-valid-base64!@#$"
        with pytest.raises(RuntimeError, match="Failed to decrypt"):
            credentials.unprotect(bad_blob)

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_unprotect_corrupted_dpapi_blob_raises(self) -> None:
        """Valid base64 but corrupted DPAPI data should raise RuntimeError."""
        # Valid base64 but not a real DPAPI blob
        fake_blob = "dpapi:" + base64.b64encode(b"garbage-data-not-dpapi").decode("ascii")
        with pytest.raises(RuntimeError, match="Failed to decrypt"):
            credentials.unprotect(fake_blob)

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_unprotect_empty_dpapi_blob_raises(self) -> None:
        """Empty DPAPI blob (just 'dpapi:') should raise RuntimeError."""
        empty_blob = "dpapi:"
        with pytest.raises(RuntimeError, match="Failed to decrypt"):
            credentials.unprotect(empty_blob)


# ── DPAPI API Failure Simulation ────────────────────────────────────


class TestDPAPIAPIFailures:
    """Simulate DPAPI API call failures."""

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_protect_when_crypt_protect_data_fails(self) -> None:
        """If CryptProtectData returns FALSE, protect() falls back to plaintext."""
        original = "sk-test-key"
        
        # Mock _crypt32.CryptProtectData to return 0 (failure)
        with patch.object(credentials._crypt32, "CryptProtectData", return_value=0):
            result = credentials.protect(original)
            # Should fall back to plaintext
            assert result == original
            assert not result.startswith("dpapi:")

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_protect_when_crypt_protect_data_raises(self) -> None:
        """If CryptProtectData raises an exception, protect() falls back to plaintext."""
        original = "sk-test-key"
        
        with patch.object(
            credentials._crypt32,
            "CryptProtectData",
            side_effect=Exception("DPAPI system failure")
        ):
            result = credentials.protect(original)
            # Should fall back to plaintext
            assert result == original
            assert not result.startswith("dpapi:")

    @pytest.mark.skipif(
        not credentials._HAS_DPAPI,
        reason="DPAPI only available on Windows"
    )
    def test_unprotect_when_crypt_unprotect_data_fails(self) -> None:
        """If CryptUnprotectData returns FALSE, unprotect() must raise RuntimeError."""
        # First, create a real encrypted blob
        original = "sk-test-key"
        encrypted = credentials.protect(original)
        assert encrypted.startswith("dpapi:")
        
        # Now mock CryptUnprotectData to fail
        with patch.object(credentials._crypt32, "CryptUnprotectData", return_value=0):
            with pytest.raises(RuntimeError, match="Failed to decrypt"):
                credentials.unprotect(encrypted)


# ── Prefix Edge Cases ───────────────────────────────────────────────


class TestPrefixEdgeCases:
    """Test edge cases around the 'dpapi:' prefix."""

    def test_unprotect_dpapi_prefix_only(self) -> None:
        """Just 'dpapi:' with no data should raise."""
        with pytest.raises(RuntimeError):
            credentials.unprotect("dpapi:")

    def test_unprotect_case_sensitive_prefix(self) -> None:
        """Prefix is case-sensitive — 'DPAPI:' is treated as legacy plaintext."""
        result = credentials.unprotect("DPAPI:somedata")
        # Should be treated as legacy plaintext (not encrypted)
        assert result == "DPAPI:somedata"

    def test_protect_result_always_has_prefix_when_encrypted(self) -> None:
        """On Windows, successful encryption must include 'dpapi:' prefix."""
        if not credentials._HAS_DPAPI:
            pytest.skip("DPAPI only available on Windows")
        
        original = "sk-test-key"
        encrypted = credentials.protect(original)
        if encrypted != original:  # If it was encrypted (not a fallback)
            assert encrypted.startswith("dpapi:")
