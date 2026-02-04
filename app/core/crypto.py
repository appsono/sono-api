from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives import hashes
import base64
import os


class CryptoHandler:
    def __init__(self):
        private_key_path = os.path.join(os.path.dirname(__file__), "keys", "private_key.pem")
        with open(private_key_path, "rb") as key_file:
            self.private_key = serialization.load_pem_private_key(key_file.read(), password=None)

    def decrypt_password(self, encrypted_password: str) -> str:
        try:
            encrypted_bytes = base64.b64decode(encrypted_password)

            decrypted_bytes = self.private_key.decrypt(encrypted_bytes, padding.OAEP(mgf=padding.MGF1(algorithm=hashes.SHA256()), algorithm=hashes.SHA256(), label=None))

            return decrypted_bytes.decode("utf-8")
        except Exception as e:
            raise ValueError(f"Failed to decrypt password: {str(e)}")
