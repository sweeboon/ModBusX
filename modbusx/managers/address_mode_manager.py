"""
Address Mode Manager

Manages address mode changes and UI updates for register display formatting.
Provides centralized control for switching between PLC and Protocol addressing modes.
"""

from PyQt5.QtCore import QObject, pyqtSignal
from ..services.register_validator import RegisterValidator
from typing import Optional


class AddressModeManager(QObject):
    """Manages address mode changes and UI updates."""
    
    # Signals
    mode_changed = pyqtSignal(str)  # 'plc' or 'protocol'
    refresh_requested = pyqtSignal()  # Request UI refresh
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_mode = RegisterValidator.get_address_mode()
        self._connected_components = []
    
    def toggle_address_mode(self, is_plc_mode: bool):
        """
        Toggle between PLC and Protocol addressing.
        
        Args:
            is_plc_mode: True for PLC mode (400001), False for Protocol mode (0x0000)
        """
        new_mode = 'plc' if is_plc_mode else 'protocol'
        if new_mode != self.current_mode:
            self.current_mode = new_mode
            RegisterValidator.set_address_mode(new_mode)
            
            # Emit signals to update UI
            self.mode_changed.emit(new_mode)
            self.refresh_requested.emit()
    
    def get_current_mode(self) -> str:
        """Get the current address mode."""
        return self.current_mode
    
    def get_current_mode_display_name(self) -> str:
        """Get human-readable name for current mode."""
        return "PLC Address (Base 1)" if self.current_mode == 'plc' else "Protocol Address (Base 0)"
    
    def is_plc_mode(self) -> bool:
        """Check if currently in PLC addressing mode."""
        return self.current_mode == 'plc'
    
    def get_mode_description(self, mode: Optional[str] = None) -> str:
        """
        Get description of addressing mode.
        
        Args:
            mode: Mode to describe ('plc' or 'protocol'). If None, uses current mode.
            
        Returns:
            Human-readable description of the addressing mode
        """
        target_mode = mode or self.current_mode
        
        if target_mode == 'plc':
            return "6-digit PLC addressing format (e.g., HR: 400001-465536, IR: 300001-365536)"
        else:
            return "Hexadecimal protocol addressing format (e.g., 0x0000-0xFFFF)"
    
    def get_example_addresses(self, mode: Optional[str] = None) -> dict:
        """
        Get example addresses for each register type in specified mode.
        
        Args:
            mode: Mode for examples ('plc' or 'protocol'). If None, uses current mode.
            
        Returns:
            Dictionary with register types as keys and example addresses as values
        """
        target_mode = mode or self.current_mode
        
        if target_mode == 'plc':
            return {
                'HR': '400001',
                'IR': '300001', 
                'CO': '000001',
                'DI': '100001'
            }
        else:
            return {
                'HR': '0x0000',
                'IR': '0x0000',
                'CO': '0x0000', 
                'DI': '0x0000'
            }
    
    def connect_component(self, component):
        """
        Connect a UI component to receive address mode updates.
        Component should have a method called 'refresh_address_display' or similar.
        """
        if hasattr(component, 'refresh_address_display'):
            self.refresh_requested.connect(component.refresh_address_display)
            self._connected_components.append(component)
        elif hasattr(component, '_on_address_mode_changed'):
            self.mode_changed.connect(component._on_address_mode_changed)
            self._connected_components.append(component)
    
    def disconnect_component(self, component):
        """Disconnect a UI component from address mode updates."""
        if component in self._connected_components:
            try:
                if hasattr(component, 'refresh_address_display'):
                    self.refresh_requested.disconnect(component.refresh_address_display)
                if hasattr(component, '_on_address_mode_changed'):
                    self.mode_changed.disconnect(component._on_address_mode_changed)
            except TypeError:
                # Connection may not exist
                pass
            
            self._connected_components.remove(component)
    
    def disconnect_all_components(self):
        """Disconnect all connected components."""
        for component in self._connected_components.copy():
            self.disconnect_component(component)