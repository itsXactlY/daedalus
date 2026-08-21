import subprocess
import tempfile
import os
import sys

def validate_html_scripts(filepath):
    """Extract and validate JavaScript from an HTML file.
    
    Usage: python validate-js.py /path/to/trailer.html
    
    Returns: True if valid, False if syntax errors found.
    Prints filename and status for each file.
    """
    if not os.path.exists(filepath):
        print(f"SKIP {filepath} - not found")
        return False
    
    content = open(filepath).read()
    script_start = content.find('<script>') + 8
    script_end = content.find('</script>')
    
    if script_start < 8 or script_end < 0:
        print(f"SKIP {filepath} - no script tag")
        return False
    
    script_content = content[script_start:script_end]
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False) as f:
        f.write(script_content)
        temp_path = f.name
    
    try:
        result = subprocess.run(['node', '--check', temp_path], capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ {os.path.basename(filepath)}")
            return True
        else:
            print(f"✗ {os.path.basename(filepath)}:")
            print(f"  {result.stderr.strip()}")
            return False
    finally:
        os.unlink(temp_path)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python validate-js.py <html-file> [<html-file>...]")
        sys.exit(1)
    
    all_valid = True
    for filepath in sys.argv[1:]:
        if not validate_html_scripts(filepath):
            all_valid = False
    
    sys.exit(0 if all_valid else 1)