"""
ВНИМАНИЕ: ОГРАНИЧЕНИЯ ШИФРОВАНИЯ НА УДАЛЁННОМ GPU

Шифрование защищает файл при передаче и хранении (зашифрованный файл на диске 
бесполезен без ключа). Однако эта схема НЕ ЗАЩИЩАЕТ от оператора арендованного сервера (например, на Vast.ai), 
который мог бы специально инспектировать память процесса во время обработки.
В этот момент сырой текст неизбежно существует в оперативной памяти инстанса.
Используйте только проверенные/высокорейтинговые хосты, если конфиденциальность переписки критична.
"""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os
import base64

def generate_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)

def generate_key_base64() -> str:
    return base64.b64encode(generate_key()).decode('utf-8')

def encrypt_file(plaintext_bytes: bytes, key: bytes) -> bytes:
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)  # 96-bit nonce, standard for GCM
    ciphertext = aesgcm.encrypt(nonce, plaintext_bytes, associated_data=None)
    return nonce + ciphertext

def decrypt_file(encrypted_bytes: bytes, key: bytes) -> bytes:
    nonce, ciphertext = encrypted_bytes[:12], encrypted_bytes[12:]
    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, associated_data=None)
