#include <stdlib.h>
#include <string.h>
#include <stdio.h>

int wheeler_decompress_c(const char* data, int data_len, unsigned char** out_buf) {
    int cap = data_len * 2 + 4096;
    unsigned char* out = (unsigned char*)malloc(cap);
    if (!out) return 0;
    int out_len = 0;

    int lookup[4096];
    memset(lookup, 0, sizeof(lookup));

    int idx = 0;
    int current_char = 0;

    #define GETCH() ({ \
        int res = 0; \
        while (idx < data_len) { \
            unsigned char c = (unsigned char)data[idx++]; \
            if (c != 10 && c >= 32 && c <= 126) { \
                current_char = c; \
                res = 1; \
                break; \
            } \
        } \
        res; \
    })

    #define INPUT_CHAR() ({ \
        int res = 0; \
        int escaped = 0; \
        while (1) { \
            if (!GETCH()) { res = 0; break; } \
            int c = current_char; \
            if (escaped) { \
                escaped = 0; \
                if (c >= '0' && c <= '9') { \
                    int d0 = c - '0'; \
                    if (!GETCH()) { res = 0; break; } \
                    int d1 = current_char - '0'; \
                    if (!GETCH()) { res = 0; break; } \
                    int d2 = current_char - '0'; \
                    int val = d0 * 100 + d1 * 10 + d2; \
                    char oct_str[16]; \
                    snprintf(oct_str, sizeof(oct_str), "%o", val); \
                    int code = (int)strtol(oct_str, NULL, 10); \
                    current_char = code & 0xFFFF; \
                    if (current_char == 13) current_char = 10; \
                    res = 1; break; \
                } else if (c == 'n') { \
                    current_char = 10; \
                    res = 1; break; \
                } else if (c == '+') { \
                    continue; \
                } else { \
                    current_char = c; \
                    res = 1; break; \
                } \
            } else { \
                if (c == '"') { res = 0; break; } \
                else if (c == '\\') { escaped = 1; continue; } \
                else { current_char = c; res = 1; break; } \
            } \
        } \
        res; \
    })

    int prev = 0;
    int bits_read = 6;
    int remaining_bits = 0;
    int buf_byte = 0;
    int ch = 0;
    int countdown = -1;

    while (countdown != 0) {
        if (bits_read == 6) {
            if (!INPUT_CHAR()) break;
            ch = current_char;
            if (ch >= 48 && ch < 58) {
                countdown = (ch - 48);
                continue;
            } else {
                bits_read = 0;
                ch -= 58;
            }
        }

        if (remaining_bits > 0) {
            buf_byte |= ((ch & 1) << (8 - remaining_bits));
            remaining_bits -= 1;
            if (remaining_bits == 0) {
                int b = buf_byte & 0xFF;
                if (out_len >= cap) {
                    cap = cap * 2 + 1024;
                    out = (unsigned char*)realloc(out, cap);
                }
                out[out_len++] = (unsigned char)b;
                lookup[prev] = b;
                prev = ((prev << 4) + b) & 4095;
            }
        } else {
            if ((ch & 1) > 0) {
                buf_byte = 0;
                remaining_bits = 8;
            } else {
                int b = lookup[prev];
                if (out_len >= cap) {
                    cap = cap * 2 + 1024;
                    out = (unsigned char*)realloc(out, cap);
                }
                out[out_len++] = (unsigned char)b;
                lookup[prev] = b;
                prev = ((prev << 4) + b) & 4095;
            }
        }

        ch >>= 1;
        bits_read += 1;
        countdown -= 1;
    }

    *out_buf = out;
    return out_len;
}

void free_wheeler_buf(unsigned char* p) {
    if (p) free(p);
}
