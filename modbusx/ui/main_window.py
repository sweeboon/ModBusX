from PyQt5.QtWidgets import (
    QMainWindow, QDialog, QSplitter, QSizePolicy,
    QAbstractItemView, QWidget, QHBoxLayout, QVBoxLayout, QLabel, QCheckBox,
    QFileDialog, QMessageBox, QTableView, QHeaderView, QStyledItemDelegate,
    QSpinBox, QLineEdit, QToolButton, QStyle, QTabWidget
)
from PyQt5 import uic
from PyQt5.QtCore import Qt, QEvent
from PyQt5.QtGui import QStandardItemModel, QStandardItem, QValidator
from pathlib import Path
from typing import Optional
from .connect_dialog import ConnectDialog
from ..managers.connection_manager import ConnectionManager
from .components.register_table_view import RegisterTableView
from .components.frame_inspector_widget import FrameInspectorWidget
from ..managers.server_manager import ServerManager
from ..managers.data_refresh_manager import DataRefresher
from ..managers.address_mode_manager import AddressModeManager
from ..managers.language_manager import LanguageManager
from ..managers.backup_manager import BackupManager
from ..services.scripting_service import get_scripting_service
from modbusx.logger import global_logger
from modbusx.usability_logger import get_usability_logger
from .bulk_operations_manual import ManualBulkOperationsDialog
from ..services.register_validator import RegisterValidator
import json
from datetime import datetime
import sys
import modbusx.assets.resources_rc
from PyQt5.QtWidgets import QAction, QMenu


class FormatSpinBox(QSpinBox):
    """Spin box that renders register values in the requested format."""

    def __init__(self, fmt: str, parent=None):
        super().__init__(parent)
        self._fmt = fmt or "Unsigned"
        self.setKeyboardTracking(False)
        self.setFrame(False)
        if self._fmt == "Signed":
            self.setRange(-32768, 32767)
        else:
            self.setRange(0, 0xFFFF)
        self.setAccelerated(True)

    def textFromValue(self, value: int) -> str:
        if self._fmt == "Signed":
            return str(value)
        if self._fmt == "Hex":
            return f"0x{(value & 0xFFFF):04X}"
        if self._fmt == "Binary":
            return f"{(value & 0xFFFF):016b}"
        return str(value & 0xFFFF)

    def _parse_text(self, text: str) -> int:
        s = (text or "").strip()
        if not s:
            raise ValueError
        fmt = self._fmt.lower()
        if fmt == "signed":
            return int(s, 10)
        if fmt == "hex":
            if s.lower().startswith("0x"):
                s = s[2:]
            if not s:
                raise ValueError
            return int(s, 16)
        if fmt == "binary":
            if s.lower().startswith("0b"):
                s = s[2:]
            if not s or any(ch not in "01" for ch in s):
                raise ValueError
            return int(s, 2)
        return int(s, 10)

    def valueFromText(self, text: str) -> int:
        try:
            return self._parse_text(text)
        except ValueError:
            return self.value()

    def validate(self, text: str, pos: int):
        stripped = text.strip()
        fmt = self._fmt.lower()
        if not stripped or stripped in ("0x", "0X", "0b", "0B"):
            return (QValidator.Intermediate, text, pos)
        if fmt == "signed" and stripped in ("-", "+"):
            return (QValidator.Intermediate, text, pos)
        if fmt == "hex" and stripped.lower() in ("0x-", "0x+"):
            return (QValidator.Intermediate, text, pos)
        if fmt == "binary" and stripped.lower() == "0b":
            return (QValidator.Intermediate, text, pos)
        try:
            value = self._parse_text(text)
        except ValueError:
            return (QValidator.Invalid, text, pos)
        if self.minimum() <= value <= self.maximum():
            return (QValidator.Acceptable, text, pos)
        return (QValidator.Invalid, text, pos)

    def focusOutEvent(self, event):
        try:
            self.interpretText()
        except Exception:
            pass
        super().focusOutEvent(event)

    def focusOutEvent(self, event):
        try:
            self.interpretText()
        except Exception:
            pass
        super().focusOutEvent(event)


