import os
import json

@mcp.tool()
def remove_memory(memory_id: str, agent_name: str = "Terry") -> str:
    """Delete a memory from your core memory using its ID. Use this if a fact is no longer true, or the user corrects you, or asks you to forget something.
    
    Args:
        memory_id: The exact ID of the memory to remove (e.g., 'M-1718912345').
        agent_name: The name of the agent to remove the memory from.
    """
    memories_file = os.path.join(AI_WORKSPACE_DIR, "agents", agent_name, "KEY_MEMORIES.json")
    try:
        with open(memories_file, "r", encoding="utf-8") as f:
            memories = json.load(f)
    except Exception:
        return "Error: Memory file not found or corrupted."
    initial_len = len(memories)
    memories = [m for m in memories if m.get("id") != memory_id]
    if len(memories) == initial_len:
        return f"Error: Memory ID '{memory_id}' not found."
    with open(memories_file, "w", encoding="utf-8") as f:
        json.dump(memories, f, indent=4)
    return f"Successfully deleted memory [{memory_id}]."
