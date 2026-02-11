from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import uvicorn
import os
from dotenv import load_dotenv

load_dotenv()
from schema.api_schema import AnalysisResult
from service.pdf_service import PDFService
from service.llm_service import llm_service

app = FastAPI(title="PDF Analysis API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def root():
    return FileResponse('static/index.html')

from service.grobid_service import GrobidService
from service.metadata_service import MetadataService

@app.post("/analyze", response_model=AnalysisResult)
async def analyze_pdf(file: UploadFile = File(...)):
    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="File must be a PDF")

    file_bytes = await file.read()

    # 1. Extract Text, Figures, Formulas, and Tables
    text, figures, formulas, tables = await PDFService.extract_content_from_pdf(file_bytes)
    
    # 2. Call Gemini
    # Ensure API Key is set
    if not os.getenv("GEMINI_API_KEY"):
         raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured on server.")
    
    try:
        result = llm_service.analyze_content(text, figures, formulas, tables, file.filename)
        
        # 3. Call Grobid for Reference Validation
        '''
        try:
            grobid_suggestions = GrobidService.process_references(file_bytes, file.filename)
            if grobid_suggestions:
                result.suggestions.extend(grobid_suggestions)
                if not result.general_comments:
                    result.general_comments = ""
                result.general_comments += "\n\n**Reference Formatting Check (Grobid):** Checked references against style guidelines."
        except Exception as grobid_error:
            print(f"Grobid check failed: {grobid_error}")
        '''

        # 4. Call Metadata Check (Rule Based)
        try:
            metadata_suggestions = MetadataService.check_metadata(file_bytes)
            if metadata_suggestions:
                result.suggestions.extend(metadata_suggestions)
        except Exception as meta_error:
            print(f"Metadata check failed: {meta_error}")

        # 5. Call Visual Check (Figures, Colors)
        from service.visual_check_service import VisualCheckService
        try:
            visual_suggestions = VisualCheckService.check_visuals(file_bytes)
            if visual_suggestions:
                result.suggestions.extend(visual_suggestions)
        except Exception as visual_error:
            print(f"Visual check failed: {visual_error}")
            
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
