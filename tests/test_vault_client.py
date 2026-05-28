from __future__ import annotations

import base64

from shared.vault_client import VaultClient


class FakeKVV2:
    def __init__(self):
        self.store = {}

    def read_secret_version(self, *, path, mount_point, raise_on_deleted_version=True):
        return {"data": {"data": self.store[(mount_point, path)]}}

    def create_or_update_secret(self, *, path, secret, mount_point):
        self.store[(mount_point, path)] = secret


class FakeTransit:
    def encrypt_data(self, *, name, plaintext, mount_point):
        return {"data": {"ciphertext": f"vault:v1:{name}:{plaintext}"}}

    def decrypt_data(self, *, name, ciphertext, mount_point):
        prefix = f"vault:v1:{name}:"
        assert ciphertext.startswith(prefix)
        return {"data": {"plaintext": ciphertext.removeprefix(prefix)}}


class FakePKI:
    def generate_certificate(self, *, name, common_name, ttl, mount_point):
        return {
            "data": {
                "certificate": f"cert:{common_name}",
                "private_key": "private-key",
                "issuing_ca": "ca",
                "serial_number": "01:02",
            }
        }


class FakeAppRole:
    def login(self, *, role_id, secret_id):
        assert role_id == "role-id"
        assert secret_id == "secret-id"
        return {"auth": {"client_token": "client-token"}}


class FakeAuth:
    def __init__(self):
        self.approle = FakeAppRole()


class FakeSecrets:
    def __init__(self):
        self.kv = type("FakeKV", (), {"v2": FakeKVV2()})()
        self.transit = FakeTransit()
        self.pki = FakePKI()


class FakeHVACClient:
    def __init__(self):
        self.auth = FakeAuth()
        self.secrets = FakeSecrets()
        self.token = None


def test_authenticate_approle_sets_client_token():
    fake = FakeHVACClient()
    vault = VaultClient(client=fake)

    vault.authenticate_approle(role_id="role-id", secret_id="secret-id")

    assert fake.token == "client-token"


def test_kv_v2_secret_helpers_clean_paths():
    vault = VaultClient(client=FakeHVACClient())

    vault.put_secret("secret/services/resource-service/db_password", {"value": "db-pass"})

    assert vault.get_secret("services/resource-service/db_password") == "db-pass"
    assert vault.get_secret_dict("secret/data/services/resource-service/db_password") == {"value": "db-pass"}


def test_transit_encrypt_decrypt_uses_tenant_key_name():
    vault = VaultClient(client=FakeHVACClient())

    ciphertext = vault.encrypt("11111111-1111-1111-1111-111111111111", "hello-alpha")

    assert ciphertext.startswith("vault:v1:tenant-11111111-1111-1111-1111-111111111111:")
    assert vault.decrypt("11111111-1111-1111-1111-111111111111", ciphertext) == b"hello-alpha"


def test_issue_certificate_maps_pki_response():
    vault = VaultClient(client=FakeHVACClient())

    cert = vault.issue_certificate("resource-service.service.local")

    assert cert.certificate == "cert:resource-service.service.local"
    assert cert.private_key == "private-key"
    assert cert.issuing_ca == "ca"
    assert cert.serial_number == "01:02"
