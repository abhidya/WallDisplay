import re

def check_balance(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    script_match = re.search(r'<script>(.*?)</script>', content, re.DOTALL)
    if not script_match:
        print("No script found")
        return
        
    script = script_match.group(1)
    
    lines = script.split('\n')
    
    single_quote = False
    double_quote = False
    backtick = False
    
    for i, line in enumerate(lines):
        line_num = 1060 + i
        escaped = False
        for char in line:
            if escaped:
                escaped = False
                continue
            if char == '\\':
                escaped = True
                continue
                
            if char == "'" and not double_quote and not backtick: single_quote = not single_quote
            elif char == '"' and not single_quote and not backtick: double_quote = not double_quote
            elif char == '`' and not single_quote and not double_quote: backtick = not backtick
            
        if line_num >= 1144 and line_num <= 1365:
            if single_quote or double_quote or backtick:
                print(f"File Line {line_num}: Unclosed quote! Single: {single_quote}, Double: {double_quote}, Backtick: {backtick}")
                print(f"Content: {line}")

check_balance('web/backend/static/overlay_window.html')
