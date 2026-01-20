#!/usr/bin/env python3
"""
Generate a proper Fernet encryption key for ENCRYPTION_KEY environment variable.

Fernet requires a 32-byte URL-safe base64-encoded key. This script generates
a valid key that can be used in your .env file.

Usage:
    python tests/integration/generate_encryption_key.py
"""

from cryptography.fernet import Fernet


def main():
    """Generate and print a Fernet encryption key."""
    key = Fernet.generate_key()
    key_string = key.decode()

    print("=" * 60)
    print("Fernet Encryption Key Generator")
    print("=" * 60)
    print()
    print("Generated key (add to your .env file):")
    print(f"ENCRYPTION_KEY={key_string}")
    print()
    print("=" * 60)
    print("Note: Keep this key secure and never commit it to version control!")
    print("=" * 60)


if __name__ == "__main__":
    main()
