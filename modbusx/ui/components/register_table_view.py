"""
Register Table View Component

Enhanced UI component for displaying and editing registers with business logic integration.
"""

from PyQt5.QtWidgets import (
    QTableView, QStyledItemDelegate, QComboBox, QSpinBox, QHeaderView,
    QMenu
)
from PyQt5.QtGui import QValidator, QColor
from PyQt5.QtCore import (
    Qt, pyqtSignal, QEvent, QItemSelectionModel, QAbstractTableModel, QModelIndex,
    QCoreApplication
)
from ...services.register_validator import MODBUS_REGISTER_TYPES, RegisterValidator
from typing import Optional, Dict, List, Any

REGISTER_TYPE_PREFIX = {
    'HR': '4x',
    'IR': '3x',
    'CO': '0x',
    'DI': '1x',
}
PREFIX_TO_REGTYPE = {prefix.upper(): key.lower() for key, prefix in REGISTER_TYPE_PREFIX.items()}
TYPE_COLOR_MAP = {
    'unsigned': QColor(255, 226, 226),
    'signed': QColor(238, 224, 255),
    'hex': QColor(220, 236, 255),
    'binary': QColor(222, 255, 222),
}


class RegisterValueSpinBox(QSpinBox):
    """Spin box that supports multiple display formats for register values."""

    def __init__(self, display_format: str, parent=None):
        super().__init__(parent)
        self.display_format = display_format or 'Unsigned'
        self.setAccelerated(True)
        self.setKeyboardTracking(False)
        fmt = self.display_format.lower()
        if fmt == 'signed':
            self.setRange(-32768, 32767)
        else:
            self.setRange(0, 0xFFFF)

    def textFromValue(self, value: int) -> str:
        fmt = self.display_format.lower()
        if fmt == 'signed':
            return str(value)
        if fmt == 'hex':
            return f"0x{(value & 0xFFFF):04X}"
        if fmt == 'binary':
            return f"{(value & 0xFFFF):016b}"
        return str(value & 0xFFFF)

    def _parse_text(self, text: str) -> int:
        s = (text or '').strip()
        if not s:
            raise ValueError
        fmt = self.display_format.lower()
        if fmt == 'signed':
            return int(s, 10)
        if fmt == 'hex':
            if s.lower().startswith('0x'):
                s = s[2:]
            if not s:
                raise ValueError
            return int(s, 16)
        if fmt == 'binary':
            if s.lower().startswith('0b'):
                s = s[2:]
            if not s or any(ch not in '01' for ch in s):
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
        fmt = self.display_format.lower()
        if not stripped or stripped in ('0x', '0X', '0b', '0B'):
            return (QValidator.Intermediate, text, pos)
        if fmt == 'signed' and stripped in ('-', '+'):
            return (QValidator.Intermediate, text, pos)
        if fmt == 'hex' and stripped.lower() in ('0x-', '0x+'):
            return (QValidator.Intermediate, text, pos)
        if fmt == 'binary' and stripped.lower() == '0b':
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

