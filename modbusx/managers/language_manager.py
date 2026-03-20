from PyQt5.QtCore import QObject, QTranslator, QCoreApplication, QLocale, pyqtSignal
from modbusx.logger import get_logger
import xml.etree.ElementTree as ET
from pathlib import Path

class XmlTranslator(QTranslator):
    """
    Custom translator that loads .ts XML files directly.
    Useful when lrelease/qm files are not available.
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._translations = {}

    def load_ts(self, filepath):
        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
            for context in root.findall('context'):
                context_name = context.find('name').text
                for message in context.findall('message'):
                    source = message.find('source').text
                    translation = message.find('translation').text
                    if source and translation:
                        self._translations[(context_name, source)] = translation
            return True
        except Exception as e:
            print(f"XML Translator error: {e}")
            return False

    def translate(self, context, source_text, disambiguation=None, n=-1):
        key = (context, source_text)
        return self._translations.get(key, source_text)

class LanguageManager(QObject):
    """
    Manages application language switching (FR15, NFR11).
    """
    language_changed = pyqtSignal(str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.translator = QTranslator()
        self.xml_translator = None # Fallback
        self.logger = get_logger("LanguageManager")
        
    def load_language(self, lang_code: str):
        """
        Load a language file (e.g., 'zh_CN', 'en_US').
        """
        # Remove old translators
        self.app.removeTranslator(self.translator)
        if self.xml_translator:
            self.app.removeTranslator(self.xml_translator)
            self.xml_translator = None
        
        # Load new translator
        success = False
        if lang_code == 'en_US':
            self.logger.info("Switched to English (Default)")
            success = True
        else:
            # Try loading .qm file first
            qm_filename = f"modbusx_{lang_code}.qm"
            base_path = Path(__file__).resolve().parent.parent / "assets" / "translations"
            qm_path = base_path / qm_filename
            
            if qm_path.exists() and self.translator.load(str(qm_path)):
                self.app.installTranslator(self.translator)
                self.logger.info(f"Loaded QM translation: {qm_path}")
                success = True
            else:
                # Fallback: Try loading .ts file
                ts_filename = f"modbusx_{lang_code}.ts"
                ts_path = base_path / ts_filename
                
                if ts_path.exists():
                    self.xml_translator = XmlTranslator(self.app)
                    if self.xml_translator.load_ts(ts_path):
                        self.app.installTranslator(self.xml_translator)
                        self.logger.info(f"Loaded TS translation (fallback): {ts_path}")
                        success = True
        
        if success:
            self.language_changed.emit(lang_code)
        else:
            self.logger.warning(f"Failed to load translation for {lang_code}")
        
        return success
