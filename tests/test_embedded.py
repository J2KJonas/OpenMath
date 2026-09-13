"""
Unit tests for Embedded Systems math, bit manipulation, timers, ADC, baud rate, and electronics.
"""

import unittest
from cas_engine import CASEngine, EmbeddedMath


class TestEmbeddedSystems(unittest.TestCase):
    def setUp(self):
        self.engine = CASEngine()

    def test_bitwise_and_base_conversions(self):
        self.assertEqual(EmbeddedMath.to_bin(0x5A, bits=8), "0b0101 1010")
        self.assertEqual(EmbeddedMath.to_hex(255, bits=8), "0xFF")

        # Two's complement of -5 in 8-bit
        repr_info = EmbeddedMath.twos_comp_repr(-5, bits=8)
        self.assertEqual(repr_info['decimal_signed'], -5)
        self.assertEqual(repr_info['decimal_unsigned'], 251)
        self.assertEqual(repr_info['hex'], "0xFB")

        # Bit manipulation
        val = 0b0000_0000
        val = EmbeddedMath.bit_set(val, 3)
        self.assertEqual(val, 8)
        self.assertEqual(EmbeddedMath.bit_get(val, 3), 1)
        self.assertEqual(EmbeddedMath.bit_get(val, 2), 0)
        val = EmbeddedMath.bit_clear(val, 3)
        self.assertEqual(val, 0)

        # Bitfield extraction
        reg = 0b1011_0110
        self.assertEqual(EmbeddedMath.bit_field(reg, 4, 7), 0b1011)

    def test_fixed_point_q_format(self):
        # Pi in Q7.8
        q = EmbeddedMath.to_q(3.14159, 7, 8)
        self.assertEqual(q['q_format'], "Q7.8")
        # 3.14159 * 256 = 804
        self.assertEqual(q['raw_int'], 804)
        recovered = EmbeddedMath.from_q(804, 8)
        self.assertAlmostEqual(recovered, 3.140625, places=5)

    def test_ieee754_floating_point(self):
        # 12.375 in single precision
        res = EmbeddedMath.ieee754(12.375, double_precision=False)
        self.assertEqual(res['sign'], 0)
        self.assertEqual(res['exponent_actual'], 3)
        self.assertEqual(res['hex'], "0x41460000")

    def test_microcontroller_timers_and_pwm(self):
        # Timer at 16 MHz with prescaler 64, ARR 249 -> 16e6 / (64 * 250) = 1000 Hz (1 kHz)
        t = EmbeddedMath.timer_calc(16e6, 64, 249)
        self.assertEqual(t['timer_frequency_hz'], 1000.0)
        self.assertEqual(t['overflow_time_ms'], 1.0)

        # ARR calculation for 1 kHz PWM on 84 MHz clock with prescaler 84
        arr_info = EmbeddedMath.timer_arr(84e6, 84, 1000)
        self.assertEqual(arr_info['arr_integer'], 999)

        # PWM duty cycle 50%
        duty = EmbeddedMath.pwm_duty(1000, 500)
        self.assertEqual(duty['duty_cycle_pct'], 50.0)

    def test_uart_baud_rate(self):
        # 16 MHz system clock, target baud 9600
        # UBRR = (16e6 / (16 * 9600)) - 1 = 103.166 -> 103
        ubrr = EmbeddedMath.ubrr_calc(16e6, 9600, mode_divisor=16)
        self.assertEqual(ubrr['ubrr_register'], 103)
        self.assertAlmostEqual(ubrr['actual_baud'], 9615.38, places=2)
        self.assertLess(abs(ubrr['error_percent']), 0.2)

    def test_adc_conversions(self):
        # 10-bit ADC, Vref = 3.3V, Vin = 1.65V -> raw = 512
        raw = EmbeddedMath.adc_raw(1.65, 3.3, bits=10)
        self.assertEqual(raw, 512)
        volt = EmbeddedMath.adc_volt(512, 3.3, bits=10)
        self.assertAlmostEqual(volt, 1.65, places=2)

        # Resolution for 12-bit ADC at 3.3V
        res = EmbeddedMath.adc_resolution(3.3, bits=12)
        self.assertAlmostEqual(res['lsb_voltage_mv'], 3.3 / 4096 * 1000, places=3)
        self.assertAlmostEqual(res['theoretical_snr_db'], 6.02 * 12 + 1.76, places=2)

    def test_circuits_and_rc_filter(self):
        # Voltage divider: 5V with R1 = 10k, R2 = 10k -> 2.5V
        v_out = EmbeddedMath.voltage_divider(5.0, 10000, 10000)
        self.assertEqual(v_out, 2.5)

        # LED Resistor: Vcc=5V, Vled=2V, Iled=20mA -> R = 3V / 0.02A = 150 Ohms
        led = EmbeddedMath.led_resistor(5.0, 2.0, 20.0)
        self.assertEqual(led['r_ohms'], 150.0)

        # RC Filter: R = 1k, C = 1uF -> tau = 1ms, fc = 1/(2*pi*0.001) ~ 159.15 Hz
        rc = EmbeddedMath.rc_cutoff(1000.0, 1e-6)
        self.assertEqual(rc['time_constant_tau_ms'], 1.0)
        self.assertAlmostEqual(rc['cutoff_frequency_hz'], 159.155, places=2)

    def test_crc_checksum(self):
        # CRC-8 over "123456789"
        crc = EmbeddedMath.crc8("123456789")
        self.assertIn("crc8_hex", crc)
        self.assertEqual(crc['length_bytes'], 9)

    def test_cas_engine_evaluation_with_embedded_units(self):
        # Evaluating with embedded SI units in CAS engine
        res = self.engine.evaluate("ubrr_calc(16 * MHz, 9600)")
        self.assertIn("103", str(res.exact_text))

        res2 = self.engine.evaluate("rc_cutoff(10 * kOhm, 100 * nF)")
        self.assertIn("cutoff", str(res2.exact_text).lower())

        res3 = self.engine.evaluate("to_bin(0x2A, 8)")
        self.assertEqual(res3.raw_result, "0b0010 1010")

    def test_no_deprecation_warning_on_preview_and_parse(self):
        """Test that parsing and previewing embedded functions like two_comp_repr(-5, 8)
        do not trigger SymPyDeprecationWarning in radsimp.py."""
        import warnings
        from sympy.utilities.exceptions import SymPyDeprecationWarning
        from ui.math_renderer import expr_to_preview_latex
        from cas_engine.parser import MathParser

        with warnings.catch_warnings():
            warnings.simplefilter("error", category=SymPyDeprecationWarning)
            # Preview rendering
            ltx = expr_to_preview_latex("two_comp_repr(-5, 8)")
            self.assertIn("two", ltx)
            self.assertNotIn("Mul", ltx)

            ltx2 = expr_to_preview_latex("twos_comp_repr(-5, 8)")
            self.assertIn("twos", ltx2)

            # Direct MathParser.parse without engine context
            res = MathParser.parse("two_comp_repr(-5, 8)")
            self.assertFalse(res.sympy_expr.is_Mul)

    def test_symbolic_and_concrete_bit_operations(self):
        """Test that bit manipulation functions handle both symbols (e.g. reg) and concrete values without TypeError."""
        engine = CASEngine()
        # Concrete evaluations
        self.assertEqual(engine.evaluate("bit_set(0x00, 3)").exact_text, "8")
        self.assertEqual(engine.evaluate("bit_clear(0xFF, 3)").exact_text, "247")
        self.assertEqual(engine.evaluate("bit_toggle(0x00, 3)").exact_text, "8")
        self.assertEqual(engine.evaluate("bit_field(0xABCD, 4, 7)").exact_text, "12")

        # Symbolic evaluations with undefined symbol 'reg'
        res_sym = engine.evaluate("bit_set(reg, 3)")
        self.assertTrue("bit_set" in res_sym.exact_text or "bitₛₑₜ" in res_sym.exact_text or "bit_set" in res_sym.python_code)
        self.assertIn("reg", res_sym.exact_text)

        res_clear = engine.evaluate("bit_clear(reg, 3)")
        self.assertTrue("bit_clear" in res_clear.exact_text or "bit_clear" in res_clear.python_code or "bit" in res_clear.exact_text)

        # After defining reg := 0x00, evaluate with variable
        engine.evaluate("reg := 0x00")
        res_defined = engine.evaluate("bit_set(reg, 3)")
        self.assertEqual(res_defined.exact_text, "8")

    def test_voltage_and_engineering_units(self):
        """Test voltage units (V, mV, uV, kV) and spaced units (e.g. 2.5 kOhm, 100 mV)."""
        engine = CASEngine()
        self.assertAlmostEqual(float(engine.evaluate("5 V").raw_result), 5.0)
        self.assertAlmostEqual(float(engine.evaluate("100 mV").raw_result), 0.1)
        self.assertAlmostEqual(float(engine.evaluate("50 uV").raw_result), 5e-5)
        self.assertAlmostEqual(float(engine.evaluate("1.2 kV").raw_result), 1200.0)

        # Resistance and frequency with spaces
        self.assertAlmostEqual(float(engine.evaluate("2.5 kOhm").raw_result), 2500.0)
        self.assertAlmostEqual(float(engine.evaluate("2,5 kOhm").raw_result), 2500.0)
        self.assertAlmostEqual(float(engine.evaluate("16 MHz").raw_result), 16e6)

        # Functions with spaced units
        div_res = engine.evaluate("voltage_divider(5 V, 10 kOhm, 10 kOhm)")
        self.assertAlmostEqual(float(div_res.raw_result), 2.5)

        rc_res = engine.evaluate("rc_cutoff(10 kOhm, 100 nF)")
        self.assertIn("cutoff_frequency_hz", rc_res.raw_result)

    def test_unit_conversions_and_inference(self):
        """Test unit inference from expressions and unit conversion tables."""
        from cas_engine.units import infer_unit_from_expression, get_unit_conversions, convert_value

        # Infer units
        self.assertEqual(infer_unit_from_expression("voltage_divider(5.0 V, 10 kOhm, 10 kOhm)"), "V")
        self.assertEqual(infer_unit_from_expression("voltagedivider(5.0 V, 10 kOhm, 10 kOhm)"), "V")
        self.assertEqual(infer_unit_from_expression("adc_volt(512, 3.3, 10)"), "V")
        self.assertEqual(infer_unit_from_expression("voltage_divider_r1(5 V, 2.5 V, 10 kOhm)"), "kOhm")

        # Conversions
        self.assertAlmostEqual(convert_value(2.5, "V", "mV"), 2500.0)
        self.assertAlmostEqual(convert_value(2.5, "V", "kV"), 0.0025)
        self.assertAlmostEqual(convert_value(10, "kOhm", "Ohm"), 10000.0)
        self.assertAlmostEqual(convert_value(100, "nF", "uF"), 0.1)

        # Options generation
        convs = get_unit_conversions(2.5, "V", decimal_separator=",")
        labels = [c['label'] for c in convs]
        self.assertIn("mV", labels)
        self.assertIn("kV", labels)
        self.assertIn("V", labels)
        mv_opt = next(c for c in convs if c['label'] == "mV")
        self.assertEqual(mv_opt['value'], 2500.0)
        self.assertEqual(mv_opt['code_unit'], "mV")

    def test_mega_units(self):
        """Test Mega SI units across resistance, voltage, frequency, power, and current."""
        from cas_engine.units import infer_unit_from_expression, get_unit_conversions, convert_value
        engine = CASEngine()

        # Resistance: MΩ, MOhm, MegaOhm, megohm
        self.assertAlmostEqual(float(engine.evaluate("4.7 MOhm").raw_result), 4.7e6)
        self.assertAlmostEqual(float(engine.evaluate("2,2 MΩ").raw_result), 2.2e6)
        self.assertAlmostEqual(float(engine.evaluate("1 MegaOhm").raw_result), 1e6)
        self.assertAlmostEqual(float(engine.evaluate("10 mega ohm").raw_result), 10e6)
        self.assertAlmostEqual(float(engine.evaluate("1 GOhm").raw_result), 1e9)

        # Voltage: MV, MegaVolt
        self.assertAlmostEqual(float(engine.evaluate("1.5 MV").raw_result), 1.5e6)
        self.assertAlmostEqual(float(engine.evaluate("2 MegaVolt").raw_result), 2e6)
        self.assertAlmostEqual(float(engine.evaluate("0.5 mega volt").raw_result), 5e5)

        # Frequency: MHz, MegaHz
        self.assertAlmostEqual(float(engine.evaluate("16 MHz").raw_result), 16e6)
        self.assertAlmostEqual(float(engine.evaluate("8 MegaHz").raw_result), 8e6)

        # Power: MW, kW, W, mW, uW
        self.assertAlmostEqual(float(engine.evaluate("3 MW").raw_result), 3e6)
        self.assertAlmostEqual(float(engine.evaluate("2.5 MegaWatt").raw_result), 2.5e6)
        self.assertAlmostEqual(float(engine.evaluate("500 kW").raw_result), 500e3)
        self.assertAlmostEqual(float(engine.evaluate("10 W").raw_result), 10.0)
        self.assertAlmostEqual(float(engine.evaluate("20 mW").raw_result), 0.02)

        # Current: MA, kA, A, mA
        self.assertAlmostEqual(float(engine.evaluate("2 MA").raw_result), 2e6)
        self.assertAlmostEqual(float(engine.evaluate("1.5 MegaAmp").raw_result), 1.5e6)
        self.assertAlmostEqual(float(engine.evaluate("10 kA").raw_result), 10000.0)

        # Unit Conversions for Mega units
        self.assertAlmostEqual(convert_value(1.0, "MV", "V"), 1e6)
        self.assertAlmostEqual(convert_value(500000.0, "V", "MV"), 0.5)
        self.assertAlmostEqual(convert_value(2.2, "MOhm", "kOhm"), 2200.0)
        self.assertAlmostEqual(convert_value(1.0, "GOhm", "MOhm"), 1000.0)
        self.assertAlmostEqual(convert_value(1000.0, "kW", "MW"), 1.0)
        self.assertAlmostEqual(convert_value(1.0, "MA", "kA"), 1000.0)

        # Conversion options list contains Mega options
        v_convs = get_unit_conversions(1.0, "MV")
        v_labels = [c['label'] for c in v_convs]
        self.assertIn("MV", v_labels)
        self.assertIn("kV", v_labels)
        self.assertIn("V", v_labels)
        self.assertIn("mV", v_labels)

        r_convs = get_unit_conversions(1.0, "MOhm")
        r_labels = [c['label'] for c in r_convs]
        self.assertIn("MΩ", r_labels)
        self.assertIn("kΩ", r_labels)
        self.assertIn("Ω", r_labels)
        self.assertIn("GΩ", r_labels)

        p_convs = get_unit_conversions(1.0, "MW")
        p_labels = [c['label'] for c in p_convs]
        self.assertIn("MW", p_labels)
        self.assertIn("kW", p_labels)
        self.assertIn("W", p_labels)

        # Unit inference with Mega units
        self.assertEqual(infer_unit_from_expression("voltage_divider(1.2 MV, 10 kOhm, 10 kOhm)"), "MV")
        self.assertEqual(infer_unit_from_expression("voltage_divider_r1(5 V, 2.5 V, 1 MOhm)"), "MOhm")


if __name__ == '__main__':
    unittest.main()
