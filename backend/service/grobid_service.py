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
             
        # Check Author Format
        author_names = []
        invalid_format_authors = []
        
        for author in authors:
            persName = author.find('persName')
            if not persName: continue
            
            surname = persName.find('surname')
            forename = persName.find('forename')
            
            s_text = surname.text if surname else ""
            f_text = forename.text if forename else ""
            
            author_names.append(f"{s_text} {f_text}")
            
            # Check: First name initial only
            # If forename is longer than 2 chars and doesn't end with dot, or just longer than 1 char (ignoring dot)
            # Example "John" -> Invalid. "J." -> Valid. "J" -> Valid? usually "J."
            if len(f_text) > 2 and not f_text.endswith('.'):
                 invalid_format_authors.append(f"{f_text} {s_text}")
            elif len(f_text) > 1 and f_text[-1] != '.':
                 # Potentially "Jo" - vague. Let's strict check: "First name initial only".
                 # So "J" or "J." is ok. "John" is not.
                 if len(f_text) > 1: # e.g. "John"
                    invalid_format_authors.append(f"{f_text} {s_text}")

        if invalid_format_authors:
            suggestions.append({
                "original_text": f"Ref #{index} Authors: " + ", ".join(invalid_format_authors),
                "issue_type": "format",
                "description": "Authors should use full surname and initial-only first name.",
                "suggestion": "Change first names to initials (e.g., 'John Smith' -> 'Smith, J.')."
            })

        # Check: Keep first 3 authors, >3 et al.
        # We can only check if we HAVE > 3 authors.
        if len(authors) > 3:
            suggestions.append({
                "original_text": f"Ref #{index} (Authors count: {len(authors)})",
                "issue_type": "clarity",
                "description": "More than 3 authors listed.",
                "suggestion": f"Keep only the first 3 authors and add 'et al.' (e.g. {author_names[0]}, {author_names[1]}, {author_names[2]} et al.)"
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
            # Simple heuristic for Sentence case
            # Split by space. Check words after the first one.
            # Ignore proper nouns? Hard to detect without NLP.
            # But the rule says "Title only first word first letter uppercase". Strict rule.
            # We will check if Words[1:] start with Uppercase.
            
            words = title_text.split()
            suspicious_caps = []
            if len(words) > 1:
                for w in words[1:]:
                    # Remove punctuation for check
                    clean_w = re.sub(r'[^\w\s]', '', w)
                    if not clean_w: continue
                    if clean_w[0].isupper() and len(clean_w) > 1:
                        # Exclude likely acronyms/formulas if possible, but rule is strict.
                        # We'll flag it as potential issue.
                        suspicious_caps.append(w)
            
            if suspicious_caps:
                 suggestions.append({
                    "original_text": title_text,
                    "issue_type": "format",
                    "description": "Title should be in sentence case (only first word capitalized, barring proper nouns).",
                    "suggestion": "Lower-case the following words if they are not proper nouns: " + ", ".join(suspicious_caps[:5])
                })

        # 3. Journal/Conference Validation
        # Rule: Journal Name -> Initial caps (Title Case). Conference -> "In: Proceedings of..."
        # Rule: Journal Name -> Preferably abbreviated. (Hard to check preference, but can check Case)
        
        venue_title = None
        if monogr:
             # Journal title
             j_title = monogr.find('title', level="j")
             if j_title:
                 venue_text = j_title.text.strip()
                 # Check Title Case
                 # If many words are lowercase, flag it.
                 words = venue_text.split()
                 lower_words = [w for w in words if w[0].islower() and w not in ['of', 'the', 'in', 'and', 'for', 'on', 'to']]
                 if len(lower_words) > 0:
                      suggestions.append({
                        "original_text": venue_text,
                        "issue_type": "format",
                        "description": "Journal name should be Capitalized (Title Case).",
                        "suggestion": f"Capitalize: {', '.join(lower_words)}"
                    })
                 
                 # Check Abbreviation (heuristic: look for dots? or length?)
                 # "Use abbreviation" is a "preference". Maybe skip strict check unless obvious.
        
        # Conference Check? Grobid might classify as <title level="m"> or "j".
        # If it looks like a conference (contains "Proc", "Conference", "Symposium")
        # Check if it starts with "In: Proceedings of"
        # Since Grobid parses the title, it might strip "In:". We check the raw context or just Suggest it.
        # Actually checking strict "In: Proceedings of" prefix on a parsed field is tricky because Grobid extracts the *Name*.
        # We'd ideally want to see the prefix text. 
        # But if the Venue Name itself is "Proceedings of...", we can check.
        # If the user means "The citation string should contain In: Proceedings of...", we might miss it if Grobid stripped it.
        # We will skip strict "In:" check unless we have raw text, but we can check the capitalized words for Conference names.

        # 4. Citation Validation
        # Rule: Year, Vol: Page. No Issue.
        imprint = monogr.find('imprint') if monogr else None
        if imprint:
            # Check Issue
            issue = imprint.find('biblScope', unit="issue")
            if issue:
                suggestions.append({
                    "original_text": f"Issue: {issue.text}",
                    "issue_type": "format",
                    "description": "Issue number found.",
                    "suggestion": "Remove the issue number. Format should be: Year, Volume: Page."
                })
            
            # Check Format: Vol: Page
            vol = imprint.find('biblScope', unit="volume")
            page = imprint.find('biblScope', unit="page")
            year = imprint.find('date', type="published")
            
            # If we have Vol and Page, we can't easily check the colon punctuation in extracted XML.
            # But we can verify their existence.
            if not vol and j_title: # Journals usually need volume
                 suggestions.append({
                    "original_text": f"Ref #{index} (Journal)",
                    "issue_type": "missing_info",
                    "description": "Missing Volume number.",
                    "suggestion": "Ensure Volume number is included."
                })

        return suggestions
