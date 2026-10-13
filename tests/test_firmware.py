"""
Firmware loader tests.

Builds a SYNTHETIC MTK .ofp in memory (using the direct key table entry) and
verifies our decryptor extracts the original bytes — proving the port is correct
without needing a real (large, copyrighted) firmware file.
"""
import os
import struct

from src.core.firmware import loader, ofp_mtk


def _build_ofp(tmp, partitions):
    """
    partitions: list of (name, filename, plaintext_bytes)
    Uses key table index 8 (direct ASCII aes key/iv). Layout:
      [enc data region][obfuscated hdr2 entries][obfuscated 0x6C header]
    The first 16 bytes of the file must decrypt to a 'MMM' magic so brute_key
    finds the table.
    """
    key, iv = ofp_mtk.get_key(8)

    # Encrypt each partition's plaintext with AES-CFB (same key as decrypt).
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    def enc(data):
        padded = data + (b"\x00" * ((16 - len(data) % 16) % 16))
        e = Cipher(algorithms.AES(key), modes.CFB(iv)).encryptor()
        return e.update(padded) + e.finalize()

    # Ensure the very first partition's ciphertext begins at offset 0 and its
    # plaintext starts with 'MMM' so _brute_key succeeds.
    body = b""
    entries = []
    for name, fname, pt in partitions:
        start = len(body)
        ct = enc(pt)
        body += ct
        entries.append((name, start, len(pt), len(pt), fname))

    # Build hdr2 entries (plaintext) then obfuscate.
    hdr2 = b""
    for name, start, length, enclen, fname in entries:
        hdr2 += struct.pack(ofp_mtk.ENTRY_FMT,
                            name.encode().ljust(32, b"\x00"), start, length, enclen,
                            fname.encode().ljust(32, b"\x00"), 0)
    hdr2_obf = bytes(ofp_mtk.mtk_obfuscate(bytearray(ofp_mtk.HDR_OBFUSCATION_KEY), bytearray(hdr2)))

    # Build the 0x6C header (plaintext) then obfuscate.
    header = struct.pack(ofp_mtk.HEADER_FMT,
                         b"EPUTEST".ljust(46, b"\x00"), 0, b"\x00" * 4,
                         b"MT6765".ljust(7, b"\x00"), b"EMMC".ljust(5, b"\x00"),
                         len(entries), b"test".ljust(32, b"\x00"), 0)
    header_obf = bytes(ofp_mtk.mtk_obfuscate(bytearray(ofp_mtk.HDR_OBFUSCATION_KEY), bytearray(header)))

    ofp = body + hdr2_obf + header_obf
    path = os.path.join(tmp, "synthetic.ofp")
    with open(path, "wb") as f:
        f.write(ofp)
    return path


def test_ofp_mtk_roundtrip(tmp_path):
    tmp = str(tmp_path)
    # First partition plaintext MUST start with b"MMM" (the magic brute_key checks).
    boot = b"MMM" + b"BOOT-IMAGE-CONTENT-1234567890" * 4
    scatter_txt = (b"MMM\n"  # magic prefix so it's the first/decryptable entry
                   b"partition_name: boot\nfile_name: boot.img\nis_download: true\n"
                   b"linear_start_addr: 0x40000\nphysical_start_addr: 0x40000\n"
                   b"partition_size: 0x2000000\n")
    path = _build_ofp(tmp, [
        ("scatter", "MT6765_scatter.txt", scatter_txt),
        ("boot", "boot.img", boot),
    ])

    out = os.path.join(tmp, "out")
    written = ofp_mtk.decrypt_ofp(path, out)
    assert set(written) == {"MT6765_scatter.txt", "boot.img"}
    # Verify exact content was recovered.
    assert open(os.path.join(out, "boot.img"), "rb").read() == boot
    assert open(os.path.join(out, "MT6765_scatter.txt"), "rb").read() == scatter_txt


def test_loader_detect(tmp_path):
    assert loader.detect("firmware.ofp") == "ofp"
    assert loader.detect("rom.ozip") == "ozip"
    assert loader.detect("MT6765_Android_scatter.txt") == "scatter"
    assert loader.detect("whatever.xml") == "scatter"


def test_loader_load_ofp(tmp_path):
    tmp = str(tmp_path)
    scatter_txt = (b"MMM\n"
                   b"partition_name: boot\nfile_name: boot.img\nis_download: true\n"
                   b"linear_start_addr: 0x40000\nphysical_start_addr: 0x40000\n"
                   b"partition_size: 0x2000000\n")
    path = _build_ofp(tmp, [("scatter", "MT6765_scatter.txt", scatter_txt)])
    fw = loader.load(path, os.path.join(tmp, "ex"))
    assert fw.format == "ofp"
    assert fw.scatter_path and os.path.isfile(fw.scatter_path)
    assert any(p.name == "boot" for p in fw.partitions)
