
import re

def test_logic():
    # Simulate the user's text and a failed reference header detection
    
    full_text = """
    Introduction
    Aiming at reducing the computational load introduced by solving regulator equations, Gao et al. [29,30] proposed an internal model-based approach for solving output regulation problems. By constructing an augmented system through an internal model [32,33], this method eliminates the requirement to solve regulator equations, thus offering faster computation compared to conventional methods.
    
    References
    [29] Gao ...
    [30] Gao ...
    [32] ...
    [33] ...
    """
    
    # 1. Try to find header with current regex
    ref_header_pattern = r'(?i)\n\s*(references|bibliography|reference)\s*\n'
    matches = list(re.finditer(ref_header_pattern, full_text))
    
    ref_count = 0
    body_text = full_text
    
    if matches:
        print("Header found!")
        last_match = matches[-1]
        body_text = full_text[:last_match.start()]
        ref_text = full_text[last_match.end():]
        
        brackets_pattern = r'^\s*\[\d+\]'
        dot_pattern = r'^\s*\d+\.'
        ref_items_brackets = re.findall(brackets_pattern, ref_text, re.MULTILINE)
        ref_items_dots = re.findall(dot_pattern, ref_text, re.MULTILINE)
        ref_count = max(len(ref_items_brackets), len(ref_items_dots))
    else:
        print("Header NOT found.")
        
    print(f"Ref Count: {ref_count}")
    
    if ref_count > 0:
        print("Running Checks...")
        # Check logic
        citation_pattern = r'\[\s*([0-9,\s\-\u2013]+)\s*\]'
        max_seen = 0
        order_issues = []
        
        for match in re.finditer(citation_pattern, body_text):
            content = match.group(1)
            parts = content.split(',')
            current_batch = []
            for part in parts:
                part = part.strip()
                if not part: continue
                if '-' in part:
                    pass # Simplified
                else:
                    try:
                        current_batch.append(int(part))
                    except: pass
            
            for num in current_batch:
                print(f"Processing citation: {num}, max_seen: {max_seen}")
                if num > max_seen + 1:
                    print(f"Error: {num} > {max_seen} + 1")
                    order_issues.append(f"Ref [{num}] cited before [{max_seen+1}]")
                if num > max_seen:
                    max_seen = num
                    
        print("Issues:", order_issues)
    else:
        print("Skipping Checks because ref_count is 0")

test_logic()
