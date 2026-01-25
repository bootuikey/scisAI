import fitz  # PyMuPDF
from fastapi import UploadFile, HTTPException
from typing import Tuple, List
import io
from PIL import Image

class PDFService:
    @staticmethod
    async def extract_content_from_pdf(content: bytes) -> Tuple[str, List[Image.Image], List[Image.Image]]:
        # if file.content_type != "application/pdf":
        #    raise HTTPException(status_code=400, detail="File must be a PDF")
        
        try:
            # content = await file.read()
            doc = fitz.open(stream=content, filetype="pdf")
            
            text_content = []
            figures = []
            formulas = []
            
            for page in doc:
                # 1. Extract Text
                text_content.append(page.get_text())
                
                # 2. Extract Figures (Native)
                image_list = page.get_images(full=True)
                for img in image_list:
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]
                    try:
                        image = Image.open(io.BytesIO(image_bytes))
                        if image.width >= 50 and image.height >= 50: # Filter tiny formatting images
                            figures.append(image)
                    except Exception:
                        continue
                
                # 3. Extract Formulas (Smart Crop)
                # Use "dict" to get structural info (blocks/lines/spans/fonts)
                blocks = page.get_text("dict")["blocks"]
                for b in blocks:
                    if "lines" not in b: continue
                    
                    is_formula_candidate = False
                    
                    # Heuristic A: Check Fonts in Spans
                    # Common logical math fonts: CMBX, MathJax, Symbol, CMSY, CMMI, CMEX, MSBM
                    for line in b["lines"]:
                        for span in line["spans"]:
                            font_name = span["font"].lower()
                            if any(k in font_name for k in ['math', 'cmbx', 'cmmi', 'cmsy', 'cmex', 'symbol', 'msbm', 'mjx']):
                                is_formula_candidate = True
                                break
                        if is_formula_candidate: break
                    
                    # Heuristic B: Position/Layout (Display Math usually has whitespace/indentation)
                    # This is harder to make generic without page detailed analysis, 
                    # so we will rely primarily on Font detection + Block separation for now.
                    # If the user specifically asked for bbox checks, we can add:
                    # if not is_formula_candidate:
                    #    page_width = page.rect.width
                    #    bbox = b["bbox"]
                    #    indent_left = bbox[0]
                    #    indent_right = page_width - bbox[2]
                    #    if indent_left > 50 and indent_right > 50: is_formula_candidate = True
                    
                    if is_formula_candidate:
                        # Padding for cleaner crop
                        r = fitz.Rect(b["bbox"])
                        # Zoom in for clear formula recognition
                        pix = page.get_pixmap(clip=r, matrix=fitz.Matrix(3, 3)) 
                        img_data = pix.tobytes("png")
                        formulas.append(Image.open(io.BytesIO(img_data)))

            full_text = "\n".join(text_content)
            
            if not full_text.strip() and not figures and not formulas:
                 raise HTTPException(status_code=400, detail="Could not extract content from PDF")
                 
            return full_text, figures, formulas
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")
