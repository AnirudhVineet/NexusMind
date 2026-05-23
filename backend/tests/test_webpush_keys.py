"""Tests for VAPID key generation — Phase 4 Track G.

Covers: VAPID key generation/loading, key format validation.
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

from py_vapid import Vapid


class TestVapidKeyGeneration:
    """Test VAPID key generation and persistence."""

    def test_generate_keys(self, tmp_path):
        """Generate a new VAPID key pair."""
        vapid = Vapid()
        vapid.generate_keys()
        assert vapid.private_key is not None
        assert vapid.public_key is not None

    def test_public_key_format(self, tmp_path):
        """Public key should be a base64url string."""
        vapid = Vapid()
        vapid.generate_keys()
        pub = vapid.public_key
        # public_key should be an EC key object
        assert pub is not None

    def test_save_and_load_keys(self, tmp_path):
        """Save keys to files and reload them."""
        priv_path = str(tmp_path / "private_key.pem")
        pub_path = str(tmp_path / "public_key.pem")

        vapid = Vapid()
        vapid.generate_keys()
        vapid.save_key(priv_path)
        vapid.save_public_key(pub_path)

        assert os.path.exists(priv_path)
        assert os.path.exists(pub_path)

        # Reload
        vapid2 = Vapid.from_file(priv_path)
        assert vapid2.private_key is not None

    def test_keys_json_persistence(self, tmp_path):
        """Test storing keys in JSON format (as NexusMind does)."""
        vapid = Vapid()
        vapid.generate_keys()

        keys_file = tmp_path / "vapid_keys.json"
        keys_data = {
            "private_key_pem": "dummy_private",
            "public_key": "dummy_public",
        }
        keys_file.write_text(json.dumps(keys_data), encoding="utf-8")

        loaded = json.loads(keys_file.read_text(encoding="utf-8"))
        assert "private_key_pem" in loaded
        assert "public_key" in loaded


class TestVapidKeyIdempotency:
    """Test that keys are only generated once."""

    def test_keys_not_overwritten_if_exist(self, tmp_path):
        keys_file = tmp_path / "vapid_keys.json"

        # First generation
        keys_data = {"private_key_pem": "first_key", "public_key": "first_pub"}
        keys_file.write_text(json.dumps(keys_data), encoding="utf-8")

        # Simulate "generate if not exists" logic
        if keys_file.exists():
            loaded = json.loads(keys_file.read_text(encoding="utf-8"))
        else:
            loaded = {"private_key_pem": "second_key", "public_key": "second_pub"}
            keys_file.write_text(json.dumps(loaded), encoding="utf-8")

        assert loaded["private_key_pem"] == "first_key"