class RegisterDisplayMixin:
    """Shared formatting helpers for register table components."""

    def _normalize_display_type(self, fmt: str) -> str:
        fmt_low = (fmt or 'Unsigned').strip().lower()
        mapping = {
            'unsigned': 'Unsigned',
            'signed': 'Signed',
            'hex': 'Hex',
            'binary': 'Binary',
        }
        # Also accept localized labels from known contexts
        for ctx in ('RegisterTableView', 'RegisterTableDelegate', 'MainWindow'):
            mapping[QCoreApplication.translate(ctx, 'Unsigned').lower()] = 'Unsigned'
            mapping[QCoreApplication.translate(ctx, 'Signed').lower()] = 'Signed'
            mapping[QCoreApplication.translate(ctx, 'Hex').lower()] = 'Hex'
            mapping[QCoreApplication.translate(ctx, 'Binary').lower()] = 'Binary'
        return mapping.get(fmt_low, 'Unsigned')

    def _get_display_label(self, code: str) -> str:
        mapping = {
            'Unsigned': QCoreApplication.translate('RegisterTableView', 'Unsigned'),
            'Signed': QCoreApplication.translate('RegisterTableView', 'Signed'),
            'Hex': QCoreApplication.translate('RegisterTableView', 'Hex'),
            'Binary': QCoreApplication.translate('RegisterTableView', 'Binary'),
        }
        return mapping.get(code, code)

    def _format_value(self, value: int, fmt: str) -> str:
        try:
            v = int(value) & 0xFFFF
        except Exception:
            v = 0
        fmt_l = self._normalize_display_type(fmt).lower()
        if fmt_l == 'signed':
            if v >= 0x8000:
                v -= 0x10000
            return str(v)
        if fmt_l == 'hex':
            return f"0x{v:04X}"
        if fmt_l == 'binary':
            return f"{v:016b}"
        return str(v)

    def _parse_value(self, text: str, fmt: str) -> int:
        fmt_l = self._normalize_display_type(fmt).lower()
        s = (text or '').strip()

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
        return int(s) & 0xFFFF

    def _format_reg_type_label(self, reg_type_upper: str) -> str:
        reg_type_upper = (reg_type_upper or '').upper()
        prefix = REGISTER_TYPE_PREFIX.get(reg_type_upper, reg_type_upper)
        info = MODBUS_REGISTER_TYPES.get(reg_type_upper, {})
        name = info.get('name') or info.get('description') or ''
        translated = QCoreApplication.translate('RegisterTableView', name) if name else ''
        label = translated or name or ''
        return f"{prefix} {label}".strip()


