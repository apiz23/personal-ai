from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from jamaibase import JamAI, protocol as p
import time
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables
load_dotenv()

# Configuration
PROJECT_ID = "proj_043e7a98a1a2fb9b967db88f"
PAT = "jamai_sk_99da212896c49785b4000524de0104e1fd6a63e5cbf0e1f1"
TABLE_TYPE_CHAT = p.TableType.chat
TABLE_TYPE_ACTION = p.TableType.action
OPENER = "Hello! How can I help you today?"

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize JamAI client
jamai = JamAI(project_id=PROJECT_ID, token=PAT)

@app.get("/")
async def hello():
    """Returns a simple greeting."""
    return {"message": "Hello, welcome to the Health Sync API!"}

# Chat session management
chat_sessions = {}

# Create a new chat session
def create_new_chat():
    """Creates a new chat session and returns the table ID."""
    timestamp = int(time.time())
    new_table_id = f"Chat_{timestamp}"
    try:
        jamai.table.duplicate_table(
            table_type=TABLE_TYPE_CHAT,
            table_id_src="SyncMate",
            table_id_dst=new_table_id,
            include_data=True,
            create_as_child=True
        )
        return new_table_id
    except Exception as e:
        return None

# Define models for chat
class ChatRequest(BaseModel):
    session_id: str
    message: str

class ChatResponse(BaseModel):
    response: str

# Define models for symptom analysis
class SymptomsRequest(BaseModel):
    symptoms: str

class SymptomsResponse(BaseModel):
    possible_disease: str
    confidence_level: str
    suggested_action: str

# Chat endpoint
@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Handles chat requests from the frontend."""
    session_id = request.session_id
    message = request.message

    # Create a new chat session if it doesn't exist
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

# Symptom analysis endpoint
@app.post("/analyze", response_model=SymptomsResponse)
async def analyze_symptoms(request: SymptomsRequest):
    """Handles symptom analysis requests."""
    try:
        if not request.symptoms.strip():
            raise ValueError("Symptoms must be a non-empty string.")

        print(f"Analyzing symptoms: {request.symptoms}")

        response = jamai.table.add_table_rows(
            table_type=TABLE_TYPE_ACTION,
            request=p.RowAddRequest(
                table_id="medical_analysis",
                data=[{"analyze_symptoms": request.symptoms}],
                stream=False,
            ),
        )

        # print("Response:", response)
        # print("Type of Response:", type(response))
        # print("Attributes of Response:", dir(response))

        if isinstance(response, tuple):
            result = response[0]
        else:
            result = response

        if hasattr(result, 'rows') and result.rows:
            row = result.rows[0]
            if hasattr(row, 'columns') and row.columns:
                possible_disease = row.columns.get("possible_disease")
                confidence_level = row.columns.get("confidence_level")
                suggested_action = row.columns.get("suggested_action")

                # Convert to strings if necessary
                possible_disease = possible_disease.text if hasattr(possible_disease, "text") else str(possible_disease)
                confidence_level = confidence_level.text if hasattr(confidence_level, "text") else str(confidence_level)
                suggested_action = suggested_action.text if hasattr(suggested_action, "text") else str(suggested_action)

            else:
                raise ValueError("Unexpected response format: 'columns' attribute not found.")
        else:
            raise ValueError("Unexpected response format: 'rows' attribute not found or empty.")

        return SymptomsResponse(
            possible_disease=possible_disease,
            confidence_level=confidence_level,
            suggested_action=suggested_action,
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))