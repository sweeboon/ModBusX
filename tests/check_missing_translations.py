import os
import re
import xml.etree.ElementTree as ET

def find_tr_strings(root_dir):
    # Match self.tr("...") and self.tr('...')
    # Use re.DOTALL to match newlines if necessary, but typically tr("...") is single line in code usually
    # unless using triple quotes.
    # Simple regex for now.
    tr_pattern = re.compile(r'self\.tr\(\s*["\'](.*?)["\']\s*\)')
    found_strings = set()
    
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    matches = tr_pattern.findall(content)
                    for match in matches:
                        # Unescape \n
                        s = match.replace(r'\n', '\n')
                        found_strings.add(s)
    return found_strings

def find_ui_strings(root_dir):
    ui_strings = set()
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.ui'):
                path = os.path.join(root, file)
                try:
                    tree = ET.parse(path)
                    for elem in tree.iter('string'):
                        if elem.text and elem.text.strip():
                            ui_strings.add(elem.text)
                except Exception as e:
                    print(f"Error parsing UI file {path}: {e}")
    return ui_strings

def load_existing_translations(ts_path):
    existing_strings = set()
    if not os.path.exists(ts_path):
        return existing_strings
        
    try:
        tree = ET.parse(ts_path)
        root = tree.getroot()
        for context in root.findall('context'):
            for message in context.findall('message'):
                source = message.find('source')
                if source is not None and source.text:
                    existing_strings.add(source.text)
    except Exception as e:
        print(f"Error parsing TS file: {e}")
        
    return existing_strings

if __name__ == '__main__':
    root_dir = 'modbusx'
    ts_path = 'modbusx/assets/translations/modbusx_zh_CN.ts'
    
    code_strings = find_tr_strings(root_dir)
    ui_strings = find_ui_strings(root_dir)
    all_source_strings = code_strings.union(ui_strings)
    
    existing_strings = load_existing_translations(ts_path)
    
    # Filter out empty strings
    all_source_strings = {s for s in all_source_strings if s.strip()}
    
    missing = all_source_strings - existing_strings
    
    print(f"Found {len(code_strings)} strings in code.")
    print(f"Found {len(ui_strings)} strings in UI files.")
    print(f"Total unique source strings: {len(all_source_strings)}")
    print(f"Found {len(existing_strings)} strings in TS file.")
    print(f"Missing {len(missing)} strings.")
    
    # Dump missing strings to a file for easier processing
    with open('missing_strings.txt', 'w', encoding='utf-8') as f:
        for s in sorted(list(missing)):
            f.write(f"{s}\n")
    
    print("Missing strings written to missing_strings.txt")