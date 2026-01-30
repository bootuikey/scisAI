import fitz
import re
from typing import List, Set, Tuple
from schema.api_schema import Suggestion

class VisualCheckService:
    @staticmethod
    def check_visuals(content: bytes) -> List[Suggestion]:
        suggestions = []
        
        # 1. Check Figures and Tables (Count vs Mentions)
        suggestions.extend(VisualCheckService._check_figure_table_mentions(content))
        
        return suggestions

    @staticmethod
    def _check_figure_table_mentions(content: bytes) -> List[Suggestion]:
        suggestions = []
        doc = fitz.open(stream=content, filetype="pdf")
        
        full_text = ""
        for page in doc:
            full_text += page.get_text()
            
        # Detect Captions (Existence)
        # Strategy: Look for lines starting with "Figure X" or "Table X"
        # We define a "Caption" as the start of a logical Figure/Table.
        # Regex for captions (start of line)
        fig_caption_pattern = r'(?m)^\s*(?:Figure|Fig\.?)\s*(\d+)'
        table_caption_pattern = r'(?m)^\s*Table\s*(\d+)'
        
        existing_figures = set(re.findall(fig_caption_pattern, full_text, re.IGNORECASE))
        existing_tables = set(re.findall(table_caption_pattern, full_text, re.IGNORECASE))
        
        # Detect Mentions (References in text)
        # We look for "Figure X" or "Table X" anywhere.
        # But we must exclude the captions themselves to verify they are *cited*.
        # Actually, counting occurrences is easier.
        # If ID "1" appears only once, it's likely just the caption (or just a mention without caption).
        # A proper figure should be mentioned at least once + have a caption = 2+ occurrences?
        # Or simpler: Search for patterns that look like citations, e.g. "Figure 1 shows..." or "(see Table 1)".
        
        # Let's extract all "Figure X" tokens.
        all_fig_tokens = re.findall(r'(?:Figure|Fig\.?)\s*(\d+)', full_text, re.IGNORECASE)
        all_table_tokens = re.findall(r'Table\s*(\d+)', full_text, re.IGNORECASE)
        
        # Check Figures
        uncited_figures = []
        for fig_id in existing_figures:
            # Count occurrences of this ID in the context of Figure/Fig
            count = all_fig_tokens.count(fig_id)
            if count < 2:
                # Potential issue: Found as caption (presumably) but not mentioned elsewhere?
                # Or found as reference but no caption?
                # The rule says: "Check if mentioned in body text".
                # If we assume 'existing_figures' are captions, and we only found 1 occurrence total, it's not mentioned in text.
                uncited_figures.append(fig_id)
                
        # Check Tables
        uncited_tables = []
        for table_id in existing_tables:
            count = all_table_tokens.count(table_id)
            if count < 2:
                uncited_tables.append(table_id)
                
        if uncited_figures:
            suggestions.append(Suggestion(
                original_text=f"Figures detected: {', '.join(existing_figures)}",
                issue_type="content_mismatch",
                description=f"Figures {', '.join(sorted(uncited_figures))} seem to be present but not explicitly mentioned/cited in the text.",
                suggestion="Ensure all figures are referenced in the body text."
            ))

        if uncited_tables:
            suggestions.append(Suggestion(
                original_text=f"Tables detected: {', '.join(existing_tables)}",
                issue_type="content_mismatch",
                description=f"Tables {', '.join(sorted(uncited_tables))} seem to be present but not explicitly mentioned/cited in the text.",
                suggestion="Ensure all tables are referenced in the body text."
            ))
            
        doc.close()
        return suggestions


