using System;
using System.Diagnostics;
using System.IO;
using System.Windows.Forms;

internal static class WeeklyReportLauncher
{
    [STAThread]
    private static void Main()
    {
        string projectPath = AppDomain.CurrentDomain.BaseDirectory;
        string scriptPath = Path.Combine(projectPath, "Start-WeeklyReportLan.ps1");
        try
        {
            if (!File.Exists(scriptPath))
            {
                throw new FileNotFoundException("未找到周报启动脚本", scriptPath);
            }

            Process.Start(new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File \"" + scriptPath + "\"",
                WorkingDirectory = projectPath,
                UseShellExecute = false,
                CreateNoWindow = true
            });
        }
        catch (Exception error)
        {
            MessageBox.Show("周报分析启动失败：\n" + error.Message, "周报分析", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }
    }
}
