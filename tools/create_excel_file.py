import os
from openpyxl import Workbook

@mcp.tool()
def create_excel_file(relative_path: str, sheet_name: str = "Sheet1", headers: list = None) -> str:
    """Create a new Excel file (.xlsx) with an optional sheet name and headers.
    
    Args:
        relative_path: The relative path where the Excel file should be created.
        sheet_name: The name of the initial sheet (default is 'Sheet1').
        headers: Optional. A list of header names to write in the first row.
    """
    safe_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not safe_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    if os.path.isdir(safe_path):
        return f"Error: The path '{relative_path}' is an existing directory. Please specify a file path including a filename (e.g. 'agents/JARVIS/spreadsheet.xlsx')."
    
    try:
        # Create directories if they do not exist
        os.makedirs(os.path.dirname(safe_path), exist_ok=True)
        
        wb = Workbook()
        ws = wb.active
        ws.title = sheet_name
        
        if headers:
            ws.append(headers)
            
        wb.save(safe_path)
        wb.close()
        return f"Successfully created Excel file at '{relative_path}' with sheet '{sheet_name}'."
    except Exception as e:
        return f"Error creating Excel file: {str(e)}"
