#!/usr/bin/env python3
"""
Test script for srsRAN GUI - validates code structure without requiring Tkinter
"""

import sys
import ast
import json
from pathlib import Path

def test_python_syntax():
    """Test that the main file has valid Python syntax"""
    print("Testing Python syntax...")
    with open('srsran_gui.py', 'r') as f:
        code = f.read()
    try:
        ast.parse(code)
        print("✓ Python syntax is valid")
        return True
    except SyntaxError as e:
        print(f"✗ Syntax error: {e}")
        return False

def test_imports():
    """Test that all required modules can be imported (except tkinter)"""
    print("\nTesting imports...")
    required_modules = [
        'subprocess',
        'threading',
        'os',
        'signal',
        'json',
        'pathlib'
    ]
    
    all_ok = True
    for module in required_modules:
        try:
            __import__(module)
            print(f"✓ {module} is available")
        except ImportError:
            print(f"✗ {module} is not available")
            all_ok = False
    
    return all_ok

def test_class_structure():
    """Test that the main class has expected methods"""
    print("\nTesting class structure...")
    with open('srsran_gui.py', 'r') as f:
        tree = ast.parse(f.read())
    
    # Find the SrsRANGUI class
    srsran_class = None
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == 'SrsRANGUI':
            srsran_class = node
            break
    
    if not srsran_class:
        print("✗ SrsRANGUI class not found")
        return False
    
    print("✓ SrsRANGUI class found")
    
    # Check for essential methods
    expected_methods = [
        '__init__',
        'setup_ui',
        'start_component',
        'stop_component',
        'start_all',
        'stop_all',
        'load_config',
        'save_config',
        'log',
        'update_status'
    ]
    
    methods = [node.name for node in srsran_class.body if isinstance(node, ast.FunctionDef)]
    
    all_ok = True
    for method in expected_methods:
        if method in methods:
            print(f"✓ Method {method} exists")
        else:
            print(f"✗ Method {method} is missing")
            all_ok = False
    
    return all_ok

def test_config_structure():
    """Test configuration structure"""
    print("\nTesting configuration structure...")
    
    # Check that default config has expected keys
    with open('srsran_gui.py', 'r') as f:
        content = f.read()
    
    expected_config_keys = [
        'epc_binary',
        'enb_binary',
        'ue_binary',
        'epc_config',
        'enb_config',
        'ue_config',
        'working_dir'
    ]
    
    all_ok = True
    for key in expected_config_keys:
        if f"'{key}'" in content:
            print(f"✓ Config key '{key}' found")
        else:
            print(f"✗ Config key '{key}' not found")
            all_ok = False
    
    return all_ok

def test_documentation():
    """Test that README exists and has content"""
    print("\nTesting documentation...")
    
    readme = Path('README.md')
    if not readme.exists():
        print("✗ README.md not found")
        return False
    
    print("✓ README.md exists")
    
    content = readme.read_text()
    
    # Check for essential sections
    sections = [
        'Overview',
        'Features',
        'Installation',
        'Usage',
        'Configuration'
    ]
    
    all_ok = True
    for section in sections:
        if section in content:
            print(f"✓ README section '{section}' found")
        else:
            print(f"✗ README section '{section}' not found")
            all_ok = False
    
    return all_ok

def test_requirements():
    """Test that requirements.txt exists"""
    print("\nTesting requirements file...")
    
    req_file = Path('requirements.txt')
    if not req_file.exists():
        print("✗ requirements.txt not found")
        return False
    
    print("✓ requirements.txt exists")
    content = req_file.read_text()
    print(f"  Contains: {content.strip()}")
    
    return True

def test_gitignore():
    """Test that .gitignore exists"""
    print("\nTesting .gitignore...")
    
    gitignore = Path('.gitignore')
    if not gitignore.exists():
        print("✗ .gitignore not found")
        return False
    
    print("✓ .gitignore exists")
    
    content = gitignore.read_text()
    
    # Check for Python-specific ignores
    expected_patterns = ['__pycache__', '*.pyc', 'venv', '.env']
    all_ok = True
    
    for pattern in expected_patterns:
        if pattern in content:
            print(f"✓ Pattern '{pattern}' found in .gitignore")
        else:
            print(f"✗ Pattern '{pattern}' not found in .gitignore")
            all_ok = False
    
    return all_ok

def main():
    """Run all tests"""
    print("=" * 60)
    print("srsRAN GUI Test Suite")
    print("=" * 60)
    
    results = []
    
    results.append(("Python Syntax", test_python_syntax()))
    results.append(("Imports", test_imports()))
    results.append(("Class Structure", test_class_structure()))
    results.append(("Configuration", test_config_structure()))
    results.append(("Documentation", test_documentation()))
    results.append(("Requirements", test_requirements()))
    results.append((".gitignore", test_gitignore()))
    
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {test_name}: {status}")
    
    all_passed = all(result for _, result in results)
    
    print("=" * 60)
    if all_passed:
        print("All tests passed! ✓")
        return 0
    else:
        print("Some tests failed. ✗")
        return 1

if __name__ == '__main__':
    sys.exit(main())
