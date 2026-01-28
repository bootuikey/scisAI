import fitz
import pdfplumber
import re
import io
from typing import List, Set, Tuple
from schema.api_schema import Suggestion

class VisualCheckService:
    @staticmethod
    def check_visuals(content: bytes) -> List[Suggestion]:
        suggestions = []
        
        # We need a file-like object for pdfplumber
        file_stream = io.BytesIO(content)
        
        # 1. Check Figures and Tables (Count vs Mentions)
        suggestions.extend(VisualCheckService._check_figure_table_mentions(content))
        
        # 2. Check Text and Line Colors (Avoid Light Colors)
        suggestions.extend(VisualCheckService._check_light_colors(content))
        
        # 3. Check Table Content Colors (No Colored Text/Lines)
        suggestions.extend(VisualCheckService._check_table_colors(file_stream))
        
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

    @staticmethod
    def _check_light_colors(content: bytes) -> List[Suggestion]:
        # Rule: Avoid light colors (yellow, light blue) in text and lines.
        suggestions = []
        doc = fitz.open(stream=content, filetype="pdf")
        
        light_color_issues = []
        
        def is_unsafe_light(r, g, b):
            # Exclude White/near White (background)
            if r > 240 and g > 240 and b > 240:
                return False
            
            # Check for Light Colors
            # Yellow (255, 255, 0) -> High R, High G, Low B.
            # Light Blue (173, 216, 230).
            # We use Luminance: 0.299R + 0.587G + 0.114B
            lum = 0.299*r + 0.587*g + 0.114*b
            
            # If Luminance is high (light) but not white
            if lum > 180:
                # Check saturation/color. If it's just gray, maybe it's fine?
                # "Avoid light colors... e.g. yellow, light blue".
                # Light Gray is also distinct from White but hard to print?
                # Let's flag any non-grayscale light color.
                # Saturation check: difference between max and min channel
                saturation = max(r,g,b) - min(r,g,b)
                if saturation > 20: # It has some color
                    return True
                # If it's light gray (saturation low, lum high), also bad for text?
                # Usually text should be dark.
                if lum > 200: 
                    return True
            return False

        for page_num, page in enumerate(doc):
            # Check Text
            text_dict = page.get_text("dict")
            for block in text_dict.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        color = span["color"] # sRGB int
                        # Convert to RGB
                        r = (color >> 16) & 0xFF
                        g = (color >> 8) & 0xFF
                        b = color & 0xFF
                        
                        if is_unsafe_light(r, g, b):
                            msg = f"Page {page_num+1}: Found light colored text '{span['text'][:20]}...' (RGB: {r},{g},{b})"
                            if len(light_color_issues) < 5:
                                light_color_issues.append(msg)

            # Check Drawings (Lines/Shapes)
            drawings = page.get_drawings()
            for draw in drawings:
                # Stroke color
                if draw["stroke_opacity"] > 0:
                     # 'color' is usually a tuple of floats (0-1) in recent pymupdf
                    stroke = draw.get("color")
                    if stroke and len(stroke) == 3:
                        r, g, b = [int(x*255) for x in stroke]
                        if is_unsafe_light(r, g, b):
                             msg = f"Page {page_num+1}: Found light colored line/shape (RGB: {r},{g},{b})"
                             if len(light_color_issues) < 5:
                                 light_color_issues.append(msg)
                                 
                # Fill color
                if draw["fill_opacity"] > 0:
                    fill = draw.get("fill")
                    if fill and len(fill) == 3:
                        r, g, b = [int(x*255) for x in fill]
                        if is_unsafe_light(r, g, b):
                             msg = f"Page {page_num+1}: Found light colored fill (RGB: {r},{g},{b})"
                             if len(light_color_issues) < 5:
                                 light_color_issues.append(msg)
            
                            
            # Check Embedded Images
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                xref = img[0]
                try:
                    pix = fitz.Pixmap(doc, xref)
                    # Convert to RGB if needed
                    if pix.n < 3: # Gray or mono
                        pix = fitz.Pixmap(fitz.csRGB, pix)
                    
                    # Convert to fitz raw bytes -> Pillow or just analyze bytes?
                    # Analyzing bytes specific logic is faster.
                    # RGB RGB RGB...
                    # But Pillow is easier.
                    from PIL import Image
                    mode = "RGB" if pix.alpha == 0 else "RGBA"
                    img_data = pix.samples
                    pil_img = Image.frombytes(mode, [pix.width, pix.height], img_data)
                    
                    # Resize for speed
                    pil_img = pil_img.resize((50, 50))
                    
                    # Analyze pixels
                    # Convert to HSV? Or just check RGB.
                    # Let's count "unsafe" pixels.
                    unsafe_pixel_count = 0
                    total_pixels = 50 * 50
                    
                    for pixel in pil_img.getdata():
                        # pixel is (r,g,b) or (r,g,b,a)
                        if len(pixel) >= 3:
                            r, g, b = pixel[:3]
                            if is_unsafe_light(r, g, b):
                                unsafe_pixel_count += 1
                                
                    # If more than 10% of image is unsafe light color
                    if unsafe_pixel_count > total_pixels * 0.1:
                         msg = f"Page {page_num+1} Image {img_index+1}: Found image with significant light-colored areas (e.g. yellow/cyan)."
                         if msg not in light_color_issues:
                             light_color_issues.append(msg)
                             
                    pix = None # Release
                except Exception as e:
                    # Ignore processing errors for specific images
                    pass
                
                if len(light_color_issues) >= 5: break
            
            if len(light_color_issues) >= 5:
                break

        
        if light_color_issues:
            suggestions.append(Suggestion(
                original_text="Visual Color Check",
                issue_type="compliance_warning",
                description="Found text or lines using light colors (e.g., yellow, light blue) which may cause printing issues. Examples:\n" + "\n".join(light_color_issues),
                suggestion="Avoid using light colors for text and lines. Ensure high contrast."
            ))
            
        return suggestions

    @staticmethod
    def _check_table_colors(file_stream) -> List[Suggestion]:
        # Rule: Table content should not be colored (black/white/gray only).
        suggestions = []
        
        colored_table_issues = []
        
        def is_colored(r, g, b):
            # Check if has color (saturation)
            # Allow small deviation for black/dark gray (e.g. compression artifacts)
            if max(r,g,b) - min(r,g,b) > 20:
                return True
            return False

        try:
            with pdfplumber.open(file_stream) as pdf:
                for page_num, page in enumerate(pdf.pages):
                    tables = page.find_tables()
                    for i, table in enumerate(tables):
                        bbox = table.bbox
                        # Check objects inside this bbox
                        
                        # Check characters (text)
                        # Page.chars has 'non_stroking_color' (fill) and 'stroking_color' (outline)
                        # pdfplumber colors are often tuples 0-1 or 0-255? 
                        # pdfplumber usually returns (R, G, B) normalized or 0-1 depending on version/pdfminer.
                        # Actually pdfplumber based on pdfminer.six. Colors are usually tuples.
                        
                        cropped = page.crop(bbox)
                        
                        # Check Chars
                        for char in cropped.chars:
                            # sc = stroking color, nsc = non_stroking_color
                            # Depending on PDF, one is used. Text is usually nsc (fill).
                            color = char.get("non_stroking_color")
                            if color and isinstance(color, (list, tuple)) and len(color) == 3:
                                # Assume 0-1 if floats, 0-255 if ints.
                                # Check type
                                c_vals = list(color)
                                if all(isinstance(v, float) for v in c_vals):
                                    c_vals = [int(v*255) for v in c_vals]
                                
                                if is_colored(*c_vals):
                                    msg = f"Page {page_num+1} Table {i+1}: Found colored text content."
                                    if msg not in colored_table_issues:
                                        colored_table_issues.append(msg)
                                        
                        # Check Lines/Rects (Borders/Fills)
                        for rect in cropped.rects:
                             # non_stroking_color (fill), stroking_color (border)
                            for key in ["non_stroking_color", "stroking_color"]:
                                color = rect.get(key)
                                if color and isinstance(color, (list, tuple)) and len(color) == 3:
                                    c_vals = list(color)
                                    if all(isinstance(v, float) for v in c_vals):
                                        c_vals = [int(v*255) for v in c_vals]
                                    if is_colored(*c_vals):
                                        msg = f"Page {page_num+1} Table {i+1}: Found colored table element."
                                        if msg not in colored_table_issues:
                                            colored_table_issues.append(msg)
                                            
                        if len(colored_table_issues) >= 5: break
                    if len(colored_table_issues) >= 5: break
        except Exception as e:
            # pdfplumber might fail on some streams or complex PDFs
            print(f"IndexError or analysis error in table color check: {e}")
            pass

        if colored_table_issues:
             suggestions.append(Suggestion(
                original_text="Table Color Check",
                issue_type="compliance_warning",
                description="Tables should not use colored text or elements (must be black/white/grayscale). Found issues:\n" + "\n".join(colored_table_issues),
                suggestion="Convert table contents to black and white or grayscale."
            ))
            
        return suggestions
