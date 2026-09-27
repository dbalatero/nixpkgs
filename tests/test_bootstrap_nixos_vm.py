"""Safety and generated-configuration checks; no real VM or secrets required."""

import contextlib
import importlib.machinery
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch


SCRIPT = Path(__file__).resolve().parents[1] / "bin/bootstrap-nixos-vm"
LOADER = importlib.machinery.SourceFileLoader("bootstrap", str(SCRIPT))
SPEC = importlib.util.spec_from_loader(LOADER.name, LOADER)
bootstrap = importlib.util.module_from_spec(SPEC)
LOADER.exec_module(bootstrap)


class BootstrapTests(unittest.TestCase):
  def setUp(self):
    self.temporary = tempfile.TemporaryDirectory()
    self.addCleanup(self.temporary.cleanup)
    self.repo = Path(self.temporary.name) / "repo"
    self.repo.mkdir()
    (self.repo / "hosts").mkdir()
    (self.repo / "home/hosts").mkdir(parents=True)
    (self.repo / "flake.nix").write_text("{\n  # NEW_HOST_SENTINEL\n}\n")
    self.git("init", "-b", "main")
    self.git("config", "user.name", "Fixture")
    self.git("config", "user.email", "fixture@example.invalid")
    self.git("config", "commit.gpgsign", "false")
    self.git("config", "core.fsmonitor", "false")
    self.git("add", "flake.nix")
    self.git("commit", "-m", "Initial fixture")

  def git(self, *args):
    return subprocess.check_output(["git", *args], cwd=self.repo, text=True, stderr=subprocess.PIPE)

  def test_invalid_inputs_fail_before_repository_or_machine_changes(self):
    cases = [
      ["-bad"], ["Upper"], ["proxmox-base"], ["x", "--profile", "desktop"],
      ["x", "--static-ip", "192.168.1.210"],
      ["x", "--gateway", "192.168.1.1"],
      ["x", "--static-ip", "192.168.1.210/24", "--gateway", "10.0.0.1", "--dns", "1.1.1.1"],
      ["x", "--static-ip", "192.168.1.0/24", "--gateway", "192.168.1.1", "--dns", "1.1.1.1"],
      ["x", "--static-ip", "192.168.1.210/24", "--gateway", "192.168.1.1"],
    ]
    with patch.object(bootstrap, "run") as run, contextlib.redirect_stderr(io.StringIO()):
      for args in cases:
        with self.subTest(args=args), self.assertRaises(SystemExit):
          bootstrap.main(args)
      run.assert_not_called()

  def test_dirty_checkout_and_collisions_fail_without_changes(self):
    initial = (self.repo / "flake.nix").read_bytes()
    (self.repo / "hosts/existing").mkdir()
    with self.assertRaisesRegex(bootstrap.BootstrapError, "already exists"):
      bootstrap.check_repository(self.repo, "existing")
    (self.repo / "untracked").write_text("keep this")
    with self.assertRaisesRegex(bootstrap.BootstrapError, "local changes"):
      bootstrap.check_repository(self.repo, "fresh")
    self.assertEqual((self.repo / "flake.nix").read_bytes(), initial)
    self.assertEqual((self.repo / "untracked").read_text(), "keep this")
    self.assertFalse((self.repo / "hosts/fresh").exists())

  def test_update_preserves_unpushed_commits_and_rejects_divergence(self):
    remote = Path(self.temporary.name) / "remote.git"
    subprocess.check_call(["git", "clone", "--bare", str(self.repo), str(remote)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    self.git("remote", "add", "origin", str(remote))
    self.git("fetch", "origin")
    self.git("branch", "--set-upstream-to=origin/main")
    (self.repo / "local").write_text("unpublished implementation")
    self.git("add", "local")
    self.git("commit", "-m", "Unpublished")
    ahead = self.git("rev-parse", "HEAD")
    bootstrap.update_repository(self.repo)
    self.assertEqual(self.git("rev-parse", "HEAD"), ahead)
    # Point the local upstream at a sibling commit through a second clone.
    other = Path(self.temporary.name) / "other"
    subprocess.check_call(["git", "clone", str(remote), str(other)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    (other / "remote-change").write_text("separate change")
    subprocess.check_call(["git", "add", "remote-change"], cwd=other)
    subprocess.check_call(["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "-c", "commit.gpgsign=false", "commit", "-m", "Remote change"], cwd=other, stdout=subprocess.DEVNULL)
    # Update the fixture bare repository directly; never contact or push to GitHub.
    subprocess.check_call(["git", "--git-dir", str(remote), "fetch", str(other), "main:main"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with self.assertRaisesRegex(bootstrap.BootstrapError, "Cannot fast-forward"):
      bootstrap.update_repository(self.repo)
    self.assertEqual(self.git("rev-parse", "HEAD"), ahead)
    self.assertEqual((self.repo / "local").read_text(), "unpublished implementation")

  def test_ambiguous_static_interface_requires_explicit_choice(self):
    links = json.dumps([{"ifname": "lo"}, {"ifname": "ens18"}, {"ifname": "ens19"}])
    with patch.object(bootstrap, "run", side_effect=[links, "[]"]):
      with self.assertRaisesRegex(bootstrap.BootstrapError, "unique"):
        bootstrap.detect_interface(None)
    with patch.object(bootstrap, "run", return_value=links):
      self.assertEqual(bootstrap.detect_interface("ens19"), "ens19")
      with self.assertRaisesRegex(bootstrap.BootstrapError, "does not exist"):
        bootstrap.detect_interface("eth0")

  @unittest.skipUnless(shutil.which("nix-instantiate"), "Nix required for generated syntax check")
  def test_static_configuration_evaluates_and_escapes_description(self):
    args = bootstrap.arguments(["test-vm", "--description", 'text\n}; builtins.abort "injected"; ${bad}', "--static-ip", "192.168.1.210/24", "--gateway", "192.168.1.1", "--dns", "1.1.1.1", "--dns", "2606:4700:4700::1111"])
    path = self.repo / "generated.nix"
    path.write_text(bootstrap.configuration(args, ["  boot.loader.systemd-boot.enable = true;"], "ens18"))
    expression = f"(import {path} {{}}).networking"
    value = json.loads(subprocess.check_output(["nix-instantiate", "--eval", "--strict", "--json", "--expr", expression], text=True))
    self.assertEqual(value["interfaces"]["ens18"]["ipv4"]["addresses"], [{"address": "192.168.1.210", "prefixLength": 24}])
    self.assertFalse(value["useDHCP"])
    self.assertEqual(value["defaultGateway"]["interface"], "ens18")

  def test_bios_root_disk_is_discovered(self):
    with patch.object(bootstrap.Path, "exists", return_value=False), patch.object(bootstrap.Path, "glob", return_value=[]), patch.object(bootstrap, "run", side_effect=["/dev/vda2\n", "/dev/vda2 part\n/dev/vda disk\n"]):
      self.assertIn('  boot.loader.grub.device = "/dev/vda";', bootstrap.boot_configuration())


if __name__ == "__main__":
  unittest.main()
