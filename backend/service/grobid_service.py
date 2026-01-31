import requests
from bs4 import BeautifulSoup
import os
import re

class GrobidService:
    GROBID_URL = os.getenv("GROBID_SERVER_URL", "http://localhost:8070")

    @staticmethod
    def process_references(pdf_file_bytes, filename: str):
        """
        Sends the PDF to Grobid to extract and parse references.
        Returns a list of suggestion dictionaries.
        """
        suggestions = []
        try:
            # Call Grobid processReferences API
            # This API extracts references from the PDF and parses them.
            url = f"{GrobidService.GROBID_URL}/api/processReferences"
            files = {'input': (filename, pdf_file_bytes, 'application/pdf')}
            
            # Allow consolidated references to resolve citations if possible, 
            # though processReferences mainly returns the list.
            data = {'consolidateHeader': '0', 'consolidateCitations': '0'} 

            try:
                response = requests.post(url, files=files, data=data, timeout=30)
            except requests.exceptions.ConnectionError:
                print("Warning: Could not connect to Grobid server.")
                return [{
                    "original_text": "System Check",
                    "issue_type": "configuration",
                    "description": "Grobid server is not reachable.",
                    "suggestion": "Please ensure Grobid is running at " + GrobidService.GROBID_URL
                }]

            if response.status_code != 200:
                print(f"Grobid error: {response.text}")
                return []

            # Grobid returns TEI XML
            soup = BeautifulSoup(response.content, 'xml')
            
            # The output has <listBibl> containing <biblStruct> elements
            references = soup.find_all('biblStruct')
            
            for i, ref in enumerate(references):
                ref_suggestions = GrobidService.validate_reference(ref, i + 1)
                suggestions.extend(ref_suggestions)

        except Exception as e:
            print(f"Error in Grobid execution: {e}")
            
        return suggestions

    @staticmethod
    def validate_reference(ref_xml, index):
        """
        Validates a single parsed reference (biblStruct) against the rules.
        """
        suggestions = []
        
        # Extract Raw Reference Text (approximate reconstruction or note)
        # Grobid sometimes includes the <note type="raw_reference"> but mostly in processCitation.
        # processReferences usually gives structured data. Ideally we want the original text to compare.
        # Usually checking the <note> tag or checking if Grobid provided the raw string.
        # If not, we validate based on the PARSED content, assuming that's what we want to correct.
        # Wait, the rule says "Mark references that do not meet requirements".
        # If Grobid corrected it, we might not know it was wrong.
        # BUT Grobid usually extracts what is THERE.
        # Let's extract the "raw" text if possible. In Reference segmenter, the text is implied.
        # We will iterate the nodes to check values.
        
        # Reconstruct a "display" string for the Original Text field
        # or grab the full text if available.
        # <biblStruct> often doesn't have the raw text in 'processReferences' unless 'includeRaw' is set?
        # Actually, let's look for <monogr> or <analytic> titles.
        
        # 1. Author Validation
        # Rule: Surname full, First name initial only. Keep first 3, >3 add et al.
        
        analytic = ref_xml.find('analytic')
        monogr = ref_xml.find('monogr')
        
        # Authors can be in analytic (article) or monogr (book/journal)
        authors = []
        if analytic:
            authors.extend(analytic.find_all('author'))
        if monogr:
            authors.extend(monogr.find_all('author'))
            
        # Deduplicate (sometimes they appear in both if not parsed perfectly, but usually analytic authors are article authors)
        # We generally check the first list we find.
        if not authors and monogr:
             # Fallback if no analytic
             pass
             
        # 1. Author Validation
        # Rule: Surname full, First name initial only. Keep first 3, >3 add "et al."
        
        analytic = ref_xml.find('analytic')
        monogr = ref_xml.find('monogr')
        
        authors = []
        if analytic:
            authors.extend(analytic.find_all('author'))
        if monogr:
            authors.extend(monogr.find_all('author'))
            
        # Deduplicate if needed (simple check)
        if not authors and monogr:
             pass

        # Check Author Count
        if len(authors) > 3:
             # Construct list of first 3 for suggestion
             display_authors = []
             for a in authors[:3]:
                 s = a.find('surname').text if a.find('surname') else ""
                 f = a.find('forename').text if a.find('forename') else ""
                 f_init = f[0] if f else ""
                 display_authors.append(f"{s} {f_init}")
             
             suggestion_text = ", ".join(display_authors) + ", et al."
             
             suggestions.append({
                "original_text": f"Ref #{index} Authors count: {len(authors)}",
                "issue_type": "format",
                "description": "More than 3 authors listed.",
                "suggestion": f"Keep only the first 3 authors and add ', et al.' (e.g. {suggestion_text})"
            })
            
        # Check Author Name Format
        invalid_format_authors = []
        for author in authors:
            persName = author.find('persName')
            if not persName: continue
            
            surname = persName.find('surname')
            forename = persName.find('forename')
            
            s_text = surname.text if surname else ""
            f_text = forename.text if forename else ""
            
            # Rule: First name only initial
            # Allow multiple initials (e.g. "Z. Y." or "Z Y")
            is_full_name = False
            # Split by common delimiters (space, dot, hyphen)
            parts = re.split(r'[\s\-\.]+', f_text)
            for p in parts:
                if not p: continue
                if len(p) > 1:
                    is_full_name = True
                    break

            if is_full_name:
                 # It's a full name like "George"
                 invalid_format_authors.append(f"{s_text} {f_text}")

        if invalid_format_authors:
            suggestions.append({
                "original_text": ", ".join(invalid_format_authors[:3]),
                "issue_type": "format",
                "description": "Authors should use full surname and first name initials only.",
                "suggestion": "Change first names to initials (e.g., 'Surname G' or 'Surname G Y')."
            })

        # 2. Title Validation
        # Rule: Only first word's first letter uppercase (Sentence case)
        title_node = None
        if analytic:
            title_node = analytic.find('title', level="a")
        if not title_node and monogr:
            title_node = monogr.find('title', level="m") # Book title if no article
            
        if title_node:
            title_text = title_node.text.strip()
            words = title_text.split()
            suspicious_caps = []
            
            # Check first word capitalization
            if words and len(words[0]) > 0 and not words[0][0].isupper():
                 suggestions.append({
                    "original_text": words[0],
                    "issue_type": "format",
                    "description": "Title should start with an uppercase letter.",
                    "suggestion": f"Capitalize '{words[0]}'."
                })

            # Check subsequent words (Sentence case)
            if len(words) > 1:
                for w in words[1:]:
                    # Remove punctuation for check
                    clean_w = re.sub(r'[^\w\s]', '', w)
                    if not clean_w: continue
                    # Rule: Only first word's first letter uppercase. 
                    if clean_w[0].isupper():
                        # We might flag proper nouns, but the rule is strict.
                        suspicious_caps.append(w)
            
            if suspicious_caps:
                 suggestions.append({
                    "original_text": title_text,
                    "issue_type": "format",
                    "description": "Title should be in sentence case (only first word capitalized).",
                    "suggestion": "Lower-case the following words: " + ", ".join(suspicious_caps[:5])
                })

        # 3. Journal/Conference Validation
        # Rule: Journal Name -> Capitalized first letters (Title Case).
        # Rule: Conference Name -> Capitalized first letters, prefixed with "In: Proceedings of"
        
        venue_node = None
        if monogr:
             # Try to find journal title or meeting title
             venue_node = monogr.find('title', level="j") or monogr.find('title', level="m")
        
        if venue_node:
             venue_text = venue_node.text.strip()
             
             # Check Title Case
             words = venue_text.split()
             lower_words = [w for w in words if w[0].islower() and w.lower() not in ['of', 'the', 'in', 'and', 'for', 'on', 'to', 'at', 'by']]
             if lower_words:
                  suggestions.append({
                    "original_text": venue_text,
                    "issue_type": "format",
                    "description": "Journal/Conference name should have capitalized first letters (Title Case).",
                    "suggestion": f"Capitalize: {', '.join(lower_words)}"
                })
        
             # Check for Conference "In: Proceedings of"
             # Heuristic: keywords
             is_conference = any(k in venue_text.lower() for k in ['proceeding', 'conference', 'symposium', 'workshop'])
             
             if is_conference:
                # Need to check if "In: Proceedings of" is present.
                pass # Logic continues below based on raw text if possible or just reminding.
                
                # Check using raw_reference if captured by Grobid
                raw_ref_node = ref_xml.find('note', type='raw_reference')
                raw_ref = raw_ref_node.text.strip() if raw_ref_node else ""
                
                if raw_ref and "In: Proceedings of" not in raw_ref:
                     suggestions.append({
                        "original_text": "Conference Ref",
                        "issue_type": "format",
                        "description": "Conference papers should be prefixed with 'In: Proceedings of'.",
                        "suggestion": "Ensure the citation includes 'In: Proceedings of' before the conference name."
                    })

        # 4. Citation Validation
        # Rule: Year, Vol: Page. No Issue.
        # 4. Imprint Validation
        # Rule: Year, Vol: Page. No Issue. No trailing dot.
        imprint = monogr.find('imprint') if monogr else None
        if imprint:
            # Check Issue
            issue = imprint.find('biblScope', unit="issue")
            if issue:
                suggestions.append({
                    "original_text": f"Issue: {issue.text}",
                    "issue_type": "format",
                    "description": "Issue number shouldn't be included.",
                    "suggestion": "Remove the issue number."
                })
            
            # Check Volume
            vol = imprint.find('biblScope', unit="volume")
            # If Journal, Volume is expected usually.
            if not vol and venue_node: 
                 suggestions.append({
                    "original_text": "Missing Volume",
                    "issue_type": "missing_info",
                    "description": "Volume number is missing.",
                    "suggestion": "Add Volume number (e.g. Year, Volume: Page)."
                })

            # Check for trailing dot in raw reference
            raw_ref_node = ref_xml.find('note', type='raw_reference')
            if raw_ref_node:
                raw_text = raw_ref_node.text.strip()
                if raw_text.endswith('.'):
                    suggestions.append({
                        "original_text": "Trailing dot detected",
                        "issue_type": "format",
                        "description": "Reference should not end with a dot.",
                        "suggestion": "Remove the final period."
                    })

        return suggestions
