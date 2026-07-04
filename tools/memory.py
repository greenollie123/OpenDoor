@mcp.tool()
def add_memory(text: str, expiry_date: str = None, agent_name: str = "Terry") -> str:
    """Save an important fact, preference, or event to your core memory. Use this when the user mentions something you should remember for future sessions.
    
    Args:
        text: The fact or preference to remember.
        expiry_date: Optional. The date this memory becomes irrelevant (YYYY-MM-DD). Leave blank or null for permanent facts.
        agent_name: The name of the agent to associate this memory with.
    """
    memories_file = os.path.join(AI_WORKSPACE_DIR, "agents", agent_name, "KEY_MEMORIES.json")
    os.makedirs(os.path.dirname(memories_file), exist_ok=True)
    try:
        with open(memories_file, "r", encoding="utf-8") as f:
            memories = json.load(f)
    except Exception:
        memories = []

    new_vector = get_embedding(text)
    if new_vector:
        for m in memories:
            if "embedding" in m:
                similarity = cosine_similarity(new_vector, m["embedding"])
                if similarity > 0.85:
                    m["text"] = text
                    m["embedding"] = new_vector
                    if expiry_date:
                        m["expiry_date"] = expiry_date
                    with open(memories_file, "w", encoding="utf-8") as f:
                        json.dump(memories, f, indent=4)
                    return f"Detected existing similar memory. Updated memory entry [{m['id']}]."

    new_id = f"M-{int(datetime.now().timestamp())}"
    new_mem = {"id": new_id, "text": text, "expiry_date": expiry_date, "embedding": new_vector}
    memories.append(new_mem)
    with open(memories_file, "w", encoding="utf-8") as f:
        json.dump(memories, f, indent=4)
    return f"Successfully recorded new semantic memory with ID [{new_id}]."

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
