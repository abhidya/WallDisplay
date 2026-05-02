import re

def check_balance(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    # Extract script starting at line 1059
    script_match = re.search(r'<script>(.*?)</script>', content, re.DOTALL)
    if not script_match:
        print("No script found")
        return
    
    # Actually just check braces around first 400 lines of script
    script = script_match.group(1)
    
    lines = script.split('\n')
    
    for i in range(len(lines)):
        if "const ANIMATION_SCRIPT_MANIFEST" in lines[i]:
            start_idx = i
            break
            
    print(f"ANIMATION_SCRIPT_MANIFEST starts at script line {start_idx}")
    
    bracket_count = 0
    square_count = 0
    paren_count = 0
    
    for i, line in enumerate(lines):
        for char in line:
            if char == '{': bracket_count += 1
            elif char == '}': bracket_count -= 1
            elif char == '[': square_count += 1
            elif char == ']': square_count -= 1
            elif char == '(': paren_count += 1
            elif char == ')': paren_count -= 1
            
        if "};" in line and "anime_background" in lines[i-3] if i >= 3 else False:
            print(f"File Line {1060 + i}: {line.strip()} - Braces: {bracket_count}, Squares: {square_count}, Parens: {paren_count}")

check_balance('web/backend/static/overlay_window.html')
