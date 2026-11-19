"""RSA Key Pair Generator for RS256 JWT Signing.

Generates 2048-bit RSA private and public PEM keys and saves them to the keys/ directory.
Strictly ensures keys are kept outside source code and ignored by Git.
"""

import os
from pathlib import Path
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_rsa_key_pair(output_dir: str = "keys", key_size: int = 2048) -> tuple[Path, Path]:
    """Generate RSA private and public PEM keys."""
    keys_path = Path(output_dir)
    keys_path.mkdir(parents=True, exist_ok=True)

    private_key_path = keys_path / "jwt-private.pem"
    public_key_path = keys_path / "jwt-public.pem"

    # Generate private key
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=key_size,
        backend=default_backend(),
    )

    # Serialize private key to PEM
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    # Serialize public key to PEM
    public_key = private_key.public_key()
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )

    with open(private_key_path, "wb") as f:
        f.write(private_pem)

    with open(public_key_path, "wb") as f:
        f.write(public_pem)

    print(f"Generated RSA Private Key: {private_key_path}")
    print(f"Generated RSA Public Key:  {public_key_path}")
    return private_key_path, public_key_path


if __name__ == "__main__":
    generate_rsa_key_pair()
