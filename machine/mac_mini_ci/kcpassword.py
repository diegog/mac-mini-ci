"""Encode a password the way loginwindow expects it in /etc/kcpassword.

The bytes are XORed with a fixed, repeating 11-byte key and padded with NUL to a multiple of 12
bytes, so there is always at least one terminating NUL (loginwindow stops at the first one).
Padding to 11 bytes — as older scripts do — drops the terminator for 22- and 33-character
passwords. Reference: brunerd's setAutoLogin.sh (2022) and Apple-generated files.
"""

KEY = bytes([0x7D, 0x89, 0x52, 0x23, 0xD2, 0xBC, 0xDD, 0xEA, 0xA3, 0xB9, 0x1F])


def encode(password: str) -> bytes:
    data = bytearray(password.encode("utf-8"))
    data += b"\x00" * (12 - len(data) % 12)
    return bytes(byte ^ KEY[i % len(KEY)] for i, byte in enumerate(data))


def decode(blob: bytes) -> str:
    plain = bytes(byte ^ KEY[i % len(KEY)] for i, byte in enumerate(blob))
    return plain.split(b"\x00", 1)[0].decode("utf-8")


if __name__ == "__main__":
    # "admin" must start with the bytes Cirrus Labs' Tahoe template writes (1c ed 3f 4a bc bc).
    assert encode("admin")[:6].hex() == "1ced3f4abcbc"
    for pw in ("a", "admin", "elevenchars", "twentytwocharacters!!!", "x" * 36):
        blob = encode(pw)
        assert len(blob) % 12 == 0 and len(blob) > len(pw), pw
        assert decode(blob) == pw, pw
    print("ok")
