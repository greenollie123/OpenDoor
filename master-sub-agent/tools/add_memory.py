import os
import json
from datetime import datetime

# Session temporary memory store
SESSION_MEMORIES = {}

@mcp.tool()
def add_memory(text: str, expiry_date: str = None, agent_name: str = "Main") -> str:
    """Save an important fact or note to temporary session memory for the current task.
    
    Args:
        text: The fact or note to remember.
        expiry_date: Optional. The date this memory becomes irrelevant (YYYY-MM-DD).
        agent_name: The name of the agent to associate this memory with.
    """
    if agent_name not in SESSION_MEMORIES:
        SESSION_MEMORIES[agent_name] = []
        
    memories = SESSION_MEMORIES[agent_name]

    new_vector = get_embedding(text) if callable(globals().get("get_embedding")) else None
    if new_vector:
        for m in memories:
            if "embedding" in m and m["embedding"]:
                similarity = cosine_similarity(new_vector, m["embedding"]) if callable(globals().get("cosine_similarity")) else 0
                if similarity > 0.85:
                    m["text"] = text
                    m["embedding"] = new_vector
                    if expiry_date:
                        m["expiry_date"] = expiry_date
                    return f"Updated existing temporary session memory [{m['id']}]."

    new_id = f"M-{int(datetime.now().timestamp())}"
    new_mem = {"id": new_id, "text": text, "expiry_date": expiry_date, "embedding": new_vector}
    memories.append(new_mem)
    return f"Recorded temporary session memory [{new_id}]: '{text}'."

