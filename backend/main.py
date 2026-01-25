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

@app.post("/analyze", response_model=AnalysisResult)
async def analyze_pdf(file: UploadFile = File(...)):
    # 1. Extract Text, Figures, and Formulas
    text, figures, formulas = await PDFService.extract_content_from_pdf(file)
    
    # 2. Call Gemini
    # Ensure API Key is set
    if not os.getenv("GEMINI_API_KEY"):
         raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured on server.")
    
    try:
        result = llm_service.analyze_content(text, figures, formulas, file.filename)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
