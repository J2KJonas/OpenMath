"""
Embedded Systems and Digital Hardware Math Engine.
Provides comprehensive utilities for:
- Bitwise manipulation, register bitmasks, and bitfield extractions
- Two's complement and integer ranges (8, 16, 32, 64-bit)
- Q-format fixed-point conversions (Q_m.n)
- IEEE-754 floating-point bit decomposition (single and double precision)
- Microcontroller Timers, Prescalers, PWM frequencies, and interrupt intervals
- UART Baud rate generation and clock divisor error calculations
- ADC and DAC conversions, quantization step sizes, and SNR
- Electronics: Voltage dividers, LED current limiting, RC time constants, and cutoffs
- CRC-8 / CRC-16 / CRC-32 and checksums
- SI frequency, time, resistance, and capacitance units
"""

import struct
import math
import sympy as sp
import numpy as np


class EmbeddedMath:
    """Namespace of embedded engineering and microcontroller helper functions."""

    # SI Constants
    KHZ = 1_000.0
    MHZ = 1_000_000.0
    GHZ = 1_000_000_000.0
    MS = 1e-3
    US = 1e-6
    NS = 1e-9
    KOHM = 1_000.0
    MOHM = 1_000_000.0
    UF = 1e-6
    NF = 1e-9
    PF = 1e-12
    MA = 1e-3
    UA = 1e-6

    # 1. Base Conversions & Bit Manipulation
    @staticmethod
    def to_bin(val, bits: int = 8):
        """Convert integer to fixed-width binary string formatted with nibble spaces."""
        try:
            val_i = int(val)
            bits_i = int(bits)
        except (TypeError, ValueError):
            return sp.Function('to_bin')(val, bits)
        v = val_i & ((1 << bits_i) - 1)
        raw_bin = bin(v)[2:].zfill(bits_i)
        nibbles = []
        for i in range(0, len(raw_bin), 4):
            nibbles.append(raw_bin[i:i+4])
        return f"0b{' '.join(nibbles)}"

    @staticmethod
    def to_hex(val, bits: int = 8):
        """Convert integer to fixed-width hexadecimal string."""
        try:
            val_i = int(val)
            bits_i = int(bits)
        except (TypeError, ValueError):
            return sp.Function('to_hex')(val, bits)
        v = val_i & ((1 << bits_i) - 1)
        hex_digits = math.ceil(bits_i / 4)
        return f"0x{int(v):0{hex_digits}X}"

    @staticmethod
    def twos_comp(val, bits: int = 8):
        """Calculate signed value from two's complement representation or vice versa."""
        try:
            v = int(val)
            bits_i = int(bits)
        except (TypeError, ValueError):
            return sp.Function('twos_comp')(val, bits)
        if v < 0:
            return (1 << bits_i) + v
        mask = 1 << (bits_i - 1)
        if v & mask:
            return v - (1 << bits_i)
        return v

    @staticmethod
    def twos_comp_repr(val, bits: int = 8):
        """Return comprehensive two's complement breakdown."""
        try:
            v = int(val)
            bits_i = int(bits)
        except (TypeError, ValueError):
            return sp.Function('twos_comp_repr')(val, bits)
        if v < 0:
            unsigned_val = (1 << bits_i) + v
        else:
            unsigned_val = v & ((1 << bits_i) - 1)

        signed_val = unsigned_val - (1 << bits_i) if (unsigned_val & (1 << (bits_i - 1))) else unsigned_val

        return {
            'decimal_signed': signed_val,
            'decimal_unsigned': unsigned_val,
            'hex': f"0x{int(unsigned_val):0{math.ceil(bits_i/4)}X}",
            'binary': bin(unsigned_val)[2:].zfill(bits_i),
            'bits': bits_i,
            'min_signed': -(1 << (bits_i - 1)),
            'max_signed': (1 << (bits_i - 1)) - 1,
            'max_unsigned': (1 << bits_i) - 1
        }

    two_comp = twos_comp
    two_comp_repr = twos_comp_repr

    @staticmethod
    def bit_get(val, bit):
        """Get state of a specific bit index (0 or 1)."""
        try:
            return (int(val) >> int(bit)) & 1
        except (TypeError, ValueError):
            return sp.Function('bit_get')(val, bit)

    @staticmethod
    def bit_set(val, bit):
        """Set a specific bit to 1."""
        try:
            return int(val) | (1 << int(bit))
        except (TypeError, ValueError):
            return sp.Function('bit_set')(val, bit)

    @staticmethod
    def bit_clear(val, bit):
        """Clear a specific bit to 0."""
        try:
            return int(val) & ~(1 << int(bit))
        except (TypeError, ValueError):
            return sp.Function('bit_clear')(val, bit)

    @staticmethod
    def bit_toggle(val, bit):
        """Toggle a specific bit."""
        try:
            return int(val) ^ (1 << int(bit))
        except (TypeError, ValueError):
            return sp.Function('bit_toggle')(val, bit)

    @staticmethod
    def bit_mask(start_bit, end_bit):
        """Create a contiguous bitmask from start_bit to end_bit inclusive."""
        try:
            s = min(int(start_bit), int(end_bit))
            e = max(int(start_bit), int(end_bit))
            return ((1 << (e - s + 1)) - 1) << s
        except (TypeError, ValueError):
            return sp.Function('bit_mask')(start_bit, end_bit)

    @staticmethod
    def bit_field(val, start_bit, end_bit):
        """Extract bitfield from start_bit to end_bit."""
        try:
            s = min(int(start_bit), int(end_bit))
            e = max(int(start_bit), int(end_bit))
            mask = (1 << (e - s + 1)) - 1
            return (int(val) >> s) & mask
        except (TypeError, ValueError):
            return sp.Function('bit_field')(val, start_bit, end_bit)

    # 2. Fixed-Point Math (Q-format: Q_m.n)
    @staticmethod
    def to_q(float_val: float, int_bits: int, frac_bits: int) -> dict:
        """Convert a floating point number to fixed-point Q[int_bits].[frac_bits] integer."""
        int_b = int(int_bits)
        frac_b = int(frac_bits)
        f_val = float(float_val)
        scaling = 1 << frac_b
        q_int = int(round(f_val * scaling))
        total_bits = int_b + frac_b + 1  # including sign
        mask = (1 << total_bits) - 1
        raw_u = int(q_int & mask)
        actual_float = float(q_int / scaling)
        hex_len = int(math.ceil(total_bits / 4))
        return {
            'q_format': f"Q{int_b}.{frac_b}",
            'raw_int': q_int,
            'raw_hex': f"0x{raw_u:0{hex_len}X}",
            'raw_bin': bin(raw_u)[2:].zfill(total_bits),
            'actual_float': actual_float,
            'quantization_error': f_val - actual_float,
            'resolution': 1.0 / scaling,
            'range': [-(1 << int_b), (1 << int_b) - (1.0 / scaling)]
        }

    @staticmethod
    def from_q(raw_int: int, frac_bits: int) -> float:
        """Convert a Q-format fixed-point integer back to float."""
        return float(raw_int) / (1 << frac_bits)

    # 3. IEEE-754 Floating Point Breakdown
    @staticmethod
    def ieee754(float_val: float, double_precision: bool = False) -> dict:
        """Deconstruct float into IEEE-754 sign, biased exponent, and mantissa/fraction."""
        f = float(float_val)
        if double_precision:
            packed = struct.pack('>d', f)
            (int_val,) = struct.unpack('>Q', packed)
            sign = (int_val >> 63) & 1
            exponent_raw = (int_val >> 52) & 0x7FF
            mantissa_raw = int_val & 0xFFFFFFFFFFFFF
            exp_bias = 1023
            exp_actual = exponent_raw - exp_bias if exponent_raw != 0 else -1022
            return {
                'format': 'IEEE-754 Double Precision (64-bit)',
                'hex': f"0x{int_val:016X}",
                'sign': sign,
                'exponent_raw': f"0x{exponent_raw:03X} ({exponent_raw})",
                'exponent_actual': exp_actual,
                'mantissa_hex': f"0x{mantissa_raw:013X}",
                'binary': f"{sign:01b} {exponent_raw:011b} {mantissa_raw:052b}"
            }
        else:
            packed = struct.pack('>f', f)
            (int_val,) = struct.unpack('>I', packed)
            sign = (int_val >> 31) & 1
            exponent_raw = (int_val >> 23) & 0xFF
            mantissa_raw = int_val & 0x7FFFFF
            exp_bias = 127
            exp_actual = exponent_raw - exp_bias if exponent_raw != 0 else -126
            return {
                'format': 'IEEE-754 Single Precision (32-bit)',
                'hex': f"0x{int_val:08X}",
                'sign': sign,
                'exponent_raw': f"0x{exponent_raw:02X} ({exponent_raw})",
                'exponent_actual': exp_actual,
                'mantissa_hex': f"0x{mantissa_raw:06X}",
                'binary': f"{sign:01b} {exponent_raw:08b} {mantissa_raw:023b}"
            }

    # 4. UART Baud Rate & Clock Divisors
    @staticmethod
    def ubrr_calc(f_clk: float, desired_baud: float, mode_divisor: int = 16) -> dict:
        """
        Calculate UART Baud Rate Register (UBRR/BRR) value, actual baud rate, and percentage error.
        Formula: Baud = f_clk / (mode_divisor * (UBRR + 1))
        """
        ubrr_exact = (float(f_clk) / (mode_divisor * float(desired_baud))) - 1
        ubrr_int = max(0, round(ubrr_exact))
        actual_baud = float(f_clk) / (mode_divisor * (ubrr_int + 1))
        error_pct = ((actual_baud - desired_baud) / desired_baud) * 100.0
        return {
            'desired_baud': desired_baud,
            'f_clk_hz': f_clk,
            'ubrr_register': ubrr_int,
            'ubrr_hex': f"0x{ubrr_int:04X}",
            'actual_baud': round(actual_baud, 2),
            'error_percent': round(error_pct, 4),
            'acceptable_uart_error': abs(error_pct) <= 2.0  # standard < 2% tolerance
        }

    @staticmethod
    def baud_rate(f_clk: float, ubrr: int, mode_divisor: int = 16) -> float:
        """Calculate resulting baud rate from clock and register setting."""
        return float(f_clk) / (mode_divisor * (int(ubrr) + 1))

    # 5. Timers, Prescalers, PWM, and Interrupts
    @staticmethod
    def timer_calc(f_clk: float, prescaler: int, arr_period: int) -> dict:
        """
        Calculate Timer Frequency, Tick Time, and Overflow / Interrupt Interval.
        Formula: f_timer = f_clk / (prescaler * (arr + 1))
        """
        psc = max(1, int(prescaler))
        arr = int(arr_period)
        f_timer = float(f_clk) / (psc * (arr + 1))
        tick_time = psc / float(f_clk)
        period_time = 1.0 / f_timer if f_timer > 0 else float('inf')
        return {
            'f_clk_hz': f_clk,
            'prescaler': psc,
            'arr_period_reg': arr,
            'timer_frequency_hz': f_timer,
            'timer_period_sec': period_time,
            'tick_time_sec': tick_time,
            'tick_time_us': tick_time * 1e6,
            'overflow_time_ms': period_time * 1e3
        }

    @staticmethod
    def timer_arr(f_clk: float, prescaler: int, target_frequency_hz: float) -> dict:
        """Calculate required ARR register value for a desired timer/PWM frequency."""
        psc = max(1, int(prescaler))
        arr_exact = (float(f_clk) / (psc * float(target_frequency_hz))) - 1
        arr_int = max(0, round(arr_exact))
        actual_f = float(f_clk) / (psc * (arr_int + 1))
        error_pct = ((actual_f - target_frequency_hz) / target_frequency_hz) * 100.0
        return {
            'target_frequency_hz': target_frequency_hz,
            'prescaler': psc,
            'arr_exact': arr_exact,
            'arr_integer': arr_int,
            'arr_hex': f"0x{arr_int:04X}",
            'actual_frequency_hz': actual_f,
            'error_percent': round(error_pct, 4)
        }

    @staticmethod
    def pwm_duty(arr: int, ccr_compare: int) -> dict:
        """Calculate PWM duty cycle percentage from compare register and period register."""
        duty_pct = (float(ccr_compare) / float(arr)) * 100.0 if arr > 0 else 0.0
        return {
            'arr_period': arr,
            'ccr_compare': ccr_compare,
            'duty_cycle_pct': round(duty_pct, 4),
            'duty_fraction': float(ccr_compare) / float(arr) if arr > 0 else 0.0
        }

    # 6. ADC & DAC Conversions
    @staticmethod
    def adc_raw(v_in: float, v_ref: float, bits: int = 10) -> int:
        """Convert analog voltage to digital ADC raw integer value."""
        max_count = (1 << bits) - 1
        ratio = max(0.0, min(1.0, float(v_in) / float(v_ref)))
        return round(ratio * max_count)

    @staticmethod
    def adc_volt(raw: int, v_ref: float, bits: int = 10) -> float:
        """Convert digital ADC raw integer back to analog voltage."""
        max_count = (1 << bits) - 1
        return (float(raw) / max_count) * float(v_ref)

    @staticmethod
    def adc_resolution(v_ref: float, bits: int = 10) -> dict:
        """Calculate ADC quantization step size (LSB voltage) and theoretical SNR."""
        steps = 1 << bits
        lsb_v = float(v_ref) / steps
        snr_db = 6.02 * bits + 1.76
        return {
            'bits': bits,
            'total_steps': steps,
            'v_ref': v_ref,
            'lsb_voltage_mv': lsb_v * 1000.0,
            'lsb_voltage_uv': lsb_v * 1e6,
            'theoretical_snr_db': round(snr_db, 2)
        }

    # 7. Hardware & Electronics Calculations
    @staticmethod
    def voltage_divider(v_in: float, r1: float, r2: float) -> float:
        """Calculate voltage divider output: Vout = Vin * (R2 / (R1 + R2))."""
        return float(v_in) * (float(r2) / (float(r1) + float(r2)))

    @staticmethod
    def voltage_divider_r1(v_in: float, v_out: float, r2: float) -> float:
        """Find required R1 given Vin, desired Vout, and chosen R2."""
        return float(r2) * ((float(v_in) / float(v_out)) - 1.0)

    @staticmethod
    def led_resistor(v_cc: float, v_led: float, i_led_ma: float) -> dict:
        """Calculate current limiting resistor for an LED."""
        v_drop = float(v_cc) - float(v_led)
        i_amp = float(i_led_ma) * 1e-3
        r_exact = v_drop / i_amp if i_amp > 0 else float('inf')
        power_mw = (i_amp ** 2) * r_exact * 1000.0
        return {
            'r_ohms': round(r_exact, 2),
            'r_kohms': round(r_exact / 1000.0, 4),
            'resistor_power_mw': round(power_mw, 2),
            'v_cc': v_cc,
            'v_led': v_led,
            'i_led_ma': i_led_ma
        }

    @staticmethod
    def rc_cutoff(r_ohms: float, c_farads: float) -> dict:
        """Calculate low-pass RC filter cutoff frequency fc = 1 / (2*pi*R*C) and time constant tau = R*C."""
        tau = float(r_ohms) * float(c_farads)
        fc = 1.0 / (2.0 * math.pi * tau) if tau > 0 else float('inf')
        return {
            'cutoff_frequency_hz': fc,
            'time_constant_tau_sec': tau,
            'time_constant_tau_ms': tau * 1e3,
            'time_constant_tau_us': tau * 1e6,
            'settle_time_99pct_ms': 5.0 * tau * 1e3  # 5*tau to reach ~99.3%
        }

    # 8. CRC Algorithms for Embedded Data Frames
    @staticmethod
    def crc8(data, poly: int = 0x07, init: int = 0x00) -> dict:
        """Compute CRC-8 checksum over bytes or string data."""
        if isinstance(data, str):
            b_data = data.encode('utf-8')
        elif isinstance(data, (list, tuple)):
            b_data = bytes(data)
        else:
            b_data = bytes(data)

        crc = init
        for byte in b_data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = ((crc << 1) ^ poly) & 0xFF
                else:
                    crc = (crc << 1) & 0xFF

        return {
            'crc8_int': crc,
            'crc8_hex': f"0x{crc:02X}",
            'crc8_bin': bin(crc)[2:].zfill(8),
            'length_bytes': len(b_data)
        }

    @staticmethod
    def crc16(data, poly: int = 0x1021, init: int = 0xFFFF) -> dict:
        """Compute CRC-16-CCITT checksum."""
        if isinstance(data, str):
            b_data = data.encode('utf-8')
        elif isinstance(data, (list, tuple)):
            b_data = bytes(data)
        else:
            b_data = bytes(data)

        crc = init
        for byte in b_data:
            crc ^= (byte << 8)
            for _ in range(8):
                if crc & 0x8000:
                    crc = ((crc << 1) ^ poly) & 0xFFFF
                else:
                    crc = (crc << 1) & 0xFFFF

        return {
            'crc16_int': crc,
            'crc16_hex': f"0x{crc:04X}",
            'crc16_bin': bin(crc)[2:].zfill(16),
            'length_bytes': len(b_data)
        }
