class DaedalusAgent < Formula
  include Language::Python::Virtualenv

  desc "Self-improving AI agent that creates skills from experience"
  homepage "https://github.com/itsXactlY/daedalus"
  # Pointed at a NousResearch-owned path until 2026-08-21: the fork's original
  # rename rewrote "hermes" inside UPSTREAM's URL, producing an org/repo pair
  # that has never existed. NousResearch does not publish this package.
  url "https://github.com/itsXactlY/daedalus/archive/refs/tags/v0.8.1.tar.gz"
  sha256 "<replace-with-release-asset-sha256>"
  license "MIT"

  depends_on "certifi" => :no_linkage
  depends_on "cryptography" => :no_linkage
  depends_on "libyaml"
  depends_on "python@3.14"

  pypi_packages ignore_packages: %w[certifi cryptography pydantic]

  # Refresh resource stanzas after bumping the source url/version:
  #   brew update-python-resources --print-only daedalus

  def install
    venv = virtualenv_create(libexec, "python3.14")
    venv.pip_install resources
    venv.pip_install buildpath

    pkgshare.install "skills", "optional-skills"

    %w[daedalus daedalus daedalus-acp].each do |exe|
      next unless (libexec/"bin"/exe).exist?

      (bin/exe).write_env_script(
        libexec/"bin"/exe,
        DAEDALUS_BUNDLED_SKILLS: pkgshare/"skills",
        DAEDALUS_OPTIONAL_SKILLS: pkgshare/"optional-skills",
        DAEDALUS_MANAGED: "homebrew"
      )
    end
  end

  test do
    assert_match "Daedalus Agent v#{version}", shell_output("#{bin}/daedalus version")

    managed = shell_output("#{bin}/daedalus update 2>&1")
    assert_match "managed by Homebrew", managed
    assert_match "brew upgrade daedalus", managed
  end
end
