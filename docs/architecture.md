# Architecture
```mermaid
flowchart LR
Input-->Perception-->WorldModel-->Reasoner-->Planner-->Verifier-->Action
WorldModel<-->SemanticMemory
WorldModel<-->EpisodicMemory
Reasoner<-->RDFStore
```
