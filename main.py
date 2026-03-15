from fastapi import FastAPI
from routes import LLM as llm

app = FastAPI()

app.include_router(llm.router, prefix='/llm')

