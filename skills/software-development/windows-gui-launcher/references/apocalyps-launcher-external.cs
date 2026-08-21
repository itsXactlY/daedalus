// DayZ Launcher — External Game Folder (Apocalyps) + Moddata Folder
// Launcher at /games/Launcher_Build/, Game at /games/Apocalyps/, Mods at /games/Apocalyps/moddata/
// Built on Linux (.NET 10 cross-compile), deployed to Windows

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace DayZLauncher;

static class Program
{
    [STAThread]
    static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new LauncherForm());
    }
}

class LauncherForm : Form
{
    readonly string ConfigPath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "config.json");
    
    // Paths resolved RELATIVE to launcher exe:
    // Launcher: /games/Launcher_Build/DayZLauncher.exe
    // Game:     /games/Apocalyps/DayZ_x64.exe
    // Mods:     /games/Apocalyps/moddata/@ModName
    readonly string DayzExe = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"..\Apocalyps\DayZ_x64.exe"));
    readonly string ModsBase = Path.GetFullPath(Path.Combine(AppDomain.CurrentDomain.BaseDirectory, @"..\Apocalyps\moddata"));

    // HARDCODED — integrity is non-negotiable
    const string ExpectedSha512 = "51c49fb7e2f0cb2fd93821684c27bc8dcea29498c5b9740ed1105ed1ebb1c319c13e795b384c3ea91f483ff89da9e588cb1e07bc6666628d74b0f6be7dc9cdc1";
    const string ServerHost = "playtest.mazemaker.online";
    const string ServerPort = "2302";

    TextBox txtName = new TextBox();
    Button btnPlay = new Button();
    Label lblStatus = new Label();

    // Only the 36 mods that the CLIENT actually needs (no server-only mods)
    readonly string[] ModFolders = {
        "@CF", "@Dabs Framework", "@Dogtags", "@CarCover", "@BodyBags",
        "@Code Lock", "@DrugsPlus", "@TruckFixV2", "@MuchCarKey",
        "@BuilderItems", "@MuchFramework", "@MuchStuffPack", "@MuchStuffPackFix",
        "@VPPAdminTools", "@Breachingcharge", "@BaseBuildingPlus",
        "@Wilmas BBP Item Drop Fix", "@Care Packages V2", "@RaG_Vehicle_Pack",
        "@Nehr_Pickup_Lada", "@VPPNotifications", "@VirtualGarageFull",
        "@MaharlikaPH_Boats", "@Forward Operator Gear", "@MMG - Mightys Military Gear",
        "@Cl0ud's Military Gear", "@WindstridesClothingPack",
        "@Uncuepas Civilian Clothing", "@CannabisPlus Experimental", "@A6",
        "@Autostack", "@Heli", "@VanillaPPMap", "@munghard",
        "@Inventory Move Sounds", "@bedrespawn", "3649957186", "3649959402"
    };

    public LauncherForm()
    {
        Text = "DayZ Launcher";
        Size = new Size(420, 240);
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.FixedSingle;
        MaximizeBox = false;
        BackColor = Color.FromArgb(30, 30, 35);

        BuildUI();
        LoadConfig();
    }

    void BuildUI()
    {
        Font font = new Font("Segoe UI", 9.5f);
        Color labelColor = Color.FromArgb(200, 200, 210);
        Color inputBack = Color.FromArgb(45, 45, 50);
        Color inputFore = Color.White;
        Color accent = Color.FromArgb(0, 160, 220);

        var lblName = new Label { Text = "Player Name", ForeColor = labelColor, Font = font, AutoSize = true, Left = 20, Top = 30 };
        txtName.Left = 130; txtName.Top = 27; txtName.Width = 240; txtName.Font = font;
        txtName.BackColor = inputBack; txtName.ForeColor = inputFore; txtName.BorderStyle = BorderStyle.FixedSingle;

        // Placeholder behavior: gray "John Doe" clears on focus, restores if empty on blur
        txtName.Text = "John Doe";
        txtName.ForeColor = Color.FromArgb(150, 150, 160);
        txtName.Enter += (s, e) => {
            if (txtName.Text == "John Doe") { txtName.Text = ""; txtName.ForeColor = inputFore; }
        };
        txtName.Leave += (s, e) => {
            if (string.IsNullOrWhiteSpace(txtName.Text)) { txtName.Text = "John Doe"; txtName.ForeColor = Color.FromArgb(150, 150, 160); }
        };

        // Server info as label (not editable — hardcoded in connect string)
        var lblServer = new Label { Text = $"Server: {ServerHost}:{ServerPort}", ForeColor = Color.FromArgb(140, 140, 150), Font = font, AutoSize = true, Left = 20, Top = 75 };

        btnPlay.Text = "CONNECT";
        btnPlay.Left = 20; btnPlay.Top = 115; btnPlay.Width = 360; btnPlay.Height = 48;
        btnPlay.Font = new Font("Segoe UI", 11f, FontStyle.Bold);
        btnPlay.BackColor = accent; btnPlay.ForeColor = Color.White; btnPlay.FlatStyle = FlatStyle.Flat;
        btnPlay.FlatAppearance.BorderSize = 0;
        btnPlay.Click += BtnPlay_Click;

        lblStatus.Text = "";
        lblStatus.ForeColor = Color.FromArgb(180, 180, 190);
        lblStatus.Font = font;
        lblStatus.AutoSize = false;
        lblStatus.Left = 20; lblStatus.Top = 175; lblStatus.Width = 360; lblStatus.Height = 30;
        lblStatus.TextAlign = ContentAlignment.MiddleCenter;

        Controls.AddRange(new Control[] { lblName, txtName, lblServer, btnPlay, lblStatus });
    }

    void LoadConfig()
    {
        if (File.Exists(ConfigPath))
        {
            try
            {
                string json = File.ReadAllText(ConfigPath);
                var cfg = JsonSerializer.Deserialize<Config>(json);
                if (cfg != null && !string.IsNullOrEmpty(cfg.PlayerName))
                    txtName.Text = cfg.PlayerName;
            }
            catch { }
        }
    }

    void SaveConfig()
    {
        var cfg = new Config { PlayerName = name };
        var options = new JsonSerializerOptions { WriteIndented = true };
        File.WriteAllText(ConfigPath, JsonSerializer.Serialize(cfg, options));
    }

    string name => txtName.Text.Trim();

    async void BtnPlay_Click(object sender, EventArgs e)
    {
        string trimmedName = name;

        // Block placeholder and "player" (case-insensitive)
        if (string.IsNullOrWhiteSpace(trimmedName)
            || trimmedName.Equals("John Doe", StringComparison.OrdinalIgnoreCase)
            || trimmedName.Equals("player", StringComparison.OrdinalIgnoreCase))
        {
            lblStatus.Text = "Eigenen Namen eingeben (nicht \"John Doe\" oder \"player\").";
            lblStatus.ForeColor = Color.FromArgb(255, 180, 80);
            return;
        }

        btnPlay.Enabled = false;
        lblStatus.Text = "Prüfe DayZ_x64.exe...";
        lblStatus.ForeColor = Color.FromArgb(180, 180, 190);
        await Task.Yield();

        if (!File.Exists(DayzExe))
        {
            lblStatus.Text = $"DayZ_x64.exe nicht gefunden: {DayzExe}";
            lblStatus.ForeColor = Color.FromArgb(255, 100, 100);
            btnPlay.Enabled = true;
            return;
        }

        string actualHash = ComputeSha512(DayzExe);
        if (ExpectedSha512 != "SET_AFTER_COMPUTE" && !actualHash.Equals(ExpectedSha512, StringComparison.OrdinalIgnoreCase))
        {
            lblStatus.Text = "SHA512 MISMATCH — DayZ_x64.exe verändert/korrupt.";
            lblStatus.ForeColor = Color.FromArgb(255, 100, 100);
            btnPlay.Enabled = true;
            return;
        }

        lblStatus.Text = "SHA512 OK. Starte DayZ...";
        lblStatus.ForeColor = Color.FromArgb(100, 220, 100);
        await Task.Delay(300);

        // Save config ONLY after validation passes
        SaveConfig();

        // Build -mod= string from full paths in moddata folder
        var modPaths = new List<string>();
        foreach (string folder in ModFolders)
        {
            string fullPath = Path.Combine(ModsBase, folder);
            if (Directory.Exists(fullPath) || File.Exists(fullPath))
                modPaths.Add(fullPath);
        }

        string modString = string.Join(";", modPaths);
        string args = $"-connect={ServerHost} -port={ServerPort} -name=\"{name}\" -mod=\"{modString}\"";

        var psi = new ProcessStartInfo
        {
            FileName = DayzExe,
            Arguments = args,
            WorkingDirectory = Path.GetDirectoryName(DayzExe),
            UseShellExecute = true
        };

        try
        {
            Process.Start(psi);
            lblStatus.Text = "DayZ gestartet. Viel Spaß!";
            lblStatus.ForeColor = Color.FromArgb(100, 220, 100);
            await Task.Delay(1000);
            Close();
        }
        catch (Exception ex)
        {
            lblStatus.Text = "Fehler: " + ex.Message;
            lblStatus.ForeColor = Color.FromArgb(255, 100, 100);
            btnPlay.Enabled = true;
        }
    }

    static string ComputeSha512(string filePath)
    {
        using var sha = SHA512.Create();
        using var stream = File.OpenRead(filePath);
        byte[] hash = sha.ComputeHash(stream);
        var sb = new StringBuilder(128);
        foreach (byte b in hash)
            sb.Append(b.ToString("x2"));
        return sb.ToString();
    }

    class Config
    {
        public string PlayerName { get; set; } = "";
    }
}