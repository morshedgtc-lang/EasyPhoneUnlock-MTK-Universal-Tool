"""
MediaTek OFP (Oppo/Realme/OnePlus) firmware decryptor.

Decrypts an encrypted .ofp container into its scatter + partition images so the
normal flashing pipeline can use it. Technicians load the stock .ofp the vendor
ships; this unpacks it locally on their PC.

Algorithm ported from the MIT-licensed bkerler/oppo_decrypt (ofp_mtk_decrypt.py,
(c) B. Kerler). Uses the project's existing `cryptography` dependency for AES-CFB
(CFB128), which matches the reference's segment_size=128.
"""
from __future__ import annotations

import hashlib
import os
import struct
from binascii import hexlify, unhexlify
from typing import List, Tuple

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

HEADER_LEN = 0x6C
ENTRY_LEN = 0x60
HEADER_FMT = "46s Q 4s 7s 5s H 32s H"   # native alignment (matches reference)
ENTRY_FMT = "<32s Q Q Q 32s Q"
HDR_OBFUSCATION_KEY = bytearray(b"geyixue")

# Key tables: triples of (obfuscated key, enc aes key, enc aes iv) in hex, plus a
# final direct (aeskey, aesiv) ASCII pair. From bkerler/oppo_decrypt (MIT).
_KEYTABLES = [
    ("67657963787565E837D226B69A495D21", "F6C50203515A2CE7D8C3E1F938B7E94C", "42F2D5399137E2B2813CD8ECDF2F4D72"),
    ("9E4F32639D21357D37D226B69A495D21", "A3D8D358E42F5A9E931DD3917D9A3218", "386935399137416B67416BECF22F519A"),
    ("892D57E92A4D8A975E3C216B7C9DE189", "D26DF2D9913785B145D18C7219B89F26", "516989E4A1BFC78B365C6BC57D944391"),
    ("27827963787265EF89D126B69A495A21", "82C50203285A2CE7D8C3E198383CE94C", "422DD5399181E223813CD8ECDF2E4D72"),
    ("3C4A618D9BF2E4279DC758CD535147C3", "87B13D29709AC1BF2382276C4E8DF232", "59B7A8E967265E9BCABE2469FE4A915E"),
    ("1C3288822BF824259DC852C1733127D3", "E7918D22799181CF2312176C9E2DF298", "3247F889A7B6DECBCA3E28693E4AAAFE"),
    ("1E4F32239D65A57D37D2266D9A775D43", "A332D3C3E42F5A3E931DD991729A321D", "3F2A35399A373377674155ECF28FD19A"),
    ("122D57E92A518AFF5E3C786B7C34E189", "DD6DF2D9543785674522717219989FB0", "12698965A132C76136CC88C5DD94EE91"),
    ("ab3f76d7989207f2", "2bf515b3a9737835"),  # direct AES key/iv (ASCII)
]


def _swap(ch: int) -> int:
    return ((ch & 0xF) << 4) + ((ch & 0xF0) >> 4)


def mtk_deobfuscate(key: bytearray, data: bytearray) -> bytearray:
    """Reverse the header obfuscation: out[i] = key ^ nibbleswap(in[i])."""
    kl = len(key)
    for i in range(len(data)):
        data[i] = key[i % kl] ^ (((data[i] & 0xF0) >> 4) | (16 * (data[i] & 0xF)))
    return data


def mtk_obfuscate(key: bytearray, data: bytearray) -> bytearray:
    """Inverse of mtk_deobfuscate: out[i] = nibbleswap(key ^ in[i]). (For tests.)"""
    kl = len(key)
    for i in range(len(data)):
        tmp = key[i % kl] ^ data[i]
        data[i] = ((tmp & 0xF0) >> 4) | (16 * (tmp & 0xF))
    return data


def _key_unshuffle(obskey: bytearray, enc: bytearray) -> bytes:
    """md5(nibbleswap(obskey ^ enc))[:16hex] — derives aes key/iv from a triple."""
    tmp = mtk_obfuscate(bytearray(obskey), bytearray(enc))
    return hexlify(hashlib.md5(tmp).digest())[:16]


def get_key(index: int) -> Tuple[bytes, bytes]:
    kt = _KEYTABLES[index]
    if len(kt) == 3:
        obskey = bytearray(unhexlify(kt[0]))
        aeskey = _key_unshuffle(obskey, bytearray(unhexlify(kt[1])))
        aesiv = _key_unshuffle(obskey, bytearray(unhexlify(kt[2])))
        return aeskey, aesiv
    return kt[0].encode("utf-8"), kt[1].encode("utf-8")


def aes_cfb_decrypt(key: bytes, iv: bytes, data: bytes) -> bytes:
    dec = Cipher(algorithms.AES(key), modes.CFB(iv)).decryptor()
    return dec.update(data) + dec.finalize()


def _brute_key(rf) -> Tuple[bytes, bytes]:
    """Find the table whose key decrypts the first block to a 'MMM' magic."""
    rf.seek(0)
    enc = rf.read(16)
    for i in range(len(_KEYTABLES)):
        key, iv = get_key(i)
        if aes_cfb_decrypt(key, iv, enc)[:3] == b"MMM":
            return key, iv
    raise ValueError("Unknown OFP key — this firmware is not a supported MTK OFP.")


def _cstr(b: bytes) -> str:
    return b.replace(b"\x00", b"").decode("utf-8", errors="ignore")


def decrypt_ofp(filename: str, outdir: str, log=lambda m: None) -> List[str]:
    """Decrypt an MTK .ofp into outdir. Returns the list of extracted filenames."""
    os.makedirs(outdir, exist_ok=True)
    filesize = os.stat(filename).st_size
    written: List[str] = []

    with open(filename, "rb") as rf:
        aeskey, aesiv = _brute_key(rf)

        rf.seek(filesize - HEADER_LEN)
        hdr = mtk_deobfuscate(HDR_OBFUSCATION_KEY, bytearray(rf.read(HEADER_LEN)))
        (prjname, _unk, _res, cpu, flashtype, entries, prjinfo, _crc) = struct.unpack(HEADER_FMT, bytes(hdr))
        prjname, cpu, flashtype, prjinfo = map(_cstr, (prjname, cpu, flashtype, prjinfo))
        if prjname:
            log(f"Project: {prjname}  CPU: {cpu}  Flash: {flashtype}")
        if prjinfo:
            log(f"Info: {prjinfo}")

        hdr2len = entries * ENTRY_LEN
        rf.seek(filesize - hdr2len - HEADER_LEN)
        hdr2 = mtk_deobfuscate(HDR_OBFUSCATION_KEY, bytearray(rf.read(hdr2len)))

        for i in range(entries):
            name, start, length, enclength, fname, _crc = struct.unpack(
                ENTRY_FMT, bytes(hdr2[i * ENTRY_LEN:(i + 1) * ENTRY_LEN]))
            name, fname = _cstr(name), _cstr(fname)
            out_path = os.path.join(outdir, fname)
            log(f"Extracting {name} -> {fname}")
            with open(out_path, "wb") as wb:
                if enclength > 0:
                    rf.seek(start)
                    enc = rf.read(enclength)
                    if enclength % 16 != 0:
                        enc += b"\x00" * (16 - (enclength % 16))
                    wb.write(aes_cfb_decrypt(aeskey, aesiv, enc)[:enclength])
                    length -= enclength
                while length > 0:
                    size = min(0x200000, length)
                    wb.write(rf.read(size))
                    length -= size
            written.append(fname)

    log(f"Decrypted {len(written)} file(s) to {outdir}")
    return written
