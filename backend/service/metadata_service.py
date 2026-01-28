import fitz
import re
from typing import List, Dict, Optional
from schema.api_schema import Suggestion

class MetadataService:
    @staticmethod
    def check_metadata(content: bytes) -> List[Suggestion]:
        suggestions = []
        doc = fitz.open(stream=content, filetype="pdf")
        
        if len(doc) == 0:
            return suggestions

        first_page = doc[0]
        text_dict = first_page.get_text("dict")
        blocks = text_dict.get("blocks", [])
        
        # 1. Identify Article Type
        article_type = None
        # valid_types = [
        #     "REVIEW", "RESEARCH PAPER", "POSITION PAPER", 
        #     "MOOP", "PERSPECTIVE", "LETTER"
        # ]
        
        # Look in the top area of the first page (e.g., top 20% or simply the first few text blocks)
        # The rule mentions "Top left", "Left and right large dots".
        # Example pattern: "● REVIEW ●" or similar.
        
        found_type_block = None
        
        for b in blocks:
            if "lines" not in b: continue
            
            # Combine all text in the block to handle cases where dots and words are in different spans or lines
            block_text = ""
            for line in b["lines"]:
                for span in line["spans"]:
                    block_text += span["text"]
                block_text += " " # Add space between lines just in case
            
            # Normalize for checking
            # We look for pattern: DOT space* NAME space* DOT
            # Dots can be ●, ., etc.
            # Names can be REVIEW, RESEARCH PAPER, etc.
            
            # Clean up encoded spaces
            block_text = block_text.replace('\xa0', ' ').strip()
            
            # Regex pattern to match the decoration
            # [●\.] matches the dots. 
            # \s* matches optional spaces
            # (REVIEW|...) matches the type
            # \s* [●\.] matches the closing dot
            
            pattern = r'[●\.•]\s*(REVIEW|RESEARCH\s*PAPER|POSITION\s*PAPER|MOOP|PERSPECTIVE|LETTER)\s*[●\.•]'
            match = re.search(pattern, block_text, re.IGNORECASE)
            
            if match:
                raw_type = match.group(1).upper()
                # Normalize spaces in type name (e.g. "RESEARCH   PAPER" -> "RESEARCH PAPER")
                raw_type = " ".join(raw_type.split())
                
                article_type = raw_type
                found_type_block = b
                break
                
            # Fallback: check purely based on keyword if the dot check fails but keyword is strong?
            # The rule says it MUST be marked with dots. But maybe we can be lenient if we find the exact text in a header position?
            # For now, stick to the pattern as user specifically mentioned the dot format.
            
        if not article_type:
            # Second pass: Try ignoring dots if strict match failed, just in case, but prioritize the dot match.
            # Or maybe the dot is only on one side? The rule says "Left and right use a large dot".
            # Let's keep the strict regex first.
            pass
            
        if not article_type:
            suggestions.append(Suggestion(
                original_text="Header",
                issue_type="missing_info",
                description="Article Type not found or unrecognized.",
                suggestion="Ensure the article type (REVIEW, RESEARCH PAPER, etc.) is clearly marked at the top-left with large dots (e.g., ● REVIEW ●)."
            ))
            return suggestions # Can't check specific requirements without type
            
        # 2. Check Requirements based on Type
        # Extract full text of first page to search for components
        page_text = first_page.get_text()
        
        # Common checks
        missing_components = []
        
        # Check components
        # Heuristics:
        # Title: Usually exists if file not empty. Hard to miss. We assume it's there if type is there.
        # Authors: Hard to check.
        # Affiliations (Units): Look for superscript or "University/Institute/Department".
        # Corresponding Author (*): Look for literal "*" character in the header text area.
        # Email: Regex check.
        
        has_star = "*" in page_text or "∗" in page_text # Check normal and math ast
        has_email = bool(re.search(r'[\w\.-]+@[\w\.-]+\.\w+', page_text))
        
        # Heuristic for Units (Affiliations)
        # Check for common keywords indicating an institution
        unit_keywords = ["University", "Univ.", "Institute", "Dept.", "Department", "School", "Academy", "Hospital", "Center", "Centre", "Laboratory", "College", "Ltd", "Inc", "GmbH"]
        has_unit = any(keyword.lower() in page_text.lower() for keyword in unit_keywords)
        
        # Component Lists
        # Group A: REVIEW, RESEARCH PAPER, POSITION PAPER -> Need Abstract, Keywords, + standard
        # Group B: MOOP, PERSPECTIVE, LETTER -> Need + standard (No Abstract/Keywords explicitly required by rule?)
        # Wait, rule says:
        # If A: ... Abstract, Keywords.
        # If B: ... (Lists Title, Author, Unit, Corresp, Email). NO Abstract/Keywords listed.
        
        # Standard checks for all types in the rule list:
        # Title, Author, Unit, Corresp (*), Email.
        
        if not has_star:
            missing_components.append("Corresponding Author annotation (*)")
        
        if not has_email:
            missing_components.append("Corresponding Author Email")

        if not has_unit:
            missing_components.append("Affiliations/Units (e.g. University, Institute)")
            
        # Content checks for Group A
        if article_type in ["REVIEW", "RESEARCH PAPER", "POSITION PAPER"]:
            if not re.search(r'(?i)\babstract\b', page_text):
                missing_components.append("Abstract")
            if not re.search(r'(?i)\bkey\s*words\b', page_text):
                missing_components.append("Keywords")
        
        # Report
        if missing_components:
            suggestions.append(Suggestion(
                original_text=f"Article Type: {article_type}",
                issue_type="missing_content",
                description=f"Missing required metadata components for {article_type}.",
                suggestion=f"Please ensure the following are present: {', '.join(missing_components)}"
            ))

        # 3. Reference Analysis (Count, Order, Usage)
        
        # Extract full text for reference analysis
        full_text = ""
        for page in doc:
            full_text += page.get_text()
            
        # Locate References Section
        # Improved regex to handle "References", "Bibliography", "Literature Cited", with optional numbering (e.g. "6. References")
        ref_header_pattern = r'(?i)(\n|^)\s*(\d+(\.\d+)*\.?\s*)?(references|bibliography|literature\s*cited|works\s*cited)\s*(\n|$)'
        matches = list(re.finditer(ref_header_pattern, full_text))
        
        body_text = full_text
        ref_text = ""
        ref_count = 0
        
        if matches:
            last_match = matches[-1]
            body_text = full_text[:last_match.start()]
            ref_text = full_text[last_match.end():]
            
            # Count References
            brackets_pattern = r'^\s*\[\d+\]'
            dot_pattern = r'^\s*\d+\.'
            
            ref_items_brackets = re.findall(brackets_pattern, ref_text, re.MULTILINE)
            ref_items_dots = re.findall(dot_pattern, ref_text, re.MULTILINE)
            
            ref_count = max(len(ref_items_brackets), len(ref_items_dots))
            
        # Rule: MOOP/LETTER Reference Count Limit
        if article_type in ["MOOP", "LETTER"]:
            if ref_count > 5:
                suggestions.append(Suggestion(
                    original_text=f"Total References: {ref_count}",
                    issue_type="compliance_warning",
                    description=f"{article_type} articles are limited to 5 references (found {ref_count}).",
                    suggestion="Please reduce the reference count to 5 or fewer."
                ))
                
        # Rule: Citation Order
        # We run this check on body_text (or full_text if header missing)
        # Check sequence
        citation_pattern = r'\[\s*([0-9,\s\-\u2013]+)\s*\]'
        cited_numbers = []
        max_seen = 0
        order_issues = []
        
        # Determine text to check. If we found a split, use body_text. If not, use full_text but be careful.
        # Actually, using full_text is safe for "skipping ahead" checks because ref list usually resets to 1 or continues current count.
        # But scanning body_text is safer to avoid noise.
        text_to_scan_citations = body_text
        
        for match in re.finditer(citation_pattern, text_to_scan_citations):
            content = match.group(1)
            parts = content.split(',')
            current_batch = []
            
            for part in parts:
                part = part.strip()
                if not part: continue
                # Handle ranges
                if '-' in part or '\u2013' in part:
                    range_parts = re.split(r'[-\u2013]', part)
                    if len(range_parts) >= 2:
                        try:
                            start = int(range_parts[0].strip())
                            end = int(range_parts[-1].strip())
                            for k in range(start, end + 1):
                                current_batch.append(k)
                        except ValueError: pass
                else:
                    try:
                        current_batch.append(int(part))
                    except ValueError: pass
            
            for num in current_batch:
                # If we skipped a number (e.g. 1 -> 3), flag it.
                # Allow starting with > 1? Usually citations start at 1.
                # If max_seen is 0, and num is 1, ok. If num is 2, it skipped 1.
                if num > max_seen + 1:
                    msg = f"Ref [{num}] cited before [{max_seen + 1}]"
                    if msg not in order_issues:
                        order_issues.append(msg)
                
                if num > max_seen:
                    max_seen = num
                cited_numbers.append(num)
        
        if order_issues:
             suggestions.append(Suggestion(
                original_text="Citation Order",
                issue_type="sequence_error",
                description="Citations should appear in numerical order. Found issues: " + "; ".join(order_issues[:3]) + ("..." if len(order_issues)>3 else ""),
                suggestion="Ensure references are numbered in order of appearance."
            ))
        
        # Rule: Uncited References
        # Only possible if we successfully counted references in verification
        if ref_count > 0:
            cited_set = set(cited_numbers)
            all_refs = set(range(1, ref_count + 1))
            uncited = sorted(list(all_refs - cited_set))
            
            if uncited:
                uncited_str = ", ".join(map(str, uncited))
                description = f"References not cited in text: [{uncited_str}]"
                if len(description) > 200: description = description[:197] + "..."
                
                suggestions.append(Suggestion(
                    original_text="Uncited References",
                    issue_type="content_mismatch",
                    description=description,
                    suggestion="Remove uncited references or cite them in the text."
                ))

        return suggestions
