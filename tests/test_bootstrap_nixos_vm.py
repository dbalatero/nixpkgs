"""Safety and generated-configuration checks; no real VM or secrets required."""

import contextlib
import copy
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
    (self.repo / "lab").mkdir()
    self.inventory_path = self.repo / "lab/network.json"
    self.inventory = {
      "subnet": "192.168.1.0/24",
      "dhcp_range": {"start": "192.168.1.2", "end": "192.168.1.200"},
      "static_range": {"start": "192.168.1.201", "end": "192.168.1.254"},
      "gateway": "192.168.1.1",
      "dns": ["192.168.1.169"],
      "machines": [
        {"ip": "192.168.1.201", "hostname": "truenas", "comment": "TrueNAS VM"},
        {"ip": "192.168.1.209", "hostname": "imessage", "comment": "Mac Mini"},
        {"ip": "192.168.1.250", "hostname": "proxmox", "comment": "Proxmox host"},
      ],
    }
    self.write_inventory(self.inventory)
    self.git("add", "flake.nix", "lab/network.json")
    self.git("commit", "-m", "Initial fixture")

  def write_inventory(self, inventory):
    self.inventory_path.write_text(json.dumps(inventory, indent=2) + "\n")

  def read_inventory(self):
    return json.loads(self.inventory_path.read_text())

  def git(self, *args):
    return subprocess.check_output(["git", *args], cwd=self.repo, text=True, stderr=subprocess.PIPE)

  def test_invalid_inputs_fail_before_repository_or_machine_changes(self):
    cases = [
      ["-bad"], ["Upper"], ["proxmox-base"], ["x", "--profile", "desktop"],
      ["x", "--static-ip", "192.168.1.210"],
      ["x", "--gateway", "192.168.1.1"],
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
    bootstrap.configure_network(args, self.inventory)
    path = self.repo / "generated.nix"
    path.write_text(bootstrap.configuration(args, ["  boot.loader.systemd-boot.enable = true;"], "ens18"))
    expression = f"(import {path} {{}}).networking"
    value = json.loads(subprocess.check_output(["nix-instantiate", "--eval", "--strict", "--json", "--expr", expression], text=True))
    self.assertEqual(value["interfaces"]["ens18"]["ipv4"]["addresses"], [{"address": "192.168.1.210", "prefixLength": 24}])
    self.assertFalse(value["useDHCP"])
    self.assertEqual(value["defaultGateway"]["interface"], "ens18")

  def run_fixture(self, argv, update=None, rebuild_returncode=0):
    original_run = bootstrap.run
    original_subprocess_run = subprocess.run

    def fake_subprocess_run(command, **kwargs):
      if command[:3] == ["sudo", "-n", "nixos-rebuild"]:
        return subprocess.CompletedProcess(command, rebuild_returncode)
      return original_subprocess_run(command, **kwargs)

    def fake_run(command, *, cwd=None):
      if command[:3] == ["sudo", "-n", "test"]:
        return ""
      if command[:3] == ["sudo", "-n", "nixos-generate-config"]:
        return '{...}: {}\n'
      if command[0] == "nix-instantiate":
        # Other tests evaluate the generated Nix; this exercises transaction/staging.
        return ""
      return original_run(command, cwd=cwd)

    output = io.StringIO()
    with contextlib.ExitStack() as stack:
      stack.enter_context(patch.object(bootstrap, "__file__", str(self.repo / "bin/bootstrap-nixos-vm")))
      stack.enter_context(patch.object(bootstrap.shutil, "which", return_value="/fixture/command"))
      stack.enter_context(patch.object(bootstrap, "run", side_effect=fake_run))
      stack.enter_context(patch.object(bootstrap.subprocess, "run", side_effect=fake_subprocess_run))
      stack.enter_context(patch.object(bootstrap, "boot_configuration", return_value=["  boot.loader.systemd-boot.enable = true;"]))
      stack.enter_context(patch.object(bootstrap, "detect_interface", return_value="ens18"))
      stack.enter_context(patch.object(bootstrap.sys.stdin, "isatty", return_value=False))
      stack.enter_context(contextlib.redirect_stdout(output))
      stack.enter_context(contextlib.redirect_stderr(output))
      if update:
        stack.enter_context(patch.object(bootstrap, "update_repository", side_effect=update))
      result = bootstrap.main(argv)
    return result, output.getvalue()

  def test_static_defaults_and_explicit_overrides(self):
    args = bootstrap.arguments(["lab-test", "--static-ip", "192.168.1.210/24"])
    bootstrap.configure_network(args, self.inventory)
    self.assertEqual(args.gateway, "192.168.1.1")
    self.assertEqual(args.dns, ["192.168.1.169"])
    args = bootstrap.arguments(["lab-test", "--static-ip", "192.168.1.210/24", "--gateway", "192.168.1.254", "--dns", "9.9.9.9", "--dns", "1.1.1.1"])
    bootstrap.configure_network(args, self.inventory)
    self.assertEqual(args.gateway, "192.168.1.254")
    self.assertEqual(args.dns, ["9.9.9.9", "1.1.1.1"])

  def test_explicit_duplicate_and_invalid_static_addresses_fail(self):
    cases = [
      ["--static-ip", "192.168.1.201/24"],
      ["--static-ip", "192.168.1.209/24"],
      ["--static-ip", "192.168.1.250/24"],
      ["--static-ip", "192.168.1.100/24"],
      ["--static-ip", "192.168.1.0/24"],
      ["--static-ip", "192.168.1.210/16"],
      ["--static-ip", "192.168.1.210/24", "--gateway", "10.0.0.1"],
    ]
    for options in cases:
      with self.subTest(options=options), contextlib.redirect_stderr(io.StringIO()), self.assertRaises((bootstrap.BootstrapError, SystemExit)):
        args = bootstrap.arguments(["lab-test", *options])
        bootstrap.configure_network(args, self.inventory)

  def test_other_subnet_requires_explicit_gateway_and_dns(self):
    args = bootstrap.arguments(["lab-test", "--static-ip", "10.20.0.5/24"])
    with self.assertRaises(bootstrap.BootstrapError):
      bootstrap.configure_network(args, self.inventory)
    args = bootstrap.arguments(["lab-test", "--static-ip", "10.20.0.5/24", "--gateway", "10.20.0.1", "--dns", "10.20.0.53"])
    bootstrap.configure_network(args, self.inventory)
    self.assertEqual(args.gateway, "10.20.0.1")
    self.assertEqual(args.dns, ["10.20.0.53"])

  def test_allocator_skips_known_addresses_and_detects_exhaustion(self):
    inventory = copy.deepcopy(self.inventory)
    selected = []
    for _ in range(51):
      address = bootstrap.suggest_ip(inventory)
      selected.append(address)
      args = bootstrap.arguments([f"vm-{len(selected)}", "--static-ip", address])
      with contextlib.redirect_stdout(io.StringIO()):
        bootstrap.configure_network(args, inventory)
      inventory = json.loads(bootstrap.reserve_ip(args, inventory))
    self.assertEqual(selected[0], "192.168.1.202/24")
    self.assertNotIn("192.168.1.201/24", selected)
    self.assertNotIn("192.168.1.209/24", selected)
    self.assertNotIn("192.168.1.250/24", selected)
    self.assertIn("192.168.1.254/24", selected)
    self.assertEqual(len(set(selected)), 51)
    with self.assertRaises(bootstrap.BootstrapError):
      bootstrap.suggest_ip(inventory)

  def test_allocator_reserves_gateway_and_dns_without_allocation_entries(self):
    inventory = copy.deepcopy(self.inventory)
    inventory["gateway"] = "192.168.1.202"
    inventory["dns"] = ["192.168.1.203"]
    self.assertEqual(bootstrap.suggest_ip(inventory), "192.168.1.204/24")

  def test_suggestion_is_read_only_and_does_not_require_vm_tools(self):
    before = self.inventory_path.read_bytes()
    with patch.object(bootstrap, "__file__", str(self.repo / "bin/bootstrap-nixos-vm")), patch.object(bootstrap.shutil, "which", return_value=None), contextlib.redirect_stdout(io.StringIO()) as output:
      result = bootstrap.main(["--suggest-ip"])
    self.assertEqual(result, 0)
    self.assertIn("192.168.1.202/24", output.getvalue())
    self.assertEqual(self.inventory_path.read_bytes(), before)
    self.assertEqual(self.git("status", "--porcelain"), "")

  def test_static_bootstrap_stages_inventory_with_generated_host(self):
    result, output = self.run_fixture(["lab-test", "--static-ip", "auto", "--skip-update", "--no-switch"])
    self.assertEqual(result, 0, output)
    inventory = self.read_inventory()
    self.assertEqual(next(machine["hostname"] for machine in inventory["machines"] if machine["ip"] == "192.168.1.202"), "lab-test")
    configuration = (self.repo / "hosts/lab-test/configuration.nix").read_text()
    self.assertIn('address = "192.168.1.202";', configuration)
    self.assertIn('address = "192.168.1.1";', configuration)
    self.assertIn('networking.nameservers = ["192.168.1.169"];', configuration)
    self.assertEqual(set(self.git("diff", "--cached", "--name-only").splitlines()), {
      "lab/network.json", "flake.nix", "hosts/lab-test/configuration.nix",
      "hosts/lab-test/hardware-configuration.nix", "home/hosts/lab-test/default.nix",
    })

  def test_rebuild_failure_preserves_staged_reservation_and_host(self):
    result, output = self.run_fixture(["lab-test", "--static-ip", "auto", "--skip-update"], rebuild_returncode=1)
    self.assertEqual(result, 1, output)
    self.assertIn("Rebuild failed", output)
    self.assertTrue((self.repo / "hosts/lab-test/configuration.nix").exists())
    inventory = self.read_inventory()
    self.assertEqual(next(machine["hostname"] for machine in inventory["machines"] if machine["ip"] == "192.168.1.202"), "lab-test")
    self.assertIn("lab/network.json", self.git("diff", "--cached", "--name-only"))

  def test_duplicate_fails_without_generating_or_staging_files(self):
    before = self.inventory_path.read_bytes()
    result, output = self.run_fixture(["lab-test", "--static-ip", "192.168.1.209/24", "--skip-update", "--no-switch"])
    self.assertEqual(result, 1, output)
    self.assertIn("192.168.1.209", output)
    self.assertFalse((self.repo / "hosts/lab-test").exists())
    self.assertEqual(self.inventory_path.read_bytes(), before)
    self.assertEqual(self.git("status", "--porcelain"), "")

  def test_dhcp_bootstrap_preserves_inventory(self):
    before = self.inventory_path.read_bytes()
    result, output = self.run_fixture(["lab-test", "--skip-update", "--no-switch"])
    self.assertEqual(result, 0, output)
    self.assertEqual(self.inventory_path.read_bytes(), before)
    configuration = (self.repo / "hosts/lab-test/configuration.nix").read_text()
    self.assertIn("networking.useDHCP = true;", configuration)
    self.assertNotIn("defaultGateway", configuration)
    self.assertNotIn("lab/network.json", self.git("diff", "--cached", "--name-only"))

  def test_allocator_uses_inventory_after_repository_update(self):
    def update(repo):
      inventory = self.read_inventory()
      inventory["machines"].append({"ip": "192.168.1.202", "hostname": "other-vm", "comment": "Added upstream"})
      self.write_inventory(inventory)
      self.git("add", "lab/network.json")
      self.git("commit", "-m", "Simulated upstream reservation")

    result, output = self.run_fixture(["lab-test", "--static-ip", "auto", "--no-switch"], update=update)
    self.assertEqual(result, 0, output)
    inventory = self.read_inventory()
    self.assertEqual(next(machine["hostname"] for machine in inventory["machines"] if machine["ip"] == "192.168.1.202"), "other-vm")
    self.assertEqual(next(machine["hostname"] for machine in inventory["machines"] if machine["ip"] == "192.168.1.203"), "lab-test")

  def test_duplicate_json_keys_fail_closed(self):
    content = self.inventory_path.read_text().replace('"subnet": "192.168.1.0/24",', '"subnet": "192.168.1.0/24", "subnet": "10.0.0.0/24",')
    self.inventory_path.write_text(content)
    with self.assertRaises(bootstrap.BootstrapError):
      bootstrap.load_inventory(self.repo)

  def test_duplicate_inventory_ips_and_hostnames_fail_closed(self):
    for extra in [
      {"ip": "192.168.1.201", "hostname": "other", "comment": "Duplicate IP"},
      {"ip": "192.168.1.202", "hostname": "truenas", "comment": "Duplicate hostname"},
      {"ip": 3232235978, "hostname": "numeric-ip", "comment": "IP must be a string"},
    ]:
      inventory = copy.deepcopy(self.inventory)
      inventory["machines"].append(extra)
      self.write_inventory(inventory)
      with self.subTest(extra=extra), self.assertRaises(bootstrap.BootstrapError):
        bootstrap.load_inventory(self.repo)

  def test_reserving_address_preserves_existing_comments(self):
    checked_in = (SCRIPT.parent.parent / "lab/network.json").read_text()
    self.assertEqual(checked_in, json.dumps(json.loads(checked_in), indent=2) + "\n")
    inventory = bootstrap.load_inventory(self.repo)
    original = copy.deepcopy(inventory)
    args = bootstrap.arguments(["lab-test", "--static-ip", "auto", "--description", "New nginx server"])
    bootstrap.configure_network(args, inventory)
    serialized = bootstrap.reserve_ip(args, inventory)
    updated = json.loads(serialized)
    self.assertEqual(serialized, json.dumps(updated, indent=2) + "\n")
    for machine in original["machines"]:
      self.assertIn(machine, updated["machines"])
    self.assertIn({"hostname": "lab-test", "ip": "192.168.1.202", "comment": "New nginx server"}, updated["machines"])
    self.assertEqual(inventory, original)

  def test_bios_root_disk_is_discovered(self):
    with patch.object(bootstrap.Path, "exists", return_value=False), patch.object(bootstrap.Path, "glob", return_value=[]), patch.object(bootstrap, "run", side_effect=["/dev/vda2\n", "/dev/vda2 part\n/dev/vda disk\n"]):
      self.assertIn('  boot.loader.grub.device = "/dev/vda";', bootstrap.boot_configuration())


if __name__ == "__main__":
  unittest.main()
