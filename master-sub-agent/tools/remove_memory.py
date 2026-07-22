import os
import json

@mcp.tool()
def remove_memory(memory_id: str, agent_name: str = "Main") -> str:
    """Delete a memory from temporary session memory using its ID.
    
    Args:
        memory_id: The exact ID of the memory to remove (e.g., 'M-1718912345').
        agent_name: The name of the agent associated with the memory.
    """
    from tools.add_memory import SESSION_MEMORIES
    memories = SESSION_MEMORIES.get(agent_name, [])
    initial_len = len(memories)
    updated = [m for m in memories if m.get("id") != memory_id]
    if len(updated) == initial_len:
        return f"Error: Memory ID '{memory_id}' not found in session memories."
    SESSION_MEMORIES[agent_name] = updated
    return f"Successfully removed session memory [{memory_id}]."

