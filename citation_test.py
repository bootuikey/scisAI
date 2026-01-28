
import re

def parse_citations(text):
    citation_pattern = r'\[\s*([0-9,\s\-\u2013]+)\s*\]'
    citations = []
    
    for match in re.finditer(citation_pattern, text):
        content = match.group(1)
        # Split by comma
        parts = content.split(',')
        current_group = []
        for part in parts:
            part = part.strip()
            if not part: continue
            
            # Check for range (hyphen or en-dash)
            if '-' in part or '\u2013' in part:
                range_parts = re.split(r'[-\u2013]', part)
                if len(range_parts) >= 2:
                    try:
                        start = int(range_parts[0].strip())
                        end = int(range_parts[-1].strip())
                        current_group.extend(range(start, end + 1))
                    except ValueError:
                        pass
            else:
                try:
                    num = int(part)
                    current_group.append(num)
                except ValueError:
                    pass
        
        if current_group:
            citations.append((match.group(0), current_group))
            
    return citations

def check_order(citations_list):
    seen_max = 0
    errors = []
    cited_set = set()
    
    for text, nums in citations_list:
        for n in nums:
            cited_set.add(n)
            if n > seen_max + 1:
                errors.append(f"Ref {text} contains [{n}] which appears before [{seen_max+1}] was cited.")
            # Update seen_max if this is a new high water mark
            # Even if it skipped, we typically assume the sequence continues from there or we flag it.
            # But the rule says "mark numbers not in order".
            if n > seen_max:
                seen_max = n
    return errors, cited_set

# Test
text = """
This is a test [1]. Then we assume [2].
Here we skip to [4]. And then [3] appears.
Also [5-7] are cited clearly.
And [9, 10] are skipped.
"""

citations = parse_citations(text)
print("Found:", citations)
errors, cited = check_order(citations)
print("Errors:", errors)
print("Cited:", cited)
