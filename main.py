from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from jamaibase import JamAI, protocol as p
from pathlib import Path
import os
import logging
import PyPDF2

# ─── ENV ────────────────────────────────────────────────────────────────────────
load_dotenv()

CHAT_PROJECT_ID = "proj_220f5118642fc87b23616090"
NOTES_PROJECT_ID = "proj_16251a55cf8ddf5518f2cc21"
PAT = "jamai_sk_99da212896c49785b4000524de0104e1fd6a63e5cbf0e1f1"

if not all([CHAT_PROJECT_ID, NOTES_PROJECT_ID, PAT]):
    raise EnvironmentError("Missing environment variables for JamAI credentials!")

# ─── LOGGER ─────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hafizu-api")

# ─── JAMAI CLIENTS ─────────────────────────────────────────────────────────────
jamai_chat = JamAI(project_id=CHAT_PROJECT_ID, token=PAT)
jamai_notes = JamAI(project_id=NOTES_PROJECT_ID, token=PAT)

# ─── FASTAPI ────────────────────────────────────────────────────────────────────
app = FastAPI(title="Hafizu Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# ─── MODELS ─────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

class NoteResponse(BaseModel):
    description: str
    extracted_text: str

class PdfResponse(BaseModel):
    flashcard_front: str
    flashcard_back: str
    definitions: str
    formulas: str

# ─── ROOT ───────────────────────────────────────────────────────────────────────
@app.get("/")
async def hello():
    return {"message": "Hello, welcome to the Hafizu Assistant AI!"}

@app.get("/api")
async def api_hello():
    return {"message": "Hello, welcome to the Hafizu Assistant AI!"}

# ─── CHAT ENDPOINT ─────────────────────────────────────────────────────────────
@app.post("/hafizu-blog/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        tbl_resp = jamai_chat.table.add_table_rows(
            table_type=p.TableType.chat,
            request=p.RowAddRequest(
                table_id="hafizu-assistant",
                data=[{"User": req.message}],
                stream=False  # ← Vercel-safe
            ),
        )
        ai_col = tbl_resp.rows[0].columns.get("AI")
        full_response = ai_col.text if hasattr(ai_col, "text") else str(ai_col)
        return {"response": full_response}
    except Exception as err:
        log.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(err))

# ─── NOTES EXTRACTION ENDPOINT ─────────────────────────────────────────────────
VALID_IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

@app.post("/studai/extract-img", response_model=NoteResponse)
async def extract_notes(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in VALID_IMG_EXT:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Allowed: {', '.join(VALID_IMG_EXT)}"
        )
    try:
        file_bytes = await file.read()
        file_resp = jamai_notes.file.upload_bytes(file_bytes, filename=file.filename)

        tbl_resp = jamai_notes.table.add_table_rows(
            table_type=p.TableType.action,
            request=p.RowAddRequest(
                table_id="extract-img",
                data=[{"img": file_resp.uri}],
                stream=False,
            ),
        )
        cols = tbl_resp.rows[0].columns
        description = cols.get("description", type('obj', (), {'text': ''})()).text
        extracted_text = cols.get("extracted_text", type('obj', (), {'text': ''})()).text
        return {"description": description, "extracted_text": extracted_text}
    except Exception as err:
        log.exception("Extract-notes error")
        raise HTTPException(status_code=500, detail=str(err))

# ─── PDF EXTRACTION ENDPOINT ───────────────────────────────────────────────────
PDF_VALID_EXT = {".pdf"}

@app.post("/studai/extract-pdf", response_model=PdfResponse)
async def extract_pdf(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in PDF_VALID_EXT:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Only PDF files are allowed."
        )
    try:
        file_bytes = await file.read()
        from io import BytesIO
        pdf_file = BytesIO(file_bytes)

        extracted_text = ""
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                extracted_text += text + "\n"

        if not extracted_text.strip():
            raise HTTPException(
                status_code=400,
                detail="Could not extract text from PDF. The PDF might be image-based or encrypted."
            )

        tbl_resp = jamai_notes.table.add_table_rows(
            table_type=p.TableType.action,
            request=p.RowAddRequest(
                table_id="extract-pdf",
                data=[{"document_text": extracted_text}],
                stream=False,
            ),
        )

        cols = tbl_resp.rows[0].columns
        return PdfResponse(
            flashcard_front=cols.get("flashcard_front", type('obj', (), {'text': ''})()).text,
            flashcard_back=cols.get("flashcard_back", type('obj', (), {'text': ''})()).text,
            definitions=cols.get("definitions", type('obj', (), {'text': ''})()).text,
            formulas=cols.get("formulas", type('obj', (), {'text': ''})()).text,
        )

    except Exception as err:
        log.exception("Extract-pdf error")
        raise HTTPException(status_code=500, detail=str(err))

# ─── VERCEL HANDLER ─────────────────────────────────────────────────────────────
handler = app
