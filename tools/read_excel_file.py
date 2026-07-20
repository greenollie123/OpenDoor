import os
import pandas as pd

@mcp.tool()
def read_excel_file(relative_path: str, sheet_name: str = None) -> str:
    """Reads the contents of an Excel file (.xlsx or .xls) and returns it as a formatted Markdown string.
    
    Args:
        relative_path: The relative path of the Excel file inside the workspace.
        sheet_name: Optional. The name of the specific sheet to read. If not specified, reads all sheets.
    """
    safe_path = os.path.abspath(os.path.join(AI_WORKSPACE_DIR, relative_path))
    if not safe_path.startswith(os.path.abspath(AI_WORKSPACE_DIR)):
        return "Error: Access denied."
    if not os.path.exists(safe_path):
        return f"Error: File '{relative_path}' not found."
    if os.path.isdir(safe_path):
        return f"Error: The path '{relative_path}' is a directory, not a file. Please specify a file path including a filename (e.g. 'agents/JARVIS/spreadsheet.xlsx')."
    
    try:
        # Load file using pandas ExcelFile in a context manager to auto-close handles
        with pd.ExcelFile(safe_path) as xl:
            sheets = xl.sheet_names
            
            output = []
            if sheet_name:
                if sheet_name not in sheets:
                    return f"Error: Sheet '{sheet_name}' not found. Available sheets: {', '.join(sheets)}"
                sheets_to_read = [sheet_name]
            else:
                sheets_to_read = sheets
                
            for sheet in sheets_to_read:
                df = pd.read_excel(xl, sheet_name=sheet)
                df = df.fillna("")
                output.append(f"### Sheet: {sheet}")
                if df.empty:
                    output.append("*(This sheet is empty)*")
                else:
                    total_rows = len(df)
                    if total_rows > 100:
                        df_subset = df.head(100)
                        output.append(df_subset.to_markdown(index=False))
                        output.append(f"\n*(Truncated: showing first 100 of {total_rows} rows. Use sheet filtering if needed.)*")
                    else:
                        output.append(df.to_markdown(index=False))
                output.append("")
                
            return "\n".join(output)
    except Exception as e:
        return f"Error reading Excel file: {str(e)}"
