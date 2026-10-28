from app.cognitive.engine import CognitiveEngine
def test_reason():
 e=CognitiveEngine();
 assert e.process('road is wet')['inference']=='road_slippery'
