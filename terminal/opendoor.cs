using System;
using System.Diagnostics;
using System.IO;
using System.Text;

class Program
{
    static int Main(string[] args)
    {
        // Intercept Ctrl+C to prevent the C# wrapper from exiting prematurely.
        // This ensures it waits for the child Python process to finish cleanup.
        Console.CancelKeyPress += (sender, e) => {
            e.Cancel = true;
        };

        string currentDir = AppDomain.CurrentDomain.BaseDirectory;
        if (currentDir.EndsWith("\\"))
        {
            currentDir = currentDir.Substring(0, currentDir.Length - 1);
        }
        string rootDir = Path.GetFullPath(Path.Combine(currentDir, ".."));

        string pythonExe = "python";
        string venvPython = Path.Combine(rootDir, "venv", "Scripts", "python.exe");
        if (File.Exists(venvPython))
        {
            pythonExe = venvPython;
        }

        string action = args.Length > 0 ? args[0].ToLower() : "";
        string scriptPath;

        if (action == "setup")
        {
            scriptPath = Path.Combine(currentDir, "setup.py");
        }
        else if (action == "configure" || action == "config")
        {
            scriptPath = Path.Combine(currentDir, "config.py");
        }
        else if (action == "update")
        {
            scriptPath = Path.Combine(currentDir, "update.py");
        }
        else if (action == "launch" || action == "start" || action == "run" || action == "server")
        {
            scriptPath = Path.Combine(rootDir, "main.py");
        }
        else
        {
            scriptPath = Path.Combine(currentDir, "terminal.py");
        }

        // Build command line arguments string using standard Windows escaping rules
        var sb = new StringBuilder();
        sb.Append(EscapeArgument(scriptPath));

        foreach (var arg in args)
        {
            sb.Append(" ");
            sb.Append(EscapeArgument(arg));
        }

        var startInfo = new ProcessStartInfo
        {
            FileName = pythonExe,
            Arguments = sb.ToString(),
            UseShellExecute = false,
            CreateNoWindow = false
        };

        try
        {
            using (var process = Process.Start(startInfo))
            {
                process.WaitForExit();
                return process.ExitCode;
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("Error executing OpenDoor: " + ex.Message);
            return 1;
        }
    }

    static string EscapeArgument(string arg)
    {
        if (string.IsNullOrEmpty(arg)) return "\"\"";

        bool needsQuotes = arg.Contains(" ") || arg.Contains("\t") || arg.Contains("\"");
        if (!needsQuotes) return arg;

        var sb = new StringBuilder();
        sb.Append('"');

        for (int i = 0; i < arg.Length; i++)
        {
            char c = arg[i];
            if (c == '\\')
            {
                int numBackslashes = 1;
                while (i + 1 < arg.Length && arg[i + 1] == '\\')
                {
                    numBackslashes++;
                    i++;
                }

                if (i + 1 == arg.Length)
                {
                    sb.Append('\\', numBackslashes * 2);
                }
                else if (arg[i + 1] == '"')
                {
                    sb.Append('\\', numBackslashes * 2 + 1);
                }
                else
                {
                    sb.Append('\\', numBackslashes);
                }
            }
            else if (c == '"')
            {
                sb.Append('\\');
                sb.Append('"');
            }
            else
            {
                sb.Append(c);
            }
        }

        sb.Append('"');
        return sb.ToString();
    }
}
