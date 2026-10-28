from fastapi import FastAPI
from app.cognitive.engine import CognitiveEngine
app=FastAPI(title="AletheiaOS")
engine=CognitiveEngine()
@app.get('/')
def root(): return {'status':'ok'}
@app.post('/reason')
def reason(text:str): return engine.process(text)
