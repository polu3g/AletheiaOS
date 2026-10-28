from app.memory.episodic import EpisodicMemory
from app.memory.semantic import SemanticMemory
from app.planning.planner import GoalPlanner
from app.logging.trace import TraceLogger
class CognitiveEngine:
    def __init__(self):
      self.e=EpisodicMemory(); self.s=SemanticMemory(); self.p=GoalPlanner(); self.t=TraceLogger()
    def process(self,text):
      self.e.events.append(text)
      inf='road_slippery' if 'wet' in text.lower() and 'road' in text.lower() else 'observation'
      self.s.facts.append(inf)
      plan=self.p.plan(inf)
      self.t.log({'input':text,'inference':inf})
      return {'input':text,'inference':inf,'plan':plan}
