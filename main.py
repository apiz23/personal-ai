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

