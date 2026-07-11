# Custom Tools in the `tools/` Folder

This guide explains how to create MCP-style custom tools in the workspace `tools/` directory.

## 1) Pick the tool name and file name
- Create a new file under `tools/`, e.g. `tools/my_tool.py`.
- The tool function name inside the file should match the tool name you want (e.g. `def my_tool(...)`).

## 2) Follow the existing tool layout
Open any existing tool in `tools/` (for example `tools/weather.py`) and follow the same structure:
- Imports
- Function definition
- Decorator

### Required decorator
All tools should be decorated with:

```python
@mcp.tool()
def my_tool(...):
    ...
```

This is what registers the function as an MCP tool.

## 3) Define inputs (arguments)
- Use standard Python function parameters.
- Add type hints where useful.
- Include a docstring describing arguments and return values.

Example:

```python
@mcp.tool()
def add(a: int, b: int) -> int:
    """Return a + b."""
    return a + b
```

## 4) Return a string (or a simple serializable value)
Look at existing tools for guidance on return types. Many return `str`.

If you return non-string data, make sure it can be serialized/printed cleanly by the MCP host. Safest option: return a `str`.

## 5) Use the workspace tools as needed
If your custom tool needs to interact with the workspace, follow patterns used in other tool files (e.g., path safety checks).

## 6) Ensure the tool is imported/visible
The runtime typically discovers tools from the `tools/` directory based on filenames and the `@mcp.tool()` decorator. Keep the file in the `tools/` directory and ensure the decorated function exists.

## 7) Test the tool
After adding the file and function:
- Ask the system to call the tool by name.
- Verify the output matches expectations.

## Example: `get_random_joke`
A minimal example that fetches and returns a string:

```python
import json
import urllib.request

@mcp.tool()
def get_random_joke() -> str:
    """Fetch a random joke from https://icanhazdadjoke.com/ and return it as a string."""
    url = "https://icanhazdadjoke.com/"
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    return str(data.get("joke", ""))
```

## Notes / Common mistakes
- Missing the `@mcp.tool()` decorator.
- Trying to import `mcp` directly (it is injected dynamically, doing `import mcp` will fail since `mcp` is not a pip package, but the fastmcp decorator).
- Placing the tool file outside `master/working/custom-tools/`.
- Hardcoding file paths using `os.getcwd()` instead of referencing the injected `AI_WORKSPACE_DIR` variable.
- `AI_WORKSPACE_DIR`: The absolute path to the active agent workspace (`master/working`). Always prefix file operations (reads/writes) with this path to ensure data is saved in the correct place.