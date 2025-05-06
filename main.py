from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from jamaibase import JamAI, protocol as p
import time
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

PROJECT_ID = "proj_220f5118642fc87b23616090"
PAT = "jamai_sk_99da212896c49785b4000524de0104e1fd6a63e5cbf0e1f1"
TABLE_TYPE_CHAT = p.TableType.chat
TABLE_TYPE_ACTION = p.TableType.action
OPENER = "Hello! How can I help you today?"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jamai = JamAI(project_id=PROJECT_ID, token=PAT)

@app.get("/")
async def hello():
    """Returns a simple greeting."""
    return {"message": "Hello, welcome to the Health Sync API!"}

chat_sessions = {}

def create_new_chat():
    """Creates a new chat session and returns the table ID."""
    timestamp = int(time.time())
    new_table_id = f"Chat_{timestamp}"
    try:
        jamai.table.duplicate_table(
            table_type=TABLE_TYPE_CHAT,
            table_id_src="hafizu-assistant",
            table_id_dst=new_table_id,
            include_data=True,
            create_as_child=True
        )
        return new_table_id
    except Exception as e:
        return None

class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    response: str

class SymptomsRequest(BaseModel):
    symptoms: str

class SymptomsResponse(BaseModel):
    possible_disease: str
    confidence_level: str
    suggested_action: str

@app.post("/hafizu-blog/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handles chat requests from the frontend."""
    session_id = request.session_id
    message = request.message

    if session_id not in chat_sessions:
        table_id = create_new_chat()
        if not table_id:
            raise HTTPException(status_code=500, detail="Error creating new chat session")
        chat_sessions[session_id] = table_id

    table_id = chat_sessions[session_id]

    full_response = ""
    try:
        for chunk in jamai.table.add_table_rows(
            table_type=TABLE_TYPE_CHAT,
            request=p.RowAddRequest(
                table_id=table_id,
                data=[{"User": message}],
                stream=True
            )
        ):
            if isinstance(chunk, p.GenTableStreamChatCompletionChunk):
                if chunk.output_column_name == 'AI':
                    full_response += chunk.choices[0].message.content
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return {"response": full_response}