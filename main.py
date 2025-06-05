from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from jamaibase import JamAI, protocol as p
from pathlib import Path
import tempfile, os, logging

# ─── ENV ────────────────────────────────────────────────────────────────────────
load_dotenv()

CHAT_PROJECT_ID   = "proj_220f5118642fc87b23616090"
NOTES_PROJECT_ID  = "proj_16251a55cf8ddf5518f2cc21"
PAT               = "jamai_sk_99da212896c49785b4000524de0104e1fd6a63e5cbf0e1f1"

# ─── LOGGER ─────────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("hafizu-api")

# ─── JAMAI CLIENTS ─────────────────────────────────────────────────────────────
jamai_chat  = JamAI(project_id=CHAT_PROJECT_ID,  token=PAT)
jamai_notes = JamAI(project_id=NOTES_PROJECT_ID, token=PAT)

# ─── FASTAPI ────────────────────────────────────────────────────────────────────
app = FastAPI(title="Hafizu Assistant API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"]
)

# ─── MODELS ─────────────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    message: str
class ChatResponse(BaseModel):
    response: str
class NoteResponse(BaseModel):
    description: str

# ─── ROOT ───────────────────────────────────────────────────────────────────────
@app.get("/")
async def hello():
    return {"message": "Hello, welcome to the Hafizu Assistant AI!"}

# ─── CHAT ENDPOINT ─────────────────────────────────────────────────────────────
@app.post("/hafizu-blog/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    try:
        full = ""
        for chunk in jamai_chat.table.add_table_rows(
            table_type=p.TableType.chat,
            request=p.RowAddRequest(
                table_id="hafizu-assistant",
                data=[{"User": req.message}],
                stream=True,
            ),
        ):
            if isinstance(chunk, p.GenTableStreamChatCompletionChunk) and \
               chunk.output_column_name == "AI":
                full += chunk.choices[0].message.content
        return {"response": full}
    except Exception as err:
        log.exception("Chat error")
        raise HTTPException(500, str(err))

# ─── NOTES EXTRACTION ENDPOINT ─────────────────────────────────────────────────
VALID_EXT = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

@app.post("/extract-notes", response_model=NoteResponse)
async def extract_notes(file: UploadFile = File(...)):
    # Validate ext
    ext = Path(file.filename).suffix.lower()
    if ext not in VALID_EXT:
        raise HTTPException(400, f"Unsupported file type. Allowed: {', '.join(VALID_EXT)}")

    tmp_path = None
    try:
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        # Upload to JamAI (notes project)
        file_resp = jamai_notes.file.upload_file(tmp_path)

        # Add row to action table and fetch description
        tbl_resp = jamai_notes.table.add_table_rows(
            table_type=p.TableType.action,
            request=p.RowAddRequest(
                table_id="notes-extraction",
                data=[{"img": file_resp.uri}],
                stream=False,
            ),
        )
        desc = tbl_resp.rows[0].columns["description"].text
        return {"description": desc}

    except Exception as err:
        log.exception("Extract-notes error")
        raise HTTPException(500, str(err))
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
