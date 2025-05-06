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
    return {"message": "Hello, welcome to the Hafizu Assistant AI!"}

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    response: str

@app.post("/hafizu-blog/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handles chat requests from the frontend (no session ID required)."""
    message = request.message

    try:
        full_response = ""
        for chunk in jamai.table.add_table_rows(
            table_type=TABLE_TYPE_CHAT,
            request=p.RowAddRequest(
                table_id="hafizu-assistant", 
                data=[{"User": message}],
                stream=True
            )
        ):
            if isinstance(chunk, p.GenTableStreamChatCompletionChunk):
                if chunk.output_column_name == 'AI':
                    full_response += chunk.choices[0].message.content
        return {"response": full_response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