class FormatValueDelegate(QStyledItemDelegate):
    """Delegate that shows arrow editors for the format value column."""

    def __init__(self, owner: 'MainWindow'):
        super().__init__(owner.formatEditor)
        self._owner = owner

    def createEditor(self, parent, option, index):
        if index.column() != 1:
            return super().createEditor(parent, option, index)
        fmt_index = self._owner.format_model.index(index.row(), 0)
        fmt_code = fmt_index.data(Qt.UserRole) if fmt_index.isValid() else None
        raw_label = fmt_index.data() if fmt_index.isValid() else None
        fmt_name = self._owner._normalize_format_code(fmt_code or raw_label or "Unsigned")
        editor = FormatSpinBox(fmt_name, parent)
        editor.installEventFilter(self)
        editor.editingFinished.connect(lambda ed=editor: self.commitData.emit(ed))
        editor.editingFinished.connect(lambda ed=editor: self.closeEditor.emit(ed, QStyledItemDelegate.NoHint))
        return editor

    def setEditorData(self, editor, index):
        if isinstance(editor, FormatSpinBox):
            text = index.data() or "0"
            try:
                value = self._owner._parse_by_format(text, editor._fmt)
            except Exception:
                value = 0
            fmt = editor._fmt.lower()
            if fmt == "signed":
                signed_val = value if value <= 0x7FFF else value - 0x10000
                editor.setValue(signed_val)
            elif fmt in ("hex", "binary"):
                editor.setValue(value & 0xFFFF)
            else:
                editor.setValue(value & 0xFFFF)
        else:
            super().setEditorData(editor, index)

    def setModelData(self, editor, model, index):
        if isinstance(editor, FormatSpinBox):
            try:
                editor.interpretText()
            except Exception:
                pass
            raw = editor.value()
            norm = raw & 0xFFFF
            formatted = self._owner._format_all(norm).get(editor._fmt, str(norm))
            model.setData(index, formatted)
        else:
            super().setModelData(editor, model, index)

    def eventFilter(self, editor, event):
        if isinstance(editor, FormatSpinBox) and event.type() == QEvent.FocusOut:
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
        return super().eventFilter(editor, event)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        ui_path = Path(__file__).resolve().parent / "main_window.ui"
        uic.loadUi(str(ui_path), self)
        self.setWindowTitle("ModbusX Multi-Instance Slave Demo")
        self._current_language_code = 'en_US'
        self._current_config_path = None
        
        # ---- Usability Logging ----
        self.usability_logger = get_usability_logger()
        self.usability_logger.log_event("APP_START", "MainWindow", "Application initialized")

        # ---- Setup UI components ----
        self._setup_ui()
        self._setup_statusbar()
        
        # ---- Initialize managers ----
        self._setup_managers()
        
        # ---- Setup Language & Backup (New Features) ----
        self.language_manager = LanguageManager(sys.modules['__main__'].app.qt_app if hasattr(sys.modules['__main__'], 'app') else self) 
        # Note: In a real run, we'd pass the QApplication instance differently, 
        # but for this structure we assume the app is accessible or we pass 'self' and refactor manager.
        # Actually, let's fix the manager instantiation:
        from PyQt5.QtWidgets import QApplication
        self.language_manager = LanguageManager(QApplication.instance())
        self._setup_language_menu()
        
        self.backup_manager = BackupManager(self)
        self.backup_manager.start_auto_backup(self._export_full_configuration)

        # ---- Connect signals ----
        self._connect_signals()
        
        # Connect the logger's signal to append function with timestamp and module name
        global_logger.log_message.connect(self._handle_structured_log_message)
        # Fallback: typed messages without module name
        try:
            global_logger.debug_message.connect(
                lambda msg: self._handle_structured_log_message("DEBUG", "app", msg)
            )
            global_logger.info_message.connect(
                lambda msg: self._handle_structured_log_message("INFO", "app", msg)
            )
            global_logger.warning_message.connect(
                lambda msg: self._handle_structured_log_message("WARNING", "app", msg)
            )
            global_logger.error_message.connect(
                lambda msg: self._handle_structured_log_message("ERROR", "app", msg)
            )
        except Exception:
            pass

    def _setup_language_menu(self):
        """Setup the Language menu in the menu bar."""
        menubar = self.menuBar()
        # Try to find an existing Language menu by objectName first
        lang_menu = self.findChild(QMenu, "menuLanguage")
        if not lang_menu:
            # Fallback: search by title if created previously
            for action in menubar.actions():
                if action.menu() and action.menu().title() in ("Language", self.tr("Language")):
                    lang_menu = action.menu()
                    break
        if not lang_menu:
            # Create a dedicated Language menu and keep a reference
            lang_menu = menubar.addMenu(self.tr("Language"))
            lang_menu.setObjectName("menuLanguage")
        self.menuLanguage = lang_menu

        # Ensure previous actions are cleared then re-added in a stable way
        self.menuLanguage.clear()

        # Add English
        action_en = QAction(self.tr("English"), self)
        action_en.setObjectName("actionLanguageEnglish")
        action_en.triggered.connect(lambda: self._change_language("en_US"))
        self.menuLanguage.addAction(action_en)

        # Add Chinese
        action_zh = QAction(self.tr("Chinese (中文)"), self)
        action_zh.setObjectName("actionLanguageChinese")
        action_zh.triggered.connect(lambda: self._change_language("zh_CN"))
        self.menuLanguage.addAction(action_zh)

        # React immediately to language change to avoid double-click effect
        try:
            self.language_manager.language_changed.disconnect()
        except Exception:
            pass
        self.language_manager.language_changed.connect(self._on_language_changed)

    def _change_language(self, lang_code: str):
        """Request a language switch and track the current code."""
        try:
            self.language_manager.load_language(lang_code)
        except Exception:
            pass

    def _export_full_configuration(self):
        """Export current state for backup/save operations."""
        config = {
            "version": 1,
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "meta": {
                "address_mode": RegisterValidator.get_address_mode(),
                "protocol_display": RegisterValidator.get_protocol_display_format(),
                "language": getattr(self, "_current_language_code", "en_US"),
                "frame_inspector_visible": self.frame_inspector.isVisible()
            },
            "connections": []
        }
        model = self.tree_model
        for i in range(model.rowCount()):
            item = model.item(i)
            serialized = self._serialize_connection_item(item)
            if serialized:
                config["connections"].append(serialized)
        return config

    def _serialize_connection_item(self, conn_item):
        if not conn_item:
            return None
        conn_info = conn_item.data(Qt.UserRole) or {}
        data = {
            "slaves": []
        }
        if 'serial_port' in conn_info:
            data.update({
                "type": "serial",
                "serial_port": conn_info.get('serial_port'),
                "baudrate": conn_info.get('baudrate'),
                "protocol": conn_info.get('protocol')
            })
        else:
            data.update({
                "type": "tcp",
                "address": conn_info.get('address'),
                "port": conn_info.get('port')
            })

        for row in range(conn_item.rowCount()):
            slave_item = conn_item.child(row, 0)
            serialized_slave = self._serialize_slave_item(slave_item)
            if serialized_slave:
                data["slaves"].append(serialized_slave)
        return data

    def _serialize_slave_item(self, slave_item):
        if not slave_item:
            return None
        slave_info = slave_item.data(Qt.UserRole) or {}
        register_map = slave_info.get('register_map')
        serialized = {
            "slave_id": slave_info.get('slave_id'),
            "name": slave_info.get('name', ''),
            "register_map": register_map.to_dict() if hasattr(register_map, "to_dict") else {},
            "register_groups": [],
            "multi_type_groups": []
        }
        for row in range(slave_item.rowCount()):
            child = slave_item.child(row, 0)
            payload = child.data(Qt.UserRole)
            if not isinstance(payload, dict):
                continue
            if (payload.get('item_type') == 'register_group' or (payload.get('reg_type') and not payload.get('register_blocks'))) and not payload.get('is_multi_type_block'):
                serialized["register_groups"].append(self._serialize_register_group(payload))
            elif payload.get('item_type') == 'multi_type_group' or payload.get('register_blocks'):
                serialized["multi_type_groups"].append(self._serialize_multi_group(payload))
        return serialized

    def _serialize_register_group(self, payload: dict):
        return {
            "group_id": payload.get('register_id'),
            "group_name": payload.get('group_name', ''),
            "reg_type": payload.get('reg_type'),
            "start_addr": payload.get('start_addr'),
            "size": payload.get('size'),
            "description": payload.get('description', ''),
            "template_name": payload.get('template_name', ''),
            "alias_prefix": payload.get('alias_prefix', '')
        }

    def _serialize_multi_group(self, payload: dict):
        result = {
            "group_id": payload.get('group_id'),
            "name": payload.get('name', ''),
            "description": payload.get('description', ''),
            "blocks": payload.get('blocks', []),
            "metadata": payload.get('metadata', {}),
            "group_type": payload.get('group_type', 'multi_type')
        }
        return result

    def _setup_ui(self):
        """Initialize UI components."""
        # Tree setup
        self.treeView = getattr(self, "treeView", None)
        self.tree_model = QStandardItemModel()
        self.tree_model.setHorizontalHeaderLabels([self.tr('Connections')])
        self.treeView.setModel(self.tree_model)
        self.treeView.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        # Table setup
        self.tableView = getattr(self, "tableView", None)
        self.reg_table_model = QStandardItemModel(self)
        self.reg_table_model.setHorizontalHeaderLabels([
            self.tr("Register Type"), self.tr("Address"), self.tr("Alias"), 
            self.tr("Value"), self.tr("Comment")
        ])
        self.tableView.setModel(self.reg_table_model)

        # Splitter setup
        self.splitter = self.findChild(QSplitter, "splitter")
        if self.splitter:
            self.splitter.setStretchFactor(0, 1)     # treeView scales a bit
            self.splitter.setStretchFactor(1, 2.5)     # right panel scales more

        self.splitterMain = self.findChild(QSplitter, "splitterMain")
        if self.splitterMain:
            self.splitterMain.setStretchFactor(0, 2)  # main area scales more
            self.splitterMain.setStretchFactor(1, 1)  # log area scales less

        # Log pane visibility + filtering defaults
        self.show_all_logs = False
        if hasattr(self, 'statusText'):
            try:
                self.statusText.setReadOnly(True)
                self.statusText.setFocusPolicy(Qt.NoFocus)
            except Exception:
                pass
            if hasattr(self, 'actionShowLogsPane'):
                self.actionShowLogsPane.setChecked(True)
                self.actionShowLogsPane.toggled.connect(self.statusText.setVisible)
            else:
                self.statusText.setVisible(True)
        if hasattr(self, 'actionShowAllLogs'):
            self.actionShowAllLogs.setChecked(False)
            self.actionShowAllLogs.toggled.connect(self._on_show_all_logs_toggled)
        else:
            # If toggle absent, default to showing every log entry
            self.show_all_logs = True
            
        # Ensure Bulk Operations action exists
        if not hasattr(self, 'actionBulkOperations'):
            self.actionBulkOperations = QAction(self.tr("Bulk Operations..."), self)
            self.actionBulkOperations.setObjectName("actionBulkOperations")
            # Try to add to Edit menu
            edit_menu = self.findChild(QMenu, "menuEdit")
            if edit_menu:
                edit_menu.addAction(self.actionBulkOperations)
            else:
                # Fallback to menu bar
                self.menuBar().addAction(self.actionBulkOperations)
                
        self.actionBulkOperations.triggered.connect(self._show_bulk_operations_dialog)

        # Make the table editable for specific columns
        self.tableView.setEditTriggers(
            QAbstractItemView.DoubleClicked | 
            QAbstractItemView.EditKeyPressed | 
            QAbstractItemView.AnyKeyPressed
        )
        
        # Setup address mode toolbar controls
        self._setup_address_mode_toolbar()

        # Secondary format preview table (bottom-right)
        self.formatEditor = self.findChild(QTableView, "formatEditor")
        if self.formatEditor:
            self._format_codes = ["Unsigned", "Signed", "Hex", "Binary"]
            self.format_model = QStandardItemModel(len(self._format_codes), 2, self)
            self.format_model.setHorizontalHeaderLabels([self.tr("Format"), self.tr("Value")])
            for r, code in enumerate(self._format_codes):
                fmt_item = QStandardItem(self._get_format_label(code))
                fmt_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                fmt_item.setData(code, Qt.UserRole)
                self.format_model.setItem(r, 0, fmt_item)
                self.format_model.setItem(r, 1, QStandardItem(""))
            self.formatEditor.setModel(self.format_model)
            try:
                header = self.formatEditor.horizontalHeader()
                header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
                header.setSectionResizeMode(1, QHeaderView.Stretch)
                header.setSectionsClickable(False)
                self.formatEditor.setSortingEnabled(False)
                self.formatEditor.verticalHeader().setVisible(False)
                self.formatEditor.setItemDelegate(FormatValueDelegate(self))
                self.formatEditor.setEditTriggers(
                    QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
                )
            except Exception:
                pass

        # Frame Inspector widget (CRC/LRC visualization) — hidden by default
        self.frame_inspector = FrameInspectorWidget(self)
        splitter_2 = self.findChild(QSplitter, "splitter_2")
        if splitter_2:
            splitter_2.addWidget(self.frame_inspector)
            splitter_2.setStretchFactor(2, 1)
        self.frame_inspector.setVisible(False)

        # Connect Redundancy Check action (defined in .ui under Tools menu)
        if hasattr(self, 'actionRedundancy_Check'):
            self.actionRedundancy_Check.setChecked(False)
            self.actionRedundancy_Check.toggled.connect(self.frame_inspector.setVisible)

    def _setup_statusbar(self):
        """Add persistent panels to the status bar for group and count info."""
        try:
            # Left slot is used by transient messages (showMessage). We add permanent widgets on the right.
            self.group_status_label = QLabel(self.tr("Group: —"))
            self.group_status_label.setObjectName("groupStatusLabel")

            self.reg_count_status_label = QLabel(self.tr("Registers: 0"))
            self.reg_count_status_label.setObjectName("registerCountStatusLabel")

            # Minor spacing and alignment
            self.group_status_label.setContentsMargins(8, 0, 8, 0)
            self.reg_count_status_label.setContentsMargins(8, 0, 8, 0)

            if hasattr(self, 'statusbar') and self.statusbar:
                # Stretch keeps labels visible while leaving room for messages
                self.statusbar.addPermanentWidget(self.group_status_label, 1)
                self.statusbar.addPermanentWidget(self.reg_count_status_label, 0)

            # Overall total registers across current slave
            self.total_regs_status_label = QLabel(self.tr("Total: 0"))
            self.total_regs_status_label.setObjectName("totalRegistersStatusLabel")
            self.total_regs_status_label.setContentsMargins(8, 0, 8, 0)

            self.rx_count_label = QLabel("RX: 0")
            self.rx_count_label.setObjectName("rxCountLabel")
            self.rx_count_label.setContentsMargins(8, 0, 8, 0)

            self.tx_count_label = QLabel("TX: 0")
            self.tx_count_label.setObjectName("txCountLabel")
            self.tx_count_label.setContentsMargins(8, 0, 8, 0)

            if hasattr(self, 'statusbar') and self.statusbar:
                self.statusbar.addPermanentWidget(self.total_regs_status_label, 0)
                self.statusbar.addPermanentWidget(self.rx_count_label, 0)
                self.statusbar.addPermanentWidget(self.tx_count_label, 0)
        except Exception:
            pass
        # Initialize with current selection (if any)
        try:
            self._update_statusbar_info()
        except Exception:
            pass
    
    def _setup_address_mode_toolbar(self):
        """Setup address mode selection in toolbar."""
        # Get the toolbar (created in UI file)
        toolbar = getattr(self, "toolBar", None)
        if not toolbar:
            return
            
        # Add separator
        toolbar.addSeparator()
        
        # Create address mode checkbox
        self.address_mode_checkbox = QCheckBox(self.tr("PLC Address (Base 1)"))
        current_mode = RegisterValidator.get_address_mode()
        self.address_mode_checkbox.setChecked(current_mode == 'plc')
        self.address_mode_checkbox.setToolTip(
            self.tr("Toggle between PLC addressing")
        )
        
        # Protocol decimal display option (only applicable when PLC is off)
        self.protocol_decimal_checkbox = QCheckBox(self.tr("Decimal (Protocol Address Only)"))
        self.protocol_decimal_checkbox.setToolTip(
            self.tr("Show protocol addresses in decimal instead of hex")
        )
        # Initialize from saved settings
        self.protocol_decimal_checkbox.setChecked(
            RegisterValidator.get_protocol_display_format() == 'dec'
        )
        # Disable if PLC is active
        self.protocol_decimal_checkbox.setEnabled(not self.address_mode_checkbox.isChecked())
        
        # Create toolbar widget with vertical layout so Decimal sits below PLC
        toolbar_widget = QWidget()
        toolbar_layout = QVBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(5, 0, 5, 0)
        toolbar_layout.setSpacing(2)

        self.address_format_label = QLabel(self.tr("Address Format:"))
        toolbar_layout.addWidget(self.address_format_label)
        toolbar_layout.addWidget(self.address_mode_checkbox)
        toolbar_layout.addWidget(self.protocol_decimal_checkbox)
        
        # Add to toolbar
        toolbar.addWidget(toolbar_widget)

        # Spacer to push search input to the right
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        toolbar.addWidget(spacer)

        # Search input for quick address navigation
        search_container = QWidget()
        search_layout = QHBoxLayout(search_container)
        search_layout.setContentsMargins(5, 0, 5, 0)
        search_layout.setSpacing(4)
        self.search_label = QLabel(self.tr("Search Address:"))
        self.search_input = QLineEdit()
        self.search_input.setObjectName("addressSearchInput")
        self.search_input.setPlaceholderText(self.tr("e.g. 400005 / 0x0004 / 4"))
        self.search_input.returnPressed.connect(self._on_search_address)
        search_layout.addWidget(self.search_label)
        input_container = QWidget()
        input_layout = QHBoxLayout(input_container)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(0)
        input_layout.addWidget(self.search_input)
        self.search_button = QToolButton()
        self.search_button.setIcon(self.style().standardIcon(QStyle.SP_FileDialogContentsView))
        self.search_button.setToolTip(self.tr("Search address"))
        self.search_button.setCursor(Qt.PointingHandCursor)
        self.search_button.setStyleSheet("QToolButton { border: none; padding: 0px; }")
        self.search_button.clicked.connect(self._on_search_address)
        input_layout.addWidget(self.search_button)
        search_layout.addWidget(input_container)

        # Bottom align within toolbar
        search_holder = QWidget()
        holder_layout = QVBoxLayout(search_holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setSpacing(0)
        holder_layout.addStretch(1)
        holder_layout.addWidget(search_container)
        toolbar.addWidget(search_holder)
    
    def _setup_managers(self):
        """Initialize all manager classes."""
        # Connection manager for tree operations
        self.connection_manager = ConnectionManager(self.treeView, self.tree_model, self)
        
        # Replace standard QTableView with enhanced RegisterTableView
        # Preserve layout and size policy from UI file
        old_table = self.tableView
        parent_splitter = old_table.parent()
        geometry = old_table.geometry()
        size_policy = old_table.sizePolicy()
        object_name = old_table.objectName()

        # Create enhanced RegisterTableView
        self.register_editor = RegisterTableView(parent_splitter)
        self.register_editor.setGeometry(geometry)
        self.register_editor.setSizePolicy(size_policy)
        self.register_editor.setObjectName(object_name)

        # Use RegisterTableView's internal model instead of external one
        self.reg_table_model = self.register_editor.model

        # Replace widget in splitter
        if parent_splitter and hasattr(parent_splitter, 'replaceWidget'):
            # QSplitter.replaceWidget expects (index, widget)
            for i in range(parent_splitter.count()):
                if parent_splitter.widget(i) == old_table:
                    parent_splitter.replaceWidget(i, self.register_editor)
                    break

        # Ensure proper size and visibility
        self.register_editor.resize(geometry.width(), geometry.height())
        self.register_editor.show()

        # Hide and delete old table
        old_table.hide()
        old_table.deleteLater()

        # Update reference for other components that expect tableView
        self.tableView = self.register_editor

        # Force geometry update
        parent_splitter.update() if parent_splitter else None
        
        # Server manager for Modbus server lifecycle
        self.server_manager = ServerManager(self)
        
        # Data refresher for real-time updates
        self.data_refresher = DataRefresher(self.reg_table_model, self.tableView, self)
        
        # Address mode manager for dynamic addressing
        self.address_mode_manager = AddressModeManager(self)

        # Scripting service shim (no manager dependency)
        self._scripting_service = get_scripting_service()
    
    def _connect_signals(self):
        """Connect all signals and slots."""
        # Tree selection changes
        self.treeView.selectionModel().currentChanged.connect(self.on_tree_selection_changed)

        # Menu actions
        if hasattr(self, "actionConnect"):
            self.actionConnect.triggered.connect(self.show_new_connection_dialog)
        if hasattr(self, "actionOpenConnect"):
            self.actionOpenConnect.triggered.connect(self.open_selected_connection)
        if hasattr(self, "actionCloseConnect"):
            self.actionCloseConnect.triggered.connect(self.close_selected_connection)
        if hasattr(self, "actionAddSlave"):
            self.actionAddSlave.triggered.connect(self.add_slave_to_selected_connection)
        if hasattr(self, "actionAddRegisterGroup"):
            self.actionAddRegisterGroup.triggered.connect(self.add_reggroup_to_selected_slave)
        if hasattr(self, "actionSaveConfiguration"):
            self.actionSaveConfiguration.triggered.connect(self._save_configuration)
        if hasattr(self, "actionSaveConfigurationAs"):
            self.actionSaveConfigurationAs.triggered.connect(self._save_configuration_as)
        if hasattr(self, "actionLoadConfiguration"):
            self.actionLoadConfiguration.triggered.connect(self._load_configuration_from_file)
        
        # Manager signals
        self.connection_manager.connection_added.connect(self.on_connection_added)
        self.connection_manager.slave_added.connect(self.on_slave_added)
        self.connection_manager.register_group_added.connect(self.on_register_group_added)
        # Requests from ConnectionManager that require ServerManager actions
        if hasattr(self.connection_manager, 'close_connection_requested'):
            self.connection_manager.close_connection_requested.connect(self._on_close_connection_requested)
        if hasattr(self.connection_manager, 'refresh_connection_requested'):
            self.connection_manager.refresh_connection_requested.connect(self._on_refresh_connection_requested)
        
        self.server_manager.server_started.connect(self.on_server_started)
        self.server_manager.server_stopped.connect(self.on_server_stopped)
        self.server_manager.server_error.connect(self.on_server_error)
        self.server_manager.server_status.connect(self.on_server_status)
        self.server_manager.frame_received.connect(self.frame_inspector.on_frame_received)
        self.server_manager.frame_received.connect(self._update_frame_counters)
        
        self.register_editor.register_changed.connect(self.on_register_changed)
        self.data_refresher.data_updated.connect(self.on_data_updated)
        if hasattr(self, 'formatEditor') and self.formatEditor:
            self.register_editor.row_selected.connect(self._update_format_editor_for_row)
            self.register_editor.cell_changed.connect(self._on_table_cell_changed)
            try:
                self.format_model.itemChanged.connect(self._on_format_editor_item_changed)
            except Exception:
                pass
        
        # Address mode manager signals
        if hasattr(self, 'address_mode_checkbox'):
            self.address_mode_checkbox.toggled.connect(self.address_mode_manager.toggle_address_mode)
        self.address_mode_manager.mode_changed.connect(self._on_address_mode_changed)
        # Keep group display in sync with address format changes
        self.address_mode_manager.mode_changed.connect(self._update_statusbar_info)
        # Protocol decimal toggle handler
        if hasattr(self, 'protocol_decimal_checkbox'):
            self.protocol_decimal_checkbox.toggled.connect(self._on_protocol_decimal_toggled)
        
        # Connect address mode changes to tree refresh (Option 2: Event-driven approach)
        self.address_mode_manager.mode_changed.connect(self._refresh_tree_addresses)
        
        # Connect register editor to address mode changes
        if hasattr(self.register_editor, 'connect_address_mode_signals'):
            self.register_editor.connect_address_mode_signals(self.address_mode_manager)
        else:
            # Fallback connection
            self.address_mode_manager.connect_component(self.register_editor)

        # Update counts when the table model structure changes
        try:
            self.register_editor.model.rowsInserted.connect(lambda *_: self._update_statusbar_info())
            self.register_editor.model.rowsRemoved.connect(lambda *_: self._update_statusbar_info())
            self.register_editor.model.modelReset.connect(lambda *_: self._update_statusbar_info())
        except Exception:
            pass

        # Scripting menu actions
        if hasattr(self, "actionRunScript"):
            self.actionRunScript.triggered.connect(self._run_script_dialog)
        if hasattr(self, "actionStopScript"):
            self.actionStopScript.triggered.connect(self._stop_script)
        self._update_save_config_action_label()

    def _run_script_dialog(self):
        self.usability_logger.log_event("DIALOG_OPEN", "RunScript")
        path, _ = QFileDialog.getOpenFileName(
            self, self.tr("Run Script"), "", self.tr("JSON Files (*.json);;All Files (*)")
        )
        if not path:
            self.usability_logger.log_event("DIALOG_CLOSE", "RunScript", "Cancelled")
            return
        
        self.usability_logger.log_event("ACTION", "RunScript", f"Selected: {Path(path).name}")
        ok = self._scripting_service.run_from_file(path)
        if ok:
            QMessageBox.information(self, self.tr("Script"), self.tr("Started script from: {}").format(path))
        else:
            self.usability_logger.log_event("ERROR", "RunScript", "Failed to start")
            QMessageBox.critical(self, self.tr("Script"), self.tr("Failed to start script from: {}").format(path))

    def _stop_script(self):
        try:
            self._scripting_service.stop()
            QMessageBox.information(self, self.tr("Script"), self.tr("Stopped script"))
        except Exception as e:
            QMessageBox.warning(self, self.tr("Script"), self.tr("Stop failed: {}").format(str(e)))
    
    def _save_configuration(self):
        """Save configuration to current path or prompt if none."""
        if not self._current_config_path:
            self._save_configuration_as()
            return
        self._write_configuration(self._current_config_path)

    def _save_configuration_as(self):
        """Prompt for file path and save configuration."""
        path, _ = QFileDialog.getSaveFileName(
            self,
            self.tr("Save Configuration As..."),
            "",
            self.tr("ModbusX Configuration (*.modbusx.json);;JSON Files (*.json);;All Files (*)")
        )
        if not path:
            return
        self._write_configuration(path)

    def _write_configuration(self, path: str):
        """Write configuration to supplied path."""
        try:
            config = self._export_full_configuration()
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(config, handle, indent=2)
            self._set_current_config_path(path)
            QMessageBox.information(self, self.tr("Save Configuration"), self.tr("Saved configuration to: {}").format(path))
        except Exception as exc:
            QMessageBox.critical(self, self.tr("Save Configuration"), self.tr("Failed to save configuration:\n{}").format(str(exc)))

    def _load_configuration_from_file(self):
        """Load a configuration file and rebuild the UI state."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            self.tr("Load Configuration"),
            "",
            self.tr("ModbusX Configuration (*.modbusx.json);;JSON Files (*.json);;All Files (*)")
        )
        if not path:
            return
        if self.tree_model.rowCount() > 0:
            reply = QMessageBox.question(
                self,
                self.tr("Load Configuration"),
                self.tr("Loading a configuration will replace all existing connections. Continue?")
            )
            if reply != QMessageBox.Yes:
                return
        try:
            with open(path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            self._apply_full_configuration(data)
            self._set_current_config_path(path)
            QMessageBox.information(self, self.tr("Load Configuration"), self.tr("Loaded configuration from: {}").format(path))
        except Exception as exc:
            QMessageBox.critical(self, self.tr("Load Configuration"), self.tr("Failed to load configuration:\n{}").format(str(exc)))

    def _apply_full_configuration(self, config_data):
        """Apply configuration dictionary to the UI."""
        if not isinstance(config_data, dict):
            raise ValueError(self.tr("Invalid configuration file"))
        version = config_data.get('version', 1)
        if version != 1:
            raise ValueError(self.tr("Configuration version {} is not supported").format(version))
        self._apply_configuration_metadata(config_data.get('meta', {}))
        connections = config_data.get('connections', [])
        self.connection_manager.restore_connections(connections)
        if hasattr(self, 'register_editor'):
            self.register_editor.clear_table()
        try:
            self.treeView.clearSelection()
        except Exception:
            pass
        self._update_statusbar_info()

    def _apply_configuration_metadata(self, meta: dict):
        """Set UI preferences based on configuration metadata."""
        if not isinstance(meta, dict):
            return
        language = meta.get('language')
        if language and language != getattr(self, '_current_language_code', 'en_US'):
            self._change_language(language)
        address_mode = meta.get('address_mode')
        if address_mode in ('plc', 'protocol') and hasattr(self, 'address_mode_checkbox'):
            self.address_mode_checkbox.setChecked(address_mode == 'plc')
        protocol_display = meta.get('protocol_display')
        if protocol_display in ('hex', 'dec') and hasattr(self, 'protocol_decimal_checkbox'):
            desired = protocol_display == 'dec'
            if bool(desired) != self.protocol_decimal_checkbox.isChecked():
                self.protocol_decimal_checkbox.setChecked(desired)
        frame_inspector_visible = meta.get('frame_inspector_visible', False)
        if hasattr(self, 'actionRedundancy_Check'):
            self.actionRedundancy_Check.setChecked(bool(frame_inspector_visible))
    
    def _set_current_config_path(self, path: Optional[str]):
        self._current_config_path = path
        self._update_save_config_action_label()

    def _update_save_config_action_label(self):
        if hasattr(self, 'actionSaveConfiguration'):
            self.actionSaveConfiguration.setText(self.tr("Save Configuration"))
            if self._current_config_path:
                tip = self.tr("Save to current configuration file.")
            else:
                tip = self.tr("Save configuration to a chosen file.")
            self.actionSaveConfiguration.setToolTip(tip)

    def _show_bulk_operations_dialog(self):
        """Show the reliable Manual Bulk Operations Dialog."""
        self.usability_logger.log_event("DIALOG_OPEN", "BulkOpsDialog", "User requested bulk operations")
        
        # Get current context
        try:
            # Try to get map from current selection
            group = getattr(self.register_editor, 'current_reg_group', None)
            reg_map = None
            if group and isinstance(group, dict):
                reg_map = group.get('parent_slave_map')
            
            # If no selection, try to find a valid slave from tree
            if not reg_map:
                # Basic fallback: first slave of first connection
                if self.tree_model.rowCount() > 0:
                    conn = self.tree_model.item(0)
                    if conn.rowCount() > 0:
                        slave = conn.child(0)
                        data = slave.data(Qt.UserRole)
                        if data:
                            reg_map = data.get('register_map')
            
            if not reg_map:
                QMessageBox.warning(self, self.tr("Bulk Operations"), self.tr("Please select a slave device or register group first."))
                self.usability_logger.log_event("DIALOG_CANCEL", "BulkOpsDialog", "No register map context found")
                return

            dialog = ManualBulkOperationsDialog(reg_map, self)
            
            # Execute
            result = dialog.exec_()
            if result == QDialog.Accepted:
                self.usability_logger.log_event("DIALOG_CLOSE", "BulkOpsDialog", "Accepted")
                # Refresh UI
                if hasattr(self, 'register_editor'):
                    self.register_editor.refresh_current_view()
                self._update_statusbar_info()
            else:
                self.usability_logger.log_event("DIALOG_CLOSE", "BulkOpsDialog", "Rejected/Cancelled")
                
        except Exception as e:
            global_logger.exception(f"Error showing bulk operations dialog: {e}")
            self.usability_logger.log_event("ERROR", "BulkOpsDialog", str(e))

    def show_connect_dialog(self):
        """Show legacy connection dialog (TCP only) and add connection if accepted."""
        dlg = ConnectDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            port = dlg.settings["port"]
            address = dlg.settings["address"]
            self.connection_manager.add_connection(port, address)
    
    def show_new_connection_dialog(self):
        """Show new TCP/RTU connection dialog and add connection if accepted."""
        from .connect_dialog import ConnectDialog
        
        self.usability_logger.log_event("DIALOG_OPEN", "ConnectDialog")
        dlg = ConnectDialog(self)
        if dlg.exec_() == QDialog.Accepted:
            settings = dlg.settings
            self.usability_logger.log_event("DIALOG_CLOSE", "ConnectDialog", f"Accepted: {settings.get('protocol')}")
            
            if settings.get('protocol') == 'tcp':
                # TCP connection - use existing connection manager method
                port = settings["port"]
                address = settings["address"]
                self.connection_manager.add_connection(port, address)
                
                # Show status message
                self.append_to_log_widget(self.tr("TCP Connection created: {}:{}").format(address, port))
                
            elif settings.get('protocol') in ['rtu', 'ascii']:
                # RTU/ASCII connection - create in connection manager
                serial_port = settings["port"]  # Serial port name
                baudrate = settings.get("baudrate", 9600)
                
                # For now, add as a special connection in the tree
                # The connection manager will need to be enhanced to handle RTU
                self.connection_manager.add_rtu_connection(
                    serial_port, baudrate, settings.get('protocol', 'rtu')
                )
                
                # Show status message  
                self.append_to_log_widget(self.tr("{} Connection created: {} @ {} baud").format(settings['protocol'].upper(), serial_port, baudrate))
        else:
            self.usability_logger.log_event("DIALOG_CLOSE", "ConnectDialog", "Cancelled")

    def open_selected_connection(self):
        """Open the selected connection by starting its Modbus server."""
        connection_item = self.connection_manager.get_selected_connection_item()
        if not connection_item:
            return
            
        conn_info = self.connection_manager.get_connection_info(connection_item)
        if not conn_info:
            return
        
        # Build unit_definitions for the server
        unit_definitions = {}
        for slave in conn_info.get("slaves", []):
            unit_definitions[slave["slave_id"]] = slave
        
        # Check if server is already running
        if self.server_manager.is_server_running(conn_info):
            return
            
        # Start the server using connection_info
        # The status will be updated by the server_started signal handler when server actually starts
        self.server_manager.start_server(conn_info, unit_definitions)

    def close_selected_connection(self):
        """Close the selected connection by stopping its Modbus server."""
        connection_item = self.connection_manager.get_selected_connection_item()
        if not connection_item:
            return
            
        conn_info = self.connection_manager.get_connection_info(connection_item)
        if not conn_info:
            return
        
        # Check if server is running and stop it
        if not self.server_manager.is_server_running(conn_info):
            return
            
        # Stop the server using connection_info
        if self.server_manager.stop_server(conn_info):
            self.connection_manager.update_connection_status(connection_item, False)

    def add_slave_to_selected_connection(self):
        """Add a new slave to the selected connection."""
        self.usability_logger.log_event("ACTION", "AddSlave", "Triggered")
        self.connection_manager.add_slave_to_selected_connection()

    def add_reggroup_to_selected_slave(self):
        """Add a new register group to the selected slave."""
        self.usability_logger.log_event("ACTION", "AddGroup", "Triggered")
        self.connection_manager.add_register_group_to_selected_slave()

    def on_tree_selection_changed(self, current, previous):
        """Handle tree selection changes."""
        item = self.tree_model.itemFromIndex(current)
        if not item:
            self.register_editor.set_current_register_group(None)
            self.data_refresher.set_current_register_group(None)
            self._update_statusbar_info()
            self._clear_format_editor()
            return
            
        group_meta = item.data(Qt.UserRole)
        if isinstance(group_meta, dict) and "parent_slave_map" in group_meta:
            # This is a register group - show it in the editor
            self.register_editor.set_current_register_group(group_meta)
            self.data_refresher.set_current_register_group(group_meta)
            self._update_statusbar_info()
            try:
                row = self.register_editor.currentIndex().row()
                if row is None or row < 0:
                    row = 0
                self._update_format_editor_for_row(row)
            except Exception:
                pass
        else:
            # Not a register group - clear the editor
            self.register_editor.set_current_register_group(None)
            self.data_refresher.set_current_register_group(None)
            self._update_statusbar_info()
            self._clear_format_editor()

    def _handle_structured_log_message(self, level: str, module_name: str, msg: str):
        """Handle structured log signals from the global logger."""
        formatted = self._format_full_log(level, module_name, msg)
        self._append_filtered_log_line(msg, formatted)

    def _format_full_log(self, level: str, module_name: str, msg: str) -> str:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        lvl = (level or "INFO").upper()
        module = module_name or "app"
        return f"[{timestamp}] {lvl:8} [{module}] {msg}"

    def _append_filtered_log_line(self, raw_msg: str, formatted_msg: str):
        raw_text = (raw_msg or "").strip()
        is_comm = self._is_comm_traffic(raw_text)
        if self.show_all_logs:
            self.append_to_log_widget(formatted_msg)
        elif is_comm:
            self.append_to_log_widget(self._format_comm_log(raw_text), force=True)
        # Non-communication logs are suppressed when show_all_logs is False

    def _extract_comm_payload(self, msg: str):
        if not msg:
            return None, None
        text = msg.strip()
        lower = text.lower()
        if lower.startswith("received modbus tcp request:"):
            payload = text.split(":", 1)[1].strip()
            return "RX", payload
        if lower.startswith("sending tcp response:"):
            payload = text.split(":", 1)[1].strip()
            return "TX", payload
        if len(text) >= 2:
            direction = text[:2].upper()
            if direction in ("RX", "TX"):
                payload = text[2:].strip()
                return direction, payload
        return None, None

    def _format_comm_log(self, msg: str) -> str:
        """Format communication messages as Direction Bytes Timestamp."""
        direction, payload = self._extract_comm_payload(msg)
        if not direction or not payload:
            return msg
        cleaned = payload.replace(" ", "")
        if len(cleaned) < 2:
            return msg
        cleaned = ''.join(ch for ch in cleaned if ch.isalnum()).upper()
        if len(cleaned) % 2 != 0:
            cleaned = cleaned[:-1]
        byte_pairs = [cleaned[i:i+2] for i in range(0, len(cleaned), 2)]
        if not byte_pairs:
            return msg
        data_str = " ".join(byte_pairs)
        timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
        return f"{timestamp} | {direction} | {data_str}"

    def _is_comm_traffic(self, msg: str) -> bool:
        direction, payload = self._extract_comm_payload(msg)
        return bool(direction and payload)

    def append_to_log_widget(self, msg, force: bool = False):
        """Append message to the log widget, preserving user scroll position.

        If the user has scrolled up (not near the bottom), do not auto-scroll.
        """
        if not force and not self.show_all_logs and not self._is_comm_traffic(msg):
            return
        try:
            te = self.statusText
            sb = te.verticalScrollBar()
            prev_value = sb.value()
            prev_max = sb.maximum()
            at_bottom = prev_value >= (prev_max - 5)

            # Insert text at the end without forcing the viewport to jump unless at bottom
            end_cursor = te.textCursor()
            end_cursor.movePosition(end_cursor.End)
            te.setTextCursor(end_cursor)
            te.insertPlainText(str(msg) + "\n")

            if at_bottom:
                sb.setValue(sb.maximum())
            else:
                # Restore previous scroll position
                sb.setValue(prev_value)
        except Exception:
            pass

    def _update_frame_counters(self, direction: str, raw_frame: bytes, protocol: str):
        """Update RX/TX counters in the status bar."""
        if hasattr(self, 'rx_count_label'):
            self.rx_count_label.setText(f"RX: {self.frame_inspector.rx_count}")
        if hasattr(self, 'tx_count_label'):
            self.tx_count_label.setText(f"TX: {self.frame_inspector.tx_count}")

    # ---- Manager Signal Handlers ----
    
    def on_connection_added(self, node_text, port, address):
        """Handle connection added signal."""
        global_logger.log(f"Connection added: {node_text}")
    
    def on_slave_added(self, slave_id, connection_text):
        """Handle slave added signal."""
        global_logger.log(f"Slave {slave_id} added to {connection_text}")
    
    def on_register_group_added(self, group_id, slave_text):
        """Handle register group added signal."""
        global_logger.log(f"Register group {group_id} added to {slave_text}")
        self._update_statusbar_info()
    
    def on_server_started(self, address, port):
        """Handle server started signal - update tree status to OPEN."""
        # Find the matching connection item and update status
        connection_item = self._find_connection_item(address, port)
        if connection_item:
            self.connection_manager.update_connection_status(connection_item, True)
    
    def on_server_stopped(self, address, port):
        """Handle server stopped signal - remove OPEN status from tree."""
        # Find the matching connection item and update status
        connection_item = self._find_connection_item(address, port)
        if connection_item:
            self.connection_manager.update_connection_status(connection_item, False)

    # ---- Requests from ConnectionManager ----
    def _on_close_connection_requested(self, connection_info: dict):
        try:
            self.server_manager.stop_server(connection_info)
        except Exception as e:
            global_logger.log(f"Close connection request failed: {e}")

    def _on_refresh_connection_requested(self, connection_info: dict):
        try:
            self.server_manager.refresh_server_context(connection_info)
        except Exception as e:
            global_logger.log(f"Refresh connection request failed: {e}")
    
    def on_server_error(self, error_msg):
        """Handle server error signal."""
        pass
    
    def on_server_status(self, status_msg):
        """Handle server status signal."""
        self.append_to_log_widget(status_msg)
    
    def on_register_changed(self, reg_type, addr, field, value):
        """Handle register value changed signal."""
        try:
            self.usability_logger.log_event("ACTION", "RegisterEdit", f"Addr:{addr} Field:{field} Val:{value}")
        except Exception:
            pass
    
    def on_data_updated(self):
        """Handle data updated signal from refresher."""
        try:
            row = self.register_editor.currentIndex().row()
            self._update_format_editor_for_row(row)
        except Exception:
            pass

    def _on_show_all_logs_toggled(self, checked: bool):
        """Toggle between communication-only and full log output."""
        self.show_all_logs = bool(checked)
        status = "Show ALL Logs enabled" if checked else "Showing communication traffic only"
        self.append_to_log_widget(status, force=True)

    # -------- Format editor helpers --------
    def _get_current_entry(self, row_override: int = None):
        try:
            group = getattr(self.register_editor, 'current_reg_group', None)
            if not group or not isinstance(group, dict):
                return None, None, None
            reg_map = group.get('parent_slave_map')
            reg_type = group.get('reg_type')
            start_addr = int(group.get('start_addr', 0))
            size = int(group.get('size', 0))
            row = row_override if row_override is not None else self.register_editor.currentIndex().row()
            if row is None or row < 0:
                row = 0
            if row >= size or not reg_map:
                return None, None, None
            addr = start_addr + row
            entry = reg_map.get_register(reg_type, addr)
            return entry, reg_type, addr
        except Exception:
            return None, None, None

    def _format_all(self, value: int):
        v = int(value) & 0xFFFF
        signed = v - 0x10000 if v >= 0x8000 else v
        return {
            "Unsigned": str(v),
            "Signed": str(signed),
            "Hex": f"0x{v:04X}",
            "Binary": f"{v:016b}",
        }

    def _get_format_label(self, code: str) -> str:
        labels = {
            "Unsigned": self.tr("Unsigned"),
            "Signed": self.tr("Signed"),
            "Hex": self.tr("Hex"),
            "Binary": self.tr("Binary")
        }
        return labels.get(code, code)

    def _normalize_format_code(self, fmt: str) -> str:
        fmt_low = (fmt or '').strip().lower()
        mapping = {
            'unsigned': 'Unsigned',
            'signed': 'Signed',
            'hex': 'Hex',
            'binary': 'Binary',
            self.tr("Unsigned").lower(): 'Unsigned',
            self.tr("Signed").lower(): 'Signed',
            self.tr("Hex").lower(): 'Hex',
            self.tr("Binary").lower(): 'Binary'
        }
        return mapping.get(fmt_low, 'Unsigned')

    def _parse_by_format(self, text: str, fmt: str) -> int:
        s = (text or '').strip()
        fmt_l = (fmt or 'Unsigned').lower()
        if fmt_l == 'signed':
            n = int(s)
            if n < 0:
                n = (n + 0x10000) & 0xFFFF
            return n & 0xFFFF
        if fmt_l == 'hex':
            if s.lower().startswith('0x'):
                s = s[2:]
            return int(s, 16) & 0xFFFF
        if fmt_l == 'binary':
            if s.lower().startswith('0b'):
                s = s[2:]
            return int(s, 2) & 0xFFFF
        # default unsigned
        return int(s) & 0xFFFF

    def _clear_format_editor(self):
        if not hasattr(self, 'format_model') or self.format_model is None:
            return
        try:
            self.format_model.blockSignals(True)
            for row in range(self.format_model.rowCount()):
                item = self.format_model.item(row, 1)
                if item:
                    item.setText("")
        finally:
            try:
                self.format_model.blockSignals(False)
            except Exception:
                pass
        if hasattr(self, 'formatEditor') and self.formatEditor:
            try:
                self.formatEditor.viewport().update()
            except Exception:
                pass

    def _update_format_editor_for_row(self, row: int):
        if not hasattr(self, 'format_model') or self.format_model is None:
            return
        entry, _, _ = self._get_current_entry(row)
        if not entry:
            self._clear_format_editor()
            return
        values = self._format_all(entry.value)
        try:
            self.format_model.blockSignals(True)
            for r, key in enumerate(["Unsigned", "Signed", "Hex", "Binary"]):
                cell = self.format_model.item(r, 1)
                if cell is None:
                    cell = QStandardItem("")
                    self.format_model.setItem(r, 1, cell)
                cell.setText(values.get(key, ""))
        finally:
            try:
                self.format_model.blockSignals(False)
            except Exception:
                pass
        if hasattr(self, 'formatEditor') and self.formatEditor:
            try:
                self.formatEditor.viewport().update()
            except Exception:
                pass

    def _on_table_cell_changed(self, row: int, column: int, new_value: str):
        if column == 3:
            try:
                self._update_format_editor_for_row(row)
            except Exception:
                pass

    def _on_format_editor_item_changed(self, item: QStandardItem):
        if not item or item.column() != 1:
            return
        fmt_item = self.format_model.item(item.row(), 0) if hasattr(self, 'format_model') else None
        fmt_name = fmt_item.text() if fmt_item else "Unsigned"
        entry, reg_type, addr = self._get_current_entry()
        if not entry or not reg_type:
            self._clear_format_editor()
            return
        try:
            parsed = self._parse_by_format(item.text(), fmt_name)
        except Exception:
            # revert to previous value and alert user
            try:
                self.format_model.blockSignals(True)
                vmap = self._format_all(entry.value)
                item.setText(vmap.get(fmt_name, ""))
            finally:
                try:
                    self.format_model.blockSignals(False)
                except Exception:
                    pass
            return

        entry.value = parsed
        group = getattr(self.register_editor, 'current_reg_group', None)
        reg_map = group.get('parent_slave_map') if group else None
        if reg_map:
            try:
                from ..services.register_sync_service import get_register_sync_service
                sync_service = get_register_sync_service()
                sync_service.propagate_register_change(reg_type, addr, parsed, reg_map)
            except Exception:
                pass

        table_row = self.register_editor.currentIndex().row()
        if table_row is None or table_row < 0:
            table_row = 0
        display_index = self.register_editor.model.index(table_row, 4)
        display_type = self.register_editor.model.data(display_index, Qt.DisplayRole) or 'Unsigned'
        formatted = self.register_editor._format_value(parsed, display_type)
        try:
            value_index = self.register_editor.model.index(table_row, 3)
            self.register_editor.model.setData(value_index, formatted, Qt.EditRole)
        except Exception:
            pass
        self._update_format_editor_for_row(table_row)

    def _on_search_address(self):
        """Focus table row matching the entered address."""
        try:
            text = self.search_input.text().strip()
        except Exception:
            return
        if not text:
            return
        
        # Log the search action
        try:
            self.usability_logger.log_event("ACTION", "SearchBar", f"Search: {text}")
        except Exception:
            pass

        group = getattr(self.register_editor, 'current_reg_group', None)
        if not group or not isinstance(group, dict):
            if hasattr(self, 'statusbar') and self.statusbar:
                self.statusbar.showMessage("No register group selected", 3000)
            return
        reg_type = group.get('reg_type')
        start_addr = int(group.get('start_addr', 0))
        size = int(group.get('size', 0))
        try:
            target = RegisterValidator.display_to_address(text, reg_type)
        except Exception:
            try:
                target = int(text, 0)
            except Exception:
                if hasattr(self, 'statusbar') and self.statusbar:
                    self.statusbar.showMessage("Invalid address format", 3000)
                return
        row = target - start_addr
        if 0 <= row < size:
            self.register_editor.select_row(row)
            self.register_editor.setFocus(Qt.OtherFocusReason)
            self._update_format_editor_for_row(row)
            if hasattr(self, 'statusbar') and self.statusbar:
                self.statusbar.showMessage(f"Selected address {text}", 2000)
        else:
            if hasattr(self, 'statusbar') and self.statusbar:
                self.statusbar.showMessage("Address not in current group", 3000)
    
    def _on_address_mode_changed(self, new_mode: str):
        """Handle address mode changes - status and logging only."""
        try:
            self.usability_logger.log_event("ACTION", "AddressMode", f"Changed to: {new_mode}")
        except Exception:
            pass

        # Update status bar
        if new_mode == 'plc':
            mode_text = "PLC Format"
            # Disable protocol decimal option when in PLC mode
            if hasattr(self, 'protocol_decimal_checkbox'):
                self.protocol_decimal_checkbox.setEnabled(False)
        else:
            fmt = RegisterValidator.get_protocol_display_format()
            mode_text = "Protocol (Decimal)" if fmt == 'dec' else "Protocol (Hex)"
            # Enable protocol decimal option in protocol mode
            if hasattr(self, 'protocol_decimal_checkbox'):
                self.protocol_decimal_checkbox.setEnabled(True)
        if hasattr(self, 'statusbar') and self.statusbar:
            self.statusbar.showMessage(f"Address Mode: {mode_text}", 3000)
        
        # Log the change
        global_logger.info(f"Address display mode changed to: {mode_text}")
    
    def _refresh_tree_addresses(self, new_mode: str):
        """Refresh UI components when address mode changes (Option 2: Event-driven approach)."""
        # Update register table if visible
        if hasattr(self, 'register_editor') and self.register_editor.current_reg_group:
            self.register_editor.refresh_current_view()
        
        # Update tree view register group labels
        if hasattr(self, 'connection_manager'):
            self.connection_manager.refresh_register_group_addresses()

    def _on_protocol_decimal_toggled(self, checked: bool):
        """Handle toggling of protocol decimal display option."""
        try:
            # If PLC mode is active, ignore and reset checkbox to disabled
            if hasattr(self, 'address_mode_checkbox') and self.address_mode_checkbox.isChecked():
                # Should not be interactable anyway
                if hasattr(self, 'protocol_decimal_checkbox'):
                    self.protocol_decimal_checkbox.setChecked(False)
                return
            # Update validator setting
            RegisterValidator.set_protocol_display_format('dec' if checked else 'hex')
            # Update status message to reflect new protocol display
            fmt = 'Decimal' if checked else 'Hex'
            if hasattr(self, 'statusbar') and self.statusbar:
                self.statusbar.showMessage(f"Address Mode: Protocol ({fmt})", 3000)
            global_logger.info(f"Protocol address display set to: {fmt}")
            # Refresh UI components to reflect new display format
            self._refresh_tree_addresses('protocol')
            self._update_statusbar_info()
        except Exception:
            pass

    def _update_statusbar_info(self):
        """Refresh the group info and register counts in the status bar."""
        try:
            # Default texts
            group_text = self.tr("Group: —")
            regs_text = self.tr("Registers: 0")

            group = getattr(self.register_editor, 'current_reg_group', None)
            if group and isinstance(group, dict):
                reg_map = group.get('parent_slave_map')
                reg_type = group.get('reg_type')
                start_addr = int(group.get('start_addr', 0))
                size = int(group.get('size', 0))

                # Format display range using current address mode
                from ..services.register_validator import RegisterValidator
                start_disp = RegisterValidator.address_to_display(start_addr, reg_type)
                end_disp = RegisterValidator.address_to_display(start_addr + max(size - 1, 0), reg_type)

                # Best-effort group name: explicit name or friendly default by type
                name = (group.get('group_name') or '').strip()
                if not name:
                    friendly_defaults = {
                        'hr': 'Holding Registers',
                        'ir': 'Input Registers',
                        'di': 'Discrete Inputs',
                        'co': 'Digital Outputs',
                    }
                    name = friendly_defaults.get(reg_type, f"Group {group.get('register_id', '')}".strip())
                reg_type_up = (reg_type or '').upper()
                group_text = self.tr("Group: {} [{} {}:{}]").format(name, reg_type_up, start_disp, end_disp)

                # Count registers present in this group range
                try:
                    reg_dict = getattr(reg_map, reg_type) if reg_map and reg_type else {}
                    present = 0
                    for i in range(size):
                        addr = start_addr + i
                        if addr in reg_dict:
                            present += 1
                    # Show both present and declared size if they differ
                    if present != size:
                        regs_text = self.tr("Registers: {}/{}").format(present, size)
                    else:
                        regs_text = self.tr("Registers: {}").format(size)
                except Exception:
                    regs_text = self.tr("Registers: {}").format(size)

                # Total across the current slave's map
                try:
                    stats = reg_map.get_statistics() if reg_map else None
                    if stats:
                        total_text = self.tr("Total: {}").format(stats.get('total_count', 0))
                    else:
                        total_text = self.tr("Total: 0")
                except Exception:
                    total_text = self.tr("Total: 0")
            else:
                total_text = self.tr("Total: 0")

            # Apply to labels if available
            if hasattr(self, 'group_status_label'):
                self.group_status_label.setText(group_text)
            if hasattr(self, 'reg_count_status_label'):
                self.reg_count_status_label.setText(regs_text)
            if hasattr(self, 'total_regs_status_label'):
                self.total_regs_status_label.setText(total_text)
        except Exception:
            # Non-fatal; keep UI responsive
            pass
    
    def changeEvent(self, event):
        """Handle dynamic language switching."""
        if event.type() == QEvent.LanguageChange:
            self._retranslate_ui()
        super().changeEvent(event)

    def _retranslate_ui(self):
        """Update all UI text for the new language."""
        self.setWindowTitle(self.tr("ModbusX Multi-Instance Slave Demo"))
        
        # Managers
        if hasattr(self, 'connection_manager'):
            self.connection_manager.retranslate_ui()
        
        if hasattr(self, 'register_editor'):
            self.register_editor.retranslate_ui()
            
        # Status Bar
        self._update_statusbar_info()

        # Actions (tool/menu actions defined in UI)
        actions = {
            'actionDisconnect': self.tr("Disconnect"),
            'actionConnect': self.tr("Add Connection"),
            'actionOpenConnect': self.tr("Open Connection"),
            'actionCloseConnect': self.tr("Close Connection"),
            'actionAddSlave': self.tr("Add Slave"),
            'actionAddRegisterGroup': self.tr("Add Register Group"),
            'actionRunScript': self.tr("Run Script..."),
            'actionStopScript': self.tr("Stop Script"),
            'actionShowLogsPane': self.tr("Show Logs Pane"),
            'actionShowAllLogs': self.tr("Show ALL Logs"),
            'actionSaveConfiguration': self.tr("Save Configuration"),
            'actionSaveConfigurationAs': self.tr("Save Configuration As..."),
            'actionLoadConfiguration': self.tr("Load Configuration..."),
            'actionRedundancy_Check': self.tr("Redundancy Check")
        }
        
        for name, text in actions.items():
            if hasattr(self, name):
                getattr(self, name).setText(text)

        # Menus (use stable objectNames so we can switch both ways)
        def _set_menu_title(obj_name: str, text: str):
            menu = self.findChild(QMenu, obj_name)
            if menu:
                menu.setTitle(text)

        _set_menu_title('menuFile', self.tr('File'))
        _set_menu_title('menuEdit', self.tr('Edit'))
        _set_menu_title('menuConnection', self.tr('Connection'))
        _set_menu_title('menuScripts', self.tr('Scripts'))
        _set_menu_title('menuSetup', self.tr('Tools'))
        _set_menu_title('menuDisplay', self.tr('Display'))
        _set_menu_title('menuView', self.tr('View'))
        _set_menu_title('menuWindow', self.tr('Window'))
        _set_menu_title('menuHelp', self.tr('Help'))
        _set_menu_title('menuLanguage', self.tr('Language'))
        
        # Language submenu items (optional retranslate if present)
        lang_en = self.findChild(QAction, 'actionLanguageEnglish')
        if lang_en:
            lang_en.setText(self.tr("English"))
        lang_zh = self.findChild(QAction, 'actionLanguageChinese')
        if lang_zh:
            lang_zh.setText(self.tr("Chinese (中文)"))
        
        # Toolbar
        if hasattr(self, 'address_mode_checkbox'):
            self.address_mode_checkbox.setText(self.tr("PLC Address (Base 1)"))
            self.address_mode_checkbox.setToolTip(self.tr("Toggle between PLC addressing"))
            
        if hasattr(self, 'protocol_decimal_checkbox'):
            self.protocol_decimal_checkbox.setText(self.tr("Decimal (Protocol Address Only)"))
            self.protocol_decimal_checkbox.setToolTip(self.tr("Show protocol addresses in decimal instead of hex"))
        
        if hasattr(self, 'address_format_label'):
            self.address_format_label.setText(self.tr("Address Format:"))
            
        if hasattr(self, 'search_label'):
            self.search_label.setText(self.tr("Search Address:"))
            
        # Format Editor
        if hasattr(self, 'format_model'):
            self.format_model.setHorizontalHeaderLabels([self.tr("Format"), self.tr("Value")])
            codes = getattr(self, '_format_codes', ["Unsigned", "Signed", "Hex", "Binary"])
            for r, code in enumerate(codes):
                item = self.format_model.item(r, 0)
                if item:
                    item.setText(self._get_format_label(code))
                    item.setData(code, Qt.UserRole)
        if hasattr(self, 'tree_model'):
            try:
                self.tree_model.setHorizontalHeaderLabels([self.tr('Connections')])
            except Exception:
                pass
        self._update_save_config_action_label()

    def _on_language_changed(self, lang_code: str):
        """Ensure UI updates immediately after translator switches."""
        self._current_language_code = lang_code or self._current_language_code
        # Let Qt deliver LanguageChange, but also force a refresh to avoid any delay
        try:
            self._retranslate_ui()
        except Exception:
            pass

    def _find_connection_item(self, address_or_port, port_or_baudrate):
        """Find connection item in tree by address:port or serial_port@baudrate."""
        # Search through all connection items in the tree
        for i in range(self.tree_model.rowCount()):
            connection_item = self.tree_model.item(i, 0)
            if not connection_item:
                continue
                
            conn_info = connection_item.data(Qt.UserRole)
            if not conn_info:
                continue
            
            # Check if this is a TCP connection match
            if 'address' in conn_info and 'port' in conn_info:
                if (conn_info['address'] == address_or_port and 
                    conn_info['port'] == port_or_baudrate):
                    return connection_item
            
            # Check if this is a serial connection match (address_or_port = serial_port, port_or_baudrate = baudrate)
            elif 'serial_port' in conn_info and 'baudrate' in conn_info:
                if (conn_info['serial_port'] == address_or_port and 
                    conn_info['baudrate'] == port_or_baudrate):
                    return connection_item
        
        return None
