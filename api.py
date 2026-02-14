from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from agent import DoctorAppointmentAgent
from langchain_core.messages import HumanMessage
import os
from utils.config import get_recursion_limit
from utils.logger import get_logger

os.environ.pop("SSL_CERT_FILE", None)


logger = get_logger(__name__)

app = FastAPI()

# Define Pydantic model to accept request body
class UserQuery(BaseModel):
    id_number: int = Field(ge=1000000, le=99999999)
    messages: str = Field(min_length=1)

agent = DoctorAppointmentAgent()
app_graph = agent.workflow()


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.post("/execute")
def execute_agent(user_input: UserQuery):
    logger.info("Received execute request for id_number=%s", user_input.id_number)
    try:
        query_data = {
            "messages": [HumanMessage(content=user_input.messages.strip())],
            "id_number": user_input.id_number,
            "next": "",
            "query": "",
            "current_reasoning": "",
        }

        response = app_graph.invoke(query_data, config={"recursion_limit": get_recursion_limit()})
        messages = response.get("messages", [])
        assistant_text = messages[-1].content if messages else "No response generated."

        return {
            "response": assistant_text,
            "route": response.get("next", ""),
            "reasoning": response.get("current_reasoning", ""),
        }
    except Exception as exc:
        logger.exception("Failed to execute agent")
        raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(exc)}")
