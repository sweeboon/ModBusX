"""Modbus checksum utilities for CRC-16 and LRC calculations."""


def calculate_crc16(data: bytes) -> int:
    """Calculate CRC-16/Modbus (polynomial 0xA001, reflected).

    Args:
        data: Raw bytes to compute CRC over (excluding CRC bytes).

    Returns:
        16-bit CRC value. Append as little-endian (low byte first).
    """
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc


def calculate_lrc(data: bytes) -> int:
    """Calculate Modbus ASCII LRC (two's complement of byte sum).

    Args:
        data: Raw bytes to compute LRC over (excluding LRC byte).

    Returns:
        8-bit LRC value.
    """
    return (-(sum(data) & 0xFF)) & 0xFF


def verify_crc16(frame: bytes) -> bool:
    """Verify CRC-16 of a complete RTU frame (including trailing CRC bytes).

    Args:
        frame: Complete RTU frame with 2-byte CRC appended (little-endian).

    Returns:
        True if CRC matches.
    """
    if len(frame) < 4:
        return False
    payload = frame[:-2]
    received_crc = frame[-2] | (frame[-1] << 8)
    return calculate_crc16(payload) == received_crc


def verify_lrc(payload: bytes, received_lrc: int) -> bool:
    """Verify LRC of a Modbus ASCII frame payload.

    Args:
        payload: Frame payload bytes (unit ID + function code + data).
        received_lrc: The LRC byte received in the frame.

    Returns:
        True if LRC matches.
    """
    return calculate_lrc(payload) == received_lrc


# Function code names for UI display
FUNCTION_CODE_NAMES = {
    0x01: "Read Coils",
    0x02: "Read Discrete Inputs",
    0x03: "Read Holding Registers",
    0x04: "Read Input Registers",
    0x05: "Write Single Coil",
    0x06: "Write Single Register",
    0x0F: "Write Multiple Coils",
    0x10: "Write Multiple Registers",
    0x17: "Read/Write Multiple Registers",
}


def get_function_code_name(fc: int) -> str:
    """Get human-readable name for a Modbus function code."""
    if fc & 0x80:
        base_fc = fc & 0x7F
        base_name = FUNCTION_CODE_NAMES.get(base_fc, f"FC {base_fc:#04x}")
        return f"Exception ({base_name})"
    return FUNCTION_CODE_NAMES.get(fc, f"FC {fc:#04x}")
