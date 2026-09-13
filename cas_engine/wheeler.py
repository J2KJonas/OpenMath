"""
Worksheet Wheeler Compression and Base64 Decoder.
Implements the decompression algorithm used by .mw documents to store embedded images
(<Image> tags) and serialized mprintslash data streams.
"""

from typing import Optional


def worksheet_base64_decode(s: str) -> str:
    """
    Decodes standard Base64 string into 8-bit character stream
    matching the worksheet Base64Encoder decode behavior.
    """
    b64_table = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
    ch_decode = {c: i for i, c in enumerate(b64_table)}
    s = "".join(c for c in s if c in ch_decode or c == '=')
    
    out = []
    i = 0
    n = len(s)
    while i < n:
        c0 = s[i]
        c1 = s[i+1] if i+1 < n else '='
        c2 = s[i+2] if i+2 < n else '='
        c3 = s[i+3] if i+3 < n else '='
        i += 4
        
        v0 = ch_decode.get(c0, 0)
        v1 = ch_decode.get(c1, 0)
        v2 = ch_decode.get(c2, 0)
        v3 = ch_decode.get(c3, 0)
        
        b0 = (v0 << 2) | (v1 >> 4)
        out.append(chr(b0 & 0xFF))
        
        if c2 != '=':
            b1 = ((v1 & 0x0F) << 4) | (v2 >> 2)
            out.append(chr(b1 & 0xFF))
            if c3 != '=':
                b2 = ((v2 & 0x03) << 6) | v3
                out.append(chr(b2 & 0xFF))
    return "".join(out)


def worksheet_base64_encode(data_str: str) -> str:
    """Encodes character stream into standard Base64 string."""
    import base64
    raw_bytes = data_str.encode('latin1')
    return base64.b64encode(raw_bytes).decode('ascii')


class WheelerInStream:
    """Streams characters handling escape sequences for Wheeler decompression."""
    def __init__(self, data: str):
        self.data = data
        self.index = 0
        self.current_char = 0

    def getch(self) -> bool:
        while self.index < len(self.data):
            c = ord(self.data[self.index])
            self.index += 1
            self.current_char = c
            if c != 10 and 32 <= c <= 126:
                return True
        return False

    def input_char(self) -> bool:
        escaped = False
        while True:
            if not self.getch():
                return False
            c = self.current_char
            if escaped:
                escaped = False
                if chr(c).isdigit():
                    digits = [chr(c)]
                    if not self.getch():
                        return False
                    digits.append(chr(self.current_char))
                    if not self.getch():
                        return False
                    digits.append(chr(self.current_char))
                    val = int("".join(digits))
                    oct_str = oct(val)[2:]
                    code = int(oct_str)
                    self.current_char = code & 0xFFFF
                    if self.current_char == 13:
                        self.current_char = 10
                    return True
                elif c == ord('n'):
                    self.current_char = 10
                    return True
                elif c == ord('+'):
                    continue
                else:
                    self.current_char = c
                    return True
            else:
                if c == ord('"'):
                    return False
                elif c == ord('\\'):
                    escaped = True
                    continue
                else:
                    self.current_char = c
                    return True


def sling_hash(b: int, prev: int) -> int:
    return ((prev << 4) + b) & 4095


def wheeler_decompress(data_str: str) -> bytes:
    """
    Decompresses character stream using the Wheeler algorithm.
    Produces the raw binary payload (typically PNG/JPEG image).
    """
    instream = WheelerInStream(data_str)
    lookup = [0] * 4096
    prev = 0
    bits_read = 6
    remaining_bits = 0
    buf_byte = 0

    out = bytearray()
    
    # Pre-fill lookup table with identities 0..255
    for i in range(256):
        lookup[i] = i
    
    idx = 256
    while instream.getch():
        ch = instream.current_char
        if ch > 255:
            break
        
        # Read variable-length encoded codes
        code = 0
        countdown = bits_read
        while countdown > 0:
            if remaining_bits == 0:
                if not instream.getch():
                    break
                buf_byte = instream.current_char
                remaining_bits = 8
            
            code |= (buf_byte & 1) << (bits_read - countdown)
            buf_byte >>= 1
            remaining_bits -= 1
            countdown -= 1
        
        if code > idx:
            break
        elif code == idx:
            # Code equals current table index: reconstruct
            entry = [prev & 0xFF]
            p = prev
            while p > 255:
                entry.append(lookup[p] & 0xFF)
                p >>= 12
            entry.reverse()
            entry.append(entry[0])
            out.extend(entry)
            lookup[idx] = (prev << 12) | entry[0]
            prev = code
        else:
            # Code is in lookup table
            entry = []
            p = code
            while p > 255:
                entry.append(lookup[p] & 0xFF)
                p >>= 12
            entry.append(lookup[p] & 0xFF)
            entry.reverse()
            out.extend(entry)
            if prev != 0:
                lookup[idx] = (prev << 12) | entry[0]
            prev = code
        
        idx += 1
        if idx >= 4095:
            # Reset table
            idx = 256
            bits_read = 6
            for i in range(256):
                lookup[i] = i
        elif idx >= (1 << bits_read):
            bits_read += 1

    return bytes(out)


def decode_worksheet_image(raw_content: str) -> bytes:
    """
    Decode raw <Image> text content from a .mw file into raw image bytes (PNG/JPEG).
    Handles both Wheeler-compressed streams and direct base64 PNG data.
    """
    cleaned = raw_content.strip().replace('\n', '').replace('\r', '').replace(' ', '')
    if not cleaned:
        return b""
    
    # Check if direct base64 PNG
    if cleaned.startswith("iVBORw0KGgo"):
        import base64
        try:
            return base64.b64decode(cleaned)
        except Exception:
            pass

    try:
        decoded_chars = worksheet_base64_decode(cleaned)
        image_bytes = wheeler_decompress(decoded_chars)
        if image_bytes.startswith(b'\x89PNG') or image_bytes.startswith(b'\xff\xd8'):
            return image_bytes
    except Exception:
        pass

    # Direct base64 fallback
    try:
        import base64
        return base64.b64decode(cleaned)
    except Exception:
        return b""
