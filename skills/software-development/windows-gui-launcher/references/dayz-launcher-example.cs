// DayZ Launcher — WinForms GUI (.NET 10, WinExe)
// Built on Linux, cross-compiled to Windows, tested under Wine
// Hardcoded: SHA512 of DayZ_x64.exe, server host:port, full mod list

using System;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Text.Json;
using System.Windows.Forms;

namespace DayZLauncher
{
    public class LauncherForm : Form
    {
        // ===== HARDCODED INTEGRITY (NON-NEGOTIABLE) =====
        const string ExpectedHash = "51c49fb7e2f0cb2fd93821684c27bc8dcea29498c5b9740ed1105ed1ebb1c319c13e795b384c3ea91f483ff89da9e588cb1e07bc6666628d74b0f6be7dc9cdc1";
        const string DayzExeName = "DayZ_x64.exe";
        const string DefaultHost = "playtest.mazemaker.online";
        const int DefaultPort = 2302;

        // ===== FULL MOD LIST (from !START.sh) =====
        static readonly string[] Mods = new[]
        {
            "@CF", "@VanillaPlusPlusMap", "@VPPAdminTools", "@Trader", "@CodeLock",
            "@MuchCars", "@MuchStuffPack", "@BuilderItems", "@MedicalAttention",
            "@MuchDecor", "@BaseBuildingLogs", "@BaseBuildingPlus", "@ExpansionMod",
            "@ExpansionModVehicles", "@ExpansionModNaval", "@ExpansionModAI",
            "@ExpansionModSpotlight", "@AdvancedComplexity", "@AdvancedLoadouts",
            "@GoreZ", "@ZombiesAndAnimals", "@WeaponsPack", "@UniformsPack",
            "@VehiclesPack", "@ItemsPack", "@SoundsPack", "@ScriptsPack",
            "@ConfigsPack", "@ModelsPack", "@TexturesPack", "@ParticlesPack",
            "@AnimationsPack", "@PrefabsPack", "@WorldPack", "@ServerPack",
            "@ClientPack", "@SharedPack"
        };

        // ===== UI =====
        readonly TextBox txtName = new TextBox { Left = 120, Top = 20, Width = 250, PlaceholderText = "Player name" };
        readonly Label lblStatus = new Label { Left = 20, Top = 60, Width = 350, Height = 40, Text = "Ready. Enter name and click CONNECT." };
        readonly Button btnConnect = new Button { Text = "CONNECT", Left = 120, Top = 110, Width = 120, Height = 40 };

        // ===== CONFIG =====
        Config config = new Config();
        static string ConfigPath => Path.Combine(AppContext.BaseDirectory, "config.json");

        class Config { public string PlayerName = ""; public string ServerHost = DefaultHost; public int ServerPort = DefaultPort; }

        public LauncherForm()
        {
            Text = "DayZ Launcher — playtest.mazemaker.online";
            Width = 420; Height = 220; FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; StartPosition = FormStartPosition.CenterScreen;

            Controls.Add(new Label { Text = "Player Name:", Left = 20, Top = 23, AutoSize = true });
            Controls.Add(txtName);
            Controls.Add(lblStatus);
            Controls.Add(btnConnect);

            btnConnect.Click += BtnConnect_Click;
            LoadConfig();
            txtName.Text = config.PlayerName;
        }

        void LoadConfig()
        {
            if (File.Exists(ConfigPath))
                config = JsonSerializer.Deserialize<Config>(File.ReadAllText(ConfigPath)) ?? new Config();
        }

        void SaveConfig()
        {
            config.PlayerName = txtName.Text.Trim();
            File.WriteAllText(ConfigPath, JsonSerializer.Serialize(config, new JsonSerializerOptions { WriteIndented = true }));
        }

        static bool VerifySha512(string path, string expected)
        {
            using var sha = SHA512.Create();
            using var fs = File.OpenRead(path);
            var hash = Convert.ToHexString(sha.ComputeHash(fs)).ToLowerInvariant();
            return hash == expected.ToLowerInvariant();
        }

        void BtnConnect_Click(object sender, EventArgs e)
        {
            string name = txtName.Text.Trim();
            if (string.IsNullOrEmpty(name)) { MessageBox.Show("Enter a player name.", "Missing Name", MessageBoxButtons.OK, MessageBoxIcon.Warning); return; }

            string dayzRoot = AppContext.BaseDirectory;
            string dayzExe = Path.Combine(dayzRoot, DayzExeName);

            if (!File.Exists(dayzExe)) { MessageBox.Show($"{DayzExeName} not found in launcher folder.", "Missing Executable", MessageBoxButtons.OK, MessageBoxIcon.Error); return; }

            lblStatus.Text = "Verifying DayZ_x64.exe integrity...";
            Application.DoEvents();

            if (!VerifySha512(dayzExe, ExpectedHash))
            {
                MessageBox.Show("DayZ_x64.exe SHA512 mismatch!\nFile may be corrupted or modified.\nRe-download from Steam.", "Integrity Check Failed", MessageBoxButtons.OK, MessageBoxIcon.Error);
                lblStatus.Text = "Integrity check FAILED.";
                return;
            }

            lblStatus.Text = "Integrity OK. Launching DayZ...";
            Application.DoEvents();
            SaveConfig();

            string modString = string.Join(";", Mods);
            string args = $"-connect={config.ServerHost} -port={config.ServerPort} -name=\"{name}\" -mod={modString}";

            var psi = new ProcessStartInfo
            {
                FileName = DayzExeName,
                Arguments = args,
                WorkingDirectory = dayzRoot,
                UseShellExecute = true
            };

            try { Process.Start(psi); }
            catch (Exception ex) { MessageBox.Show($"Failed to launch DayZ:\n{ex.Message}", "Launch Error", MessageBoxButtons.OK, MessageBoxIcon.Error); lblStatus.Text = "Launch failed."; return; }

            Close(); // Fire-and-forget; launcher exits after spawn
        }

        [STAThread]
        static void Main()
        {
            Application.SetHighDpiMode(HighDpiMode.SystemAware);
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new LauncherForm());
        }
    }
}