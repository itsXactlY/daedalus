// Placeholder text + blocked names validation pattern for WinForms launchers
// Copy into BuildUI() and BtnPlay_Click()

// In BuildUI() - setup placeholder behavior:
txtName.Text = "John Doe";
txtName.ForeColor = Color.FromArgb(150, 150, 160); // gray placeholder color

txtName.Enter += (s, e) => {
    if (txtName.Text == "John Doe") { txtName.Text = ""; txtName.ForeColor = inputFore; }
};
txtName.Leave += (s, e) => {
    if (string.IsNullOrWhiteSpace(txtName.Text)) { txtName.Text = "John Doe"; txtName.ForeColor = Color.FromArgb(150, 150, 160); }
};

// In BtnPlay_Click() - validate before saving/launching:
string name = txtName.Text.Trim();
if (string.IsNullOrWhiteSpace(name)
    || name.Equals("John Doe", StringComparison.OrdinalIgnoreCase)
    || name.Equals("player", StringComparison.OrdinalIgnoreCase))
{
    lblStatus.Text = "Eigenen Namen eingeben (nicht \"John Doe\" oder \"player\").";
    lblStatus.ForeColor = Color.FromArgb(255, 180, 80);
    return;
}

// Only save config AFTER validation passes:
SaveConfig(); // saves 'name' (not the placeholder)