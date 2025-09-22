from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from jamaibase import JamAI, protocol as p
from pathlib import Path
import os
import logging
import PyPDF2
import tempfile

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
            ),
        )
        ai_col = tbl_resp.rows[0].columns.get("AI")
        full_response = ai_col.text if hasattr(ai_col, "text") else str(ai_col)
        return {"response": full_response}
    except Exception as err:
        log.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(err))

# ─── NOTES EXTRACTION ENDPOINT ─────────────────────────────────────────────────
VALID_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# ─── ENDPOINT ───────────────────────────────────────────────────────────────
@app.post("/studai/extract-img", response_model=NoteResponse)
async def extract_notes(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in VALID_EXT:
        raise HTTPException(
            400, f"Unsupported file type. Allowed: {', '.join(VALID_EXT)}"
        )

    tmp_path = None
    try:
        # simpan fail sementara
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # upload ke JamAI
        file_resp = jamai_notes.file.upload_file(tmp_path)

        # proses di action table
        tbl_resp = jamai_notes.table.add_table_rows(
            table_type=p.TableType.action,
            request=p.RowAddRequest(
                table_id="extract-img",
                data=[{"img": file_resp.uri}],
                stream=False,
            ),
        )

        # ambil hasil
        cols = tbl_resp.rows[0].columns
        description = cols["description"].text if "description" in cols else ""
        # sesuaikan nama kolum di JamAI kalau lain
        extracted_text = cols["extracted_text"].text if "extracted_text" in cols else ""

        return {"description": description, "extracted_text": extracted_text}

    except Exception as err:
        log.exception("Extract-notes error")
        raise HTTPException(500, str(err))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)

class PdfResponse(BaseModel):
    flashcard_front: str
    flashcard_back: str
    definitions: str
    formulas: str

PDF_VALID_EXT = {".pdf"}

@app.post("/studai/extract-pdf", response_model=PdfResponse)
async def extract_pdf_alt(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in PDF_VALID_EXT:
        raise HTTPException(
            400, f"Unsupported file type. Only PDF files are allowed."
        )
    
    tmp_path = None
    try:
        # Save file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name
        
        # Extract text from PDF
        with open(tmp_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            extracted_text = ""
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() + "\n"
        
        if not extracted_text.strip():
            raise HTTPException(400, "Could not extract text from PDF. The PDF might be image-based or encrypted.")
        
        # Send to JamAI as text
        tbl_resp = jamai_notes.table.add_table_rows(
            table_type=p.TableType.action,
            request=p.RowAddRequest(
                table_id="extract-pdf",
                data=[{"document_text": extracted_text}],
                stream=False,
            ),
        )
        
        # Get results
        cols = tbl_resp.rows[0].columns
        flashcard_front = cols["flashcard_front"].text if "flashcard_front" in cols else ""
        flashcard_back = cols["flashcard_back"].text if "flashcard_back" in cols else ""
        definitions = cols["definitions"].text if "definitions" in cols else ""
        formulas = cols["formulas"].text if "formulas" in cols else ""
        
        return {
            "flashcard_front": flashcard_front,
            "flashcard_back": flashcard_back,
            "definitions": definitions,
            "formulas": formulas,
        }
        
    except Exception as err:
        log.exception("Extract-pdf error")
        raise HTTPException(500, str(err))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)