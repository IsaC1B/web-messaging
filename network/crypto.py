import base64
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


DEFAULT_PRIVATE_KEY_ENV = "P2P_RSA_PRIVATE_KEY_PASSWORD"


def _safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", value)


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("ascii"))


@dataclass(slots=True)
class StoredKeyPaths:
    private_key: Path
    public_key: Path


class HybridCryptoBox:
    def __init__(self, node_id: str, storage_dir: Path | None = None, private_key_password: str | None = None):
        self.node_id = node_id
        self.storage_dir = storage_dir or Path(__file__).resolve().parent / "keys"
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        env_password = os.environ.get(DEFAULT_PRIVATE_KEY_ENV)
        self.private_key_password = private_key_password if private_key_password is not None else env_password

        safe_node_id = _safe_name(node_id)
        self.paths = StoredKeyPaths(
            private_key=self.storage_dir / f"{safe_node_id}_private.pem",
            public_key=self.storage_dir / f"{safe_node_id}_public.txt",
        )

        self._private_key = None
        self._public_key = None
        self._ensure_keys()

    def _ensure_keys(self) -> None:
        if self.paths.private_key.exists() and self.paths.public_key.exists():
            self._load_keys()
            return

        self._private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self._public_key = self._private_key.public_key()
        self._write_keys()

    def _load_keys(self) -> None:
        private_key_bytes = self.paths.private_key.read_bytes()
        password_bytes = self.private_key_password.encode("utf-8") if self.private_key_password else None
        self._private_key = serialization.load_pem_private_key(private_key_bytes, password=password_bytes)
        self._public_key = self._private_key.public_key()

    def _write_keys(self) -> None:
        password_bytes = self.private_key_password.encode("utf-8") if self.private_key_password else None
        encryption_algorithm = (
            serialization.BestAvailableEncryption(password_bytes)
            if password_bytes
            else serialization.NoEncryption()
        )

        private_key_bytes = self._private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=encryption_algorithm,
        )
        public_key_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        self.paths.private_key.write_bytes(private_key_bytes)
        self.paths.public_key.write_text(public_key_bytes.decode("utf-8"), encoding="utf-8")

    @property
    def private_key(self):
        return self._private_key

    @property
    def public_key(self):
        return self._public_key

    @property
    def public_key_pem(self) -> str:
        return self.paths.public_key.read_text(encoding="utf-8")

    def encrypt_for_peer(self, peer_public_key_pem: str, message: str) -> dict:
        peer_public_key = serialization.load_pem_public_key(peer_public_key_pem.encode("utf-8"))

        aes_key = os.urandom(32)
        nonce = os.urandom(12)
        ciphertext = AESGCM(aes_key).encrypt(nonce, message.encode("utf-8"), None)

        encrypted_key = peer_public_key.encrypt(
            aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        return {
            "algorithm": "rsa-oaep+aes-gcm",
            "encrypted_key": _b64encode(encrypted_key),
            "nonce": _b64encode(nonce),
            "ciphertext": _b64encode(ciphertext),
        }

    def decrypt_payload(self, payload: dict) -> str:
        encrypted_key = _b64decode(payload["encrypted_key"])
        nonce = _b64decode(payload["nonce"])
        ciphertext = _b64decode(payload["ciphertext"])

        aes_key = self._private_key.decrypt(
            encrypted_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            ),
        )

        plaintext = AESGCM(aes_key).decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")

    def public_key_message(self) -> str:
        return json.dumps({
            "type": "hello",
            "node_id": self.node_id,
            "public_key": self.public_key_pem,
        })