class RegisterTableModel(RegisterDisplayMixin, QAbstractTableModel):
    """Lightweight table model that virtualizes register rows."""

    register_updated = pyqtSignal(str, int, str, object)
    cell_edited = pyqtSignal(int, int, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._headers = [
            QCoreApplication.translate("RegisterTableView", "Register Type"),
            QCoreApplication.translate("RegisterTableView", "Address"),
            QCoreApplication.translate("RegisterTableView", "Alias"),
            QCoreApplication.translate("RegisterTableView", "Value"),
            QCoreApplication.translate("RegisterTableView", "Type"),
            QCoreApplication.translate("RegisterTableView", "Comment"),
        ]
        self._entries: List[Any] = []
        self._reg_group: Optional[Dict] = None
        self._reg_type: Optional[str] = None

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._entries)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._headers)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if orientation == Qt.Horizontal and role == Qt.DisplayRole:
            if 0 <= section < len(self._headers):
                return self._headers[section]
        return super().headerData(section, orientation, role)

    def set_register_group(self, reg_group: Optional[Dict]):
        """Bind the model to a new register group."""
        self.beginResetModel()
        self._entries = []
        self._reg_group = None
        self._reg_type = None
        if isinstance(reg_group, dict):
            reg_map = reg_group.get('parent_slave_map')
            reg_type = reg_group.get('reg_type')
            start_addr = reg_group.get('start_addr')
            size = reg_group.get('size')
            if reg_map and reg_type is not None and start_addr is not None and size is not None:
                entries = [
                    e for e in reg_map.all_entries(reg_type)
                    if start_addr <= e.addr < start_addr + size
                ]
                entries.sort(key=lambda entry: entry.addr)
                self._entries = entries
                self._reg_group = reg_group
                self._reg_type = reg_type
        self.endResetModel()

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        row = index.row()
        column = index.column()
        if not (0 <= row < len(self._entries)):
            return None
        entry = self._entries[row]
        reg_type_upper = entry.reg_type.upper()
        display_type = self._get_entry_display_type(entry)

        if role == Qt.DisplayRole or role == Qt.EditRole:
            if column == 0:
                return self._format_reg_type_label(reg_type_upper)
            if column == 1:
                return RegisterValidator.address_to_display(entry.addr, entry.reg_type)
            if column == 2:
                return entry.alias
            if column == 3:
                return self._format_value(entry.value, display_type)
            if column == 4:
                return self._get_display_label(display_type)
            if column == 5:
                return entry.comment
        elif role == Qt.BackgroundRole and column == 4:
            return TYPE_COLOR_MAP.get(display_type.lower())
        elif role == Qt.UserRole:
            if column == 0:
                return entry.reg_type.lower()
            if column == 1:
                return entry.addr
            if column == 3:
                return int(entry.value)
            if column == 4:
                return display_type
        return None

    def flags(self, index: QModelIndex):
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return Qt.NoItemFlags
        column = index.column()
        base = Qt.ItemIsEnabled | Qt.ItemIsSelectable
        if column in (2, 3, 4, 5):
            base |= Qt.ItemIsEditable
        return base

    def setData(self, index: QModelIndex, value, role: int = Qt.EditRole):
        if role not in (Qt.EditRole, Qt.DisplayRole):
            return False
        if not index.isValid() or not (0 <= index.row() < len(self._entries)):
            return False

        entry = self._entries[index.row()]
        column = index.column()
        reg_type = entry.reg_type.lower()
        text_value = str(value) if value is not None else ""
        updated = False

        if column == 2:  # Alias
            entry.alias = text_value
            updated = True
            field = 'alias'
        elif column == 5:  # Comment
            entry.comment = text_value
            updated = True
            field = 'comment'
        elif column == 4:  # Display type
            canonical = self._normalize_display_type(text_value)
            setattr(entry, 'display_type', canonical)
            updated = True
            field = 'type'
            text_value = canonical
            self.dataChanged.emit(
                self.index(index.row(), 3), self.index(index.row(), 4),
                [Qt.DisplayRole, Qt.EditRole]
            )
        elif column == 3:  # Value
            display_type = self._get_entry_display_type(entry)
            try:
                parsed = self._parse_value(text_value, display_type)
                RegisterValidator.validate_register_value(parsed, reg_type)
            except Exception:
                return False
            entry.value = parsed
            updated = True
            field = 'value'
            self._propagate_register_change(reg_type, entry.addr, parsed)
        else:
            return False

        if updated:
            self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
            display_text = self.data(index, Qt.DisplayRole)
            self.cell_edited.emit(index.row(), column, str(display_text))
            self.register_updated.emit(reg_type, entry.addr, field, text_value)
        return updated

    def _propagate_register_change(self, reg_type: str, addr: int, value: int):
        """Forward register updates to the sync service if available."""
        try:
            from ...services.register_sync_service import get_register_sync_service

            reg_map = self._reg_group.get('parent_slave_map') if self._reg_group else None
            if not reg_map:
                return
            sync_service = get_register_sync_service()
            sync_service.propagate_register_change(reg_type, addr, value, reg_map)
        except Exception:
            pass

    def _get_entry_display_type(self, entry) -> str:
        display_type = getattr(entry, 'display_type', 'Unsigned')
        return self._normalize_display_type(display_type)

    def get_row_reg_type(self, row: int) -> str:
        if 0 <= row < len(self._entries):
            return self._entries[row].reg_type.lower()
        return ''

    def get_row_display_type(self, row: int) -> str:
        if 0 <= row < len(self._entries):
            return self._get_entry_display_type(self._entries[row])
        return 'Unsigned'

    def refresh_display(self):
        """Request a repaint of currently bound data."""
        if not self._entries:
            return
        top_left = self.index(0, 0)
        bottom_right = self.index(len(self._entries) - 1, len(self._headers) - 1)
        self.dataChanged.emit(top_left, bottom_right, [Qt.DisplayRole])

    def set_row_display_type(self, row: int, new_type: str):
        if not (0 <= row < len(self._entries)):
            return
        entry = self._entries[row]
        canonical = self._normalize_display_type(new_type)
        setattr(entry, 'display_type', canonical)
        idx_value = self.index(row, 3)
        idx_type = self.index(row, 4)
        self.dataChanged.emit(idx_value, idx_type, [Qt.DisplayRole, Qt.EditRole])
        reg_type = entry.reg_type.lower()
        self.register_updated.emit(reg_type, entry.addr, 'type', canonical)
        display_label = self._get_display_label(canonical)
        self.cell_edited.emit(row, 4, display_label)

    def update_headers(self):
        """Refresh header translations."""
        self._headers = [
            QCoreApplication.translate("RegisterTableView", "Register Type"),
            QCoreApplication.translate("RegisterTableView", "Address"),
            QCoreApplication.translate("RegisterTableView", "Alias"),
            QCoreApplication.translate("RegisterTableView", "Value"),
            QCoreApplication.translate("RegisterTableView", "Type"),
            QCoreApplication.translate("RegisterTableView", "Comment"),
        ]
        self.headerDataChanged.emit(Qt.Horizontal, 0, len(self._headers) - 1)

    def clear(self):
        self.set_register_group(None)

    def current_group(self) -> Optional[Dict]:
        return self._reg_group


