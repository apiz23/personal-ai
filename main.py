from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from jamaibase import JamAI, protocol as p
from pathlib import Path
import logging
import os

load_dotenv()

CHAT_PROJECT_ID = os.getenv("CHAT_PROJECT_ID")
NOTES_PROJECT_ID = os.getenv("NOTES_PROJECT_ID")
PAT = os.getenv("PAT")

if not all([CHAT_PROJECT_ID, NOTES_PROJECT_ID, PAT]):
    raise EnvironmentError("Missing environment variables for JamAI credentials!")

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hafizu-api")

jamai_chat = JamAI(project_id=CHAT_PROJECT_ID, token=PAT)
jamai_notes = JamAI(project_id=NOTES_PROJECT_ID, token=PAT)

app = FastAPI(title="Hafizu Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

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

@app.get("/")
async def hello():
    return {"message": "Hello, welcome to the Hafizu Assistant AI!"}

@app.get("/api")
async def api_hello():
    return {"message": "Hello, welcome to the Hafizu Assistant AI!"}

@app.post("/hafizu-blog/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        tbl_resp = jamai_chat.table.add_table_rows(
            table_type=p.TableType.chat,
            request=p.RowAddRequest(
                table_id="hafizu-assistant",
                data=[{"User": req.message}],
                stream=False,
            ),
        )
        ai_col = tbl_resp.rows[0].columns.get("AI")
        full_response = ai_col.text if hasattr(ai_col, "text") else str(ai_col)
        return {"response": full_response}
    except Exception as err:
        log.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(err))
