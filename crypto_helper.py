"""
SMTP Password Encryption Helper
Encrypts SMTP passwords using AES-256-GCM for secure transmission to email service
"""

import os
import base64
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def get_encryption_key() -> bytes:
    """Get encryption key from environment variable"""
    key_base64 = os.getenv('SMTP_PASSWORD_ENCRYPTION_KEY')
    if not key_base64:
        raise ValueError("SMTP_PASSWORD_ENCRYPTION_KEY not set in environment")

    key = base64.b64decode(key_base64)
    if len(key) != 32:
        raise ValueError(f"Encryption key must be 32 bytes (got {len(key)})")

    return key


def encrypt_smtp_password(plain_password: str) -> str:
    """
    Encrypt SMTP password using AES-256-GCM

    Args:
        plain_password: Plain text password

    Returns:
        Encrypted password in format: encrypted:{nonce_base64}:{ciphertext_base64}
    """
    # Get encryption key
    encryption_key = get_encryption_key()

    # Generate random nonce (12 bytes for GCM)
    nonce = os.urandom(12)

    # Create AESGCM cipher
    aesgcm = AESGCM(encryption_key)

    # Encrypt (returns ciphertext + auth tag)
    ciphertext = aesgcm.encrypt(nonce, plain_password.encode('utf-8'), None)

    # Encode to base64
    nonce_b64 = base64.b64encode(nonce).decode('utf-8')
    ciphertext_b64 = base64.b64encode(ciphertext).decode('utf-8')

    # Return format: "encrypted:{nonce}:{ciphertext}"
    return f"encrypted:{nonce_b64}:{ciphertext_b64}"


if __name__ == "__main__":
    # Test encryption
    from dotenv import load_dotenv
    load_dotenv()

    test_password = "myTestPassword123"
    print(f"Plain password: {test_password}")

    encrypted = encrypt_smtp_password(test_password)
    print(f"Encrypted: {encrypted}")
    print(f"Length: {len(encrypted)} characters")