class RegisterTableView(RegisterDisplayMixin, QTableView):
    """Enhanced register table component with business logic integration."""

    # UI signals
    cell_changed = pyqtSignal(int, int, str)  # row, column, new_value
    row_selected = pyqtSignal(int)            # row
    context_menu_requested = pyqtSignal(int, object)  # row, position

    # Business logic compatibility signal
    register_changed = pyqtSignal(str, int, str, object)  # reg_type, addr, field, value
    
    def __init__(self, parent=None):
        super().__init__(parent)

        # Business logic properties
        self.current_reg_group: Optional[Dict] = None

        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Setup the UI components."""
        self.model = RegisterTableModel(self)
        self.setModel(self.model)
        self.model.cell_edited.connect(self.cell_changed.emit)
        self.model.register_updated.connect(self.register_changed.emit)
        
        self.delegate = RegisterTableDelegate(self)
        self.setItemDelegate(self.delegate)
        
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setAlternatingRowColors(True)
        self.setVerticalScrollMode(QTableView.ScrollPerPixel)
        
        header = self.horizontalHeader()
        try:
            for col in range(self.model.columnCount()):
                header.setSectionResizeMode(col, QHeaderView.Interactive)
        except Exception:
            header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)
        try:
            header.setSectionResizeMode(2, QHeaderView.Stretch)
        except Exception:
            pass
        self._apply_default_column_widths()
        # Pastel selection color for a softer highlight
        self.setStyleSheet("""
            QTableView::item:selected {
                background-color: #a6d7f5;
                color: #000000;
            }
        """)
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)

    def _format_reg_type_label(self, reg_type_upper: str) -> str:
        reg_type_upper = (reg_type_upper or '').upper()
        prefix = REGISTER_TYPE_PREFIX.get(reg_type_upper, reg_type_upper)
        info = MODBUS_REGISTER_TYPES.get(reg_type_upper, {})
        name = info.get('name') or info.get('description') or ''
        translated = QCoreApplication.translate('RegisterTableView', name) if name else ''
        label = translated or name or ''
        return f"{prefix} {label}".strip()

    def _connect_signals(self):
        """Connect internal UI signals."""
        selection_model = self.selectionModel()
        if selection_model:
            selection_model.currentRowChanged.connect(self._on_row_changed)
        self.customContextMenuRequested.connect(self._on_context_menu)

    
    def clear_table(self):
        """Clear all table contents."""
        self.model.clear()
    
    def get_row_count(self) -> int:
        """Get number of rows in table."""
        return self.model.rowCount()
    
    def select_row(self, row: int):
        """Select a specific row."""
        if 0 <= row < self.model.rowCount():
            index = self.model.index(row, 0)
            selection_model = self.selectionModel()
            if selection_model:
                selection_model.setCurrentIndex(
                    index, QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows
                )
            try:
                self.scrollTo(index, QTableView.PositionAtCenter)
            except Exception:
                self.scrollTo(index)
            self.setFocus(Qt.OtherFocusReason)
    
    def _get_cell_value(self, row: int, column: int) -> str:
        """Get value from a specific cell."""
        if not (0 <= row < self.model.rowCount()):
            return ""
        index = self.model.index(row, column)
        value = self.model.data(index, Qt.DisplayRole)
        return value if value is not None else ""
    
    def _on_row_changed(self, current, previous):
        """Handle row selection change."""
        if current.isValid():
            self.row_selected.emit(current.row())
    
    def _on_context_menu(self, position):
        """Handle context menu request and show format options directly."""
        index = self.indexAt(position)
        if not index.isValid():
            return
        row = index.row()
        self.context_menu_requested.emit(row, position)
        menu = QMenu(self)
        # Use translated options
        from PyQt5.QtCore import QCoreApplication as QCApp
        options = [
            QCApp.translate("MainWindow", "Unsigned"),
            QCApp.translate("MainWindow", "Signed"),
            QCApp.translate("MainWindow", "Hex"),
            QCApp.translate("MainWindow", "Binary"),
        ]
        current = self.model.data(self.model.index(row, 4), Qt.DisplayRole) or QCApp.translate("MainWindow", "Unsigned")
        for opt in options:
            act = menu.addAction(opt)
            act.setCheckable(True)
            act.setChecked(opt.lower() == current.lower())
            act.triggered.connect(lambda checked, o=opt: self._apply_row_format(row, o))
        menu.exec_(self.viewport().mapToGlobal(position))

    def _apply_row_format(self, row: int, new_type: str):
        if 0 <= row < self.model.rowCount():
            self.model.set_row_display_type(row, new_type)

    def refresh_address_display(self):
        """Refresh address display to show addresses in the current format."""
        self.model.refresh_display()

    # ===== BUSINESS LOGIC METHODS (migrated from RegisterEditorAdapter) =====

    def retranslate_ui(self):
        """Update UI strings for language change."""
        self.model.update_headers()
        self.model.refresh_display()
        if self.current_reg_group:
            self.populate_table_from_group()

    def set_current_register_group(self, reg_group: Optional[Dict]):
        """Set the current register group being edited."""
        self.current_reg_group = reg_group
        self.populate_table_from_group()

    def populate_table_from_group(self):
        """Populate the table with register entries from current group."""
        if not self.current_reg_group or not isinstance(self.current_reg_group, dict):
            self.clear_table()
            return

        if "parent_slave_map" not in self.current_reg_group:
            self.clear_table()
            return

        self.model.set_register_group(self.current_reg_group)
        self._apply_default_column_widths()

    def _apply_default_column_widths(self):
        """Apply consistent column widths for all tables."""
        widths = {
            0: 175,  # Register Type
            1: 120,  # Address
            2: 140,  # Alias (base width, stretches)
            3: 140,  # Value
            4: 105,  # Type
            5: 190,  # Comment
        }
        for col, width in widths.items():
            try:
                self.setColumnWidth(col, width)
            except Exception:
                continue

    def _get_row_reg_type_code(self, row: int) -> str:
        if hasattr(self.model, 'get_row_reg_type'):
            return self.model.get_row_reg_type(row)
        return ''

    # Legacy helper methods removed in favor of RegisterTableModel handling logic.

    def refresh_current_view(self):
        """Refresh the current register group view."""
        if self.current_reg_group:
            self.populate_table_from_group()

    def connect_address_mode_signals(self, address_mode_manager):
        """Connect to address mode change signals."""
        if hasattr(address_mode_manager, 'mode_changed'):
            address_mode_manager.mode_changed.connect(self._on_address_mode_changed)

    def _on_address_mode_changed(self, new_mode: str):
        """Handle address mode changes by refreshing display."""
        self._refresh_address_display()

    def _refresh_address_display(self):
        """Refresh address column based on current address mode."""
        if not self.current_reg_group:
            return
        self.model.refresh_display()


class RegisterTableDelegate(QStyledItemDelegate):
    """Custom delegate for register table editing."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
    
    def createEditor(self, parent, option, index):
        if index.column() == 0:  # Register Type column
            editor = QComboBox(parent)
            for reg_type, info in MODBUS_REGISTER_TYPES.items():
                # We need to access self.tr here, but this class inherits QStyledItemDelegate
                # which inherits QObject, so self.tr() is available.
                editor.addItem(f"{reg_type} - {info['name']}", reg_type.lower())
            return editor
        elif index.column() == 3:  # Value column
            model = index.model()
            fmt_index = model.index(index.row(), 4)
            table = self.parent()
            fmt_code = fmt_index.data(Qt.UserRole) if fmt_index.isValid() else None
            fmt_label = fmt_index.data() if fmt_index.isValid() else ''
            if isinstance(fmt_code, str):
                fmt_name = fmt_code.capitalize()
            elif table and hasattr(table, '_normalize_display_type'):
                fmt_name = table._normalize_display_type(fmt_label)
            else:
                fmt_name = 'Unsigned'
            editor = RegisterValueSpinBox(fmt_name, parent)
            editor.installEventFilter(self)
            editor.editingFinished.connect(lambda ed=editor: self.commitData.emit(ed))
            editor.editingFinished.connect(lambda ed=editor: self.closeEditor.emit(ed, QStyledItemDelegate.NoHint))
            return editor
        elif index.column() == 4:  # Type column
            editor = QComboBox(parent)
            for opt in [self.tr("Unsigned"), self.tr("Signed"), self.tr("Hex"), self.tr("Binary")]:
                editor.addItem(opt)
            return editor
        return super().createEditor(parent, option, index)
    
    def setEditorData(self, editor, index):
        if index.column() == 0 and isinstance(editor, QComboBox):
            table = self.parent()
            reg_code = table._get_row_reg_type_code(index.row()) if table else None
            if reg_code:
                idx = editor.findData(reg_code)
                if idx >= 0:
                    editor.setCurrentIndex(idx)
                    return
            current_text = index.model().data(index, Qt.EditRole) or ""
            base = current_text.split()[0]
            for i in range(editor.count()):
                if editor.itemText(i).startswith(base):
                    editor.setCurrentIndex(i)
                    break
        elif index.column() == 3 and isinstance(editor, RegisterValueSpinBox):
            table = self.parent()
            fmt = editor.display_format.lower()
            value = index.model().data(index, Qt.EditRole) or "0"
            try:
                parsed = table._parse_value(value, fmt) if hasattr(table, '_parse_value') else int(value, 0)
            except Exception:
                parsed = 0
            if fmt == 'signed':
                signed = parsed if parsed <= 0x7FFF else parsed - 0x10000
                editor.setValue(max(-32768, min(32767, signed)))
            else:
                editor.setValue(parsed & 0xFFFF)
        elif index.column() == 4 and isinstance(editor, QComboBox):
            current = index.model().data(index, Qt.EditRole)
            if current:
                idx = editor.findText(current)
                if idx >= 0:
                    editor.setCurrentIndex(idx)
        else:
            super().setEditorData(editor, index)
    
    def setModelData(self, editor, model, index):
        if index.column() == 3 and isinstance(editor, RegisterValueSpinBox):
            table = self.parent()
            fmt = editor.display_format.lower()
            try:
                editor.interpretText()
            except Exception:
                pass
            raw = editor.value()
            stored = raw & 0xFFFF
            display_value = table._format_value(stored, editor.display_format) if table else str(stored)
            model.setData(index, display_value, Qt.EditRole)
        elif index.column() == 4 and isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.EditRole)
        else:
            super().setModelData(editor, model, index)

    def eventFilter(self, editor, event):
        if isinstance(editor, RegisterValueSpinBox) and event.type() == QEvent.FocusOut:
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QStyledItemDelegate.NoHint)
        return super().eventFilter(editor, event)
