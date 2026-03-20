"""Frame Inspector Widget for CRC/LRC visualization and Modbus frame analysis."""

from collections import deque
from datetime import datetime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QGridLayout, QSplitter
)
from PyQt5.QtCore import Qt, pyqtSlot, QTimer
from PyQt5.QtGui import QColor, QFont
from modbusx.utils.checksum import (
    calculate_crc16, calculate_lrc, verify_crc16, verify_lrc,
    get_function_code_name
)


class FrameInspectorWidget(QWidget):
    """Displays decoded Modbus frames with CRC/LRC validation."""

    MAX_HISTORY = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._frame_history = deque(maxlen=self.MAX_HISTORY)
        self._pending_frames = []
        self._rx_count = 0
        self._tx_count = 0

        # Throttle timer for batch UI updates under high traffic
        self._update_timer = QTimer(self)
        self._update_timer.setInterval(100)
        self._update_timer.timeout.connect(self._flush_pending_frames)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # --- Top: Latest frame breakdown ---
        self._detail_group = QGroupBox("Frame Breakdown")
        detail_layout = QGridLayout(self._detail_group)
        detail_layout.setContentsMargins(6, 10, 6, 6)
        detail_layout.setSpacing(4)

        mono = QFont("Consolas", 9)

        self._lbl_direction = QLabel("—")
        self._lbl_protocol = QLabel("—")
        self._lbl_timestamp = QLabel("—")

        self._lbl_unit_id = QLabel("—")
        self._lbl_unit_id.setFont(mono)
        self._lbl_func_code = QLabel("—")
        self._lbl_func_code.setFont(mono)
        self._lbl_data = QLabel("—")
        self._lbl_data.setFont(mono)
        self._lbl_data.setWordWrap(True)

        self._lbl_recv_check = QLabel("—")
        self._lbl_recv_check.setFont(mono)
        self._lbl_calc_check = QLabel("—")
        self._lbl_calc_check.setFont(mono)
        self._lbl_status = QLabel("—")
        self._lbl_status.setFont(QFont("Consolas", 10, QFont.Bold))

        row = 0
        detail_layout.addWidget(QLabel("Direction:"), row, 0)
        detail_layout.addWidget(self._lbl_direction, row, 1)
        detail_layout.addWidget(QLabel("Protocol:"), row, 2)
        detail_layout.addWidget(self._lbl_protocol, row, 3)
        detail_layout.addWidget(QLabel("Time:"), row, 4)
        detail_layout.addWidget(self._lbl_timestamp, row, 5)

        row += 1
        detail_layout.addWidget(QLabel("Unit ID:"), row, 0)
        detail_layout.addWidget(self._lbl_unit_id, row, 1)
        detail_layout.addWidget(QLabel("Function:"), row, 2)
        detail_layout.addWidget(self._lbl_func_code, row, 3, 1, 3)

        row += 1
        detail_layout.addWidget(QLabel("Data:"), row, 0)
        detail_layout.addWidget(self._lbl_data, row, 1, 1, 5)

        row += 1
        sep = QLabel("")
        sep.setStyleSheet("border-top: 1px solid #555;")
        sep.setFixedHeight(2)
        detail_layout.addWidget(sep, row, 0, 1, 6)

        row += 1
        detail_layout.addWidget(QLabel("Received:"), row, 0)
        detail_layout.addWidget(self._lbl_recv_check, row, 1)
        detail_layout.addWidget(QLabel("Calculated:"), row, 2)
        detail_layout.addWidget(self._lbl_calc_check, row, 3)
        detail_layout.addWidget(QLabel("Status:"), row, 4)
        detail_layout.addWidget(self._lbl_status, row, 5)

        layout.addWidget(self._detail_group)

        # --- Bottom: Frame history table ---
        self._history_table = QTableWidget()
        self._history_table.setColumnCount(6)
        self._history_table.setHorizontalHeaderLabels([
            "Time", "Dir", "Protocol", "Frame (Hex)", "Checksum", "Status"
        ])
        self._history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeToContents)
        self._history_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        self._history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._history_table.setAlternatingRowColors(True)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setFont(QFont("Consolas", 9))
        self._history_table.itemSelectionChanged.connect(self._on_history_selection)

        layout.addWidget(self._history_table, stretch=1)

    @property
    def rx_count(self) -> int:
        return self._rx_count

    @property
    def tx_count(self) -> int:
        return self._tx_count

    def reset_counters(self):
        self._rx_count = 0
        self._tx_count = 0

    @pyqtSlot(str, bytes, str)
    def on_frame_received(self, direction: str, raw_frame: bytes, protocol: str):
        """Handle incoming frame data from the bridge."""
        if direction == "RX":
            self._rx_count += 1
        else:
            self._tx_count += 1

        entry = self._parse_frame(direction, raw_frame, protocol)
        self._frame_history.appendleft(entry)
        self._pending_frames.append(entry)

        if not self._update_timer.isActive():
            self._update_timer.start()

    def _flush_pending_frames(self):
        """Batch-update the UI with pending frames."""
        self._update_timer.stop()
        if not self._pending_frames:
            return

        # Update detail panel with latest frame
        latest = self._pending_frames[-1]
        self._update_detail_panel(latest)

        # Rebuild history table
        self._rebuild_history_table()
        self._pending_frames.clear()

    def _parse_frame(self, direction: str, raw_frame: bytes, protocol: str) -> dict:
        """Parse a raw Modbus frame into a structured dict."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        entry = {
            "timestamp": timestamp,
            "direction": direction,
            "protocol": protocol,
            "raw": raw_frame,
            "hex": " ".join(f"{b:02X}" for b in raw_frame),
            "unit_id": None,
            "function_code": None,
            "function_name": "",
            "data_bytes": b"",
            "data_hex": "",
            "recv_check": None,
            "calc_check": None,
            "check_valid": None,
            "check_label": "N/A",
        }

        if len(raw_frame) < 2:
            return entry

        if protocol == "TCP":
            self._parse_tcp_frame(entry, raw_frame)
        elif protocol == "RTU":
            self._parse_rtu_frame(entry, raw_frame)
        elif protocol == "ASCII":
            self._parse_ascii_frame(entry, raw_frame)

        return entry

    def _parse_tcp_frame(self, entry: dict, frame: bytes):
        """Parse TCP/MBAP frame. No CRC/LRC — show MBAP header fields."""
        if len(frame) < 7:
            return
        # MBAP header: TransID(2) + ProtoID(2) + Length(2) + UnitID(1) + PDU...
        entry["unit_id"] = frame[6]
        if len(frame) >= 8:
            entry["function_code"] = frame[7]
            entry["function_name"] = get_function_code_name(frame[7])
        if len(frame) > 8:
            entry["data_bytes"] = frame[8:]
            entry["data_hex"] = " ".join(f"{b:02X}" for b in frame[8:])

        trans_id = (frame[0] << 8) | frame[1]
        mbap_len = (frame[4] << 8) | frame[5]
        entry["check_label"] = f"MBAP TxID={trans_id:#06x} Len={mbap_len}"
        entry["check_valid"] = True  # TCP has no checksum

    def _parse_rtu_frame(self, entry: dict, frame: bytes):
        """Parse RTU frame with CRC-16 validation."""
        if len(frame) < 4:
            return
        entry["unit_id"] = frame[0]
        entry["function_code"] = frame[1]
        entry["function_name"] = get_function_code_name(frame[1])

        # Data is everything between FC and CRC (last 2 bytes)
        entry["data_bytes"] = frame[2:-2]
        entry["data_hex"] = " ".join(f"{b:02X}" for b in frame[2:-2])

        # CRC validation
        recv_crc = frame[-2] | (frame[-1] << 8)
        calc_crc = calculate_crc16(frame[:-2])
        entry["recv_check"] = f"0x{recv_crc:04X}"
        entry["calc_check"] = f"0x{calc_crc:04X}"
        entry["check_valid"] = recv_crc == calc_crc
        entry["check_label"] = "CRC-16"

    def _parse_ascii_frame(self, entry: dict, frame: bytes):
        """Parse ASCII frame (already decoded payload) with LRC info."""
        # The frame from _log_comm_frame is the decoded payload (no LRC, no colon)
        if len(frame) < 2:
            return
        entry["unit_id"] = frame[0]
        entry["function_code"] = frame[1]
        entry["function_name"] = get_function_code_name(frame[1])

        if len(frame) > 2:
            entry["data_bytes"] = frame[2:]
            entry["data_hex"] = " ".join(f"{b:02X}" for b in frame[2:])

        # LRC: calculate over the payload we received
        calc_lrc = calculate_lrc(frame)
        entry["calc_check"] = f"0x{calc_lrc:02X}"
        entry["check_label"] = "LRC"
        # For ASCII, the server already validated LRC during decode;
        # the payload we get is valid (otherwise it would have been dropped)
        entry["check_valid"] = True
        entry["recv_check"] = "(validated)"

    def _update_detail_panel(self, entry: dict):
        """Update the top detail breakdown with a frame entry."""
        self._lbl_direction.setText(entry["direction"])
        self._lbl_protocol.setText(entry["protocol"])
        self._lbl_timestamp.setText(entry["timestamp"])

        if entry["unit_id"] is not None:
            self._lbl_unit_id.setText(f"0x{entry['unit_id']:02X} ({entry['unit_id']})")
        else:
            self._lbl_unit_id.setText("—")

        if entry["function_code"] is not None:
            fc = entry["function_code"]
            self._lbl_func_code.setText(f"0x{fc:02X} ({entry['function_name']})")
        else:
            self._lbl_func_code.setText("—")

        self._lbl_data.setText(entry["data_hex"] or "—")

        if entry["recv_check"] is not None:
            self._lbl_recv_check.setText(f"{entry['check_label']}: {entry['recv_check']}")
        else:
            self._lbl_recv_check.setText(entry["check_label"])

        if entry["calc_check"] is not None:
            self._lbl_calc_check.setText(f"{entry['check_label']}: {entry['calc_check']}")
        else:
            self._lbl_calc_check.setText("—")

        if entry["check_valid"] is True:
            self._lbl_status.setText("VALID")
            self._lbl_status.setStyleSheet("color: #4CAF50; font-weight: bold;")
        elif entry["check_valid"] is False:
            self._lbl_status.setText("MISMATCH")
            self._lbl_status.setStyleSheet("color: #F44336; font-weight: bold;")
        else:
            self._lbl_status.setText("—")
            self._lbl_status.setStyleSheet("")

    def _rebuild_history_table(self):
        """Rebuild the history table from the deque."""
        self._history_table.setRowCount(len(self._frame_history))
        for row, entry in enumerate(self._frame_history):
            self._history_table.setItem(row, 0, QTableWidgetItem(entry["timestamp"]))
            self._history_table.setItem(row, 1, QTableWidgetItem(entry["direction"]))
            self._history_table.setItem(row, 2, QTableWidgetItem(entry["protocol"]))
            self._history_table.setItem(row, 3, QTableWidgetItem(entry["hex"]))

            check_text = entry["check_label"]
            if entry["recv_check"]:
                check_text += f" {entry['recv_check']}"
            self._history_table.setItem(row, 4, QTableWidgetItem(check_text))

            if entry["check_valid"] is True:
                status_item = QTableWidgetItem("VALID")
                status_item.setForeground(QColor("#4CAF50"))
            elif entry["check_valid"] is False:
                status_item = QTableWidgetItem("FAIL")
                status_item.setForeground(QColor("#F44336"))
            else:
                status_item = QTableWidgetItem("—")
            self._history_table.setItem(row, 5, status_item)

    def _on_history_selection(self):
        """When a row is selected in history, show its details in the breakdown."""
        rows = self._history_table.selectionModel().selectedRows()
        if not rows:
            return
        row_idx = rows[0].row()
        if 0 <= row_idx < len(self._frame_history):
            entry = self._frame_history[row_idx]
            self._update_detail_panel(entry)
