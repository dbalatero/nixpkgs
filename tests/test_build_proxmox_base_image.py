"""Safety and snapshot tests use temporary repositories and dummy values only."""
import importlib.machinery
import contextlib
import io
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch

MODULE = Path(__file__).resolve().parents[1] / 'bin/build-proxmox-base-image'
loader = importlib.machinery.SourceFileLoader('image_builder', str(MODULE))
builder = types.ModuleType(loader.name)
builder.__file__ = str(MODULE)
loader.exec_module(builder)


class ImageBuilderTests(unittest.TestCase):
  def test_password_source_defaults_and_explicit_alternatives(self):
    positional = []
    self.assertEqual(builder.arguments(positional).password_op_item, 'yklwrusohu3uus3bpnua7v27ky')
    self.assertEqual(builder.arguments(positional + ['--password-op-item', 'a' * 26]).password_op_item, 'a' * 26)
    self.assertIsNone(builder.arguments(positional + ['--password-prompt']).password_op_item)
    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
      builder.arguments(positional + ['--password-prompt', '--password-op-item', 'a' * 26])

  def test_explicit_prompt_rejects_non_tty_before_tools_or_secret_access(self):
    with patch.object(builder.sys, 'argv', [str(MODULE), '--password-prompt']), \
      patch.object(builder.sys.stdin, 'isatty', return_value=False), \
      patch.object(builder, 'ensure_tools') as tools, \
      contextlib.redirect_stderr(io.StringIO()) as error:
      self.assertEqual(builder.main(), 1)
      tools.assert_not_called()
      self.assertIn('--password-prompt requires an interactive TTY', error.getvalue())
    args = builder.arguments(['--password-op-item', ''])
    with self.assertRaisesRegex(ValueError, '26-character UUID'):
      builder.read_password(args)

  def test_private_file_rejects_public_permissions_and_symlinks(self):
    with tempfile.TemporaryDirectory() as temp:
      path = Path(temp) / 'value'
      path.write_text('dummy')
      path.chmod(0o644)
      with self.assertRaises(ValueError):
        builder.private_file(path)
      path.chmod(0o700)
      with self.assertRaises(ValueError):
        builder.private_file(path)
      path.chmod(0o600)
      self.assertEqual(builder.private_file(path), path)
      link = Path(temp) / 'link'
      link.symlink_to(path)
      with self.assertRaises(ValueError):
        builder.private_file(link)

  def test_missing_password_fails_without_tty(self):
    args = types.SimpleNamespace(password_op_item=None)
    with patch.object(builder.sys.stdin, 'isatty', return_value=False):
      with self.assertRaisesRegex(ValueError, 'requires an interactive TTY'):
        builder.read_password(args)

  def test_password_validation_with_mocked_op_and_prompt(self):
    args = builder.arguments([])
    with patch.object(builder, 'run', return_value=b'dummy\n'):
      self.assertEqual(builder.read_password(args), b'dummy')
    with patch.object(builder, 'run', return_value=b'multi\nline\n'):
      with self.assertRaises(ValueError):
        builder.read_password(args)
    args = builder.arguments(['--password-prompt'])
    with patch.object(builder.sys.stdin, 'isatty', return_value=True), \
      patch.object(builder.getpass, 'getpass', side_effect=['dummy', 'dummy']):
      self.assertEqual(builder.read_password(args), b'dummy')
    with patch.object(builder.sys.stdin, 'isatty', return_value=True), \
      patch.object(builder.getpass, 'getpass', side_effect=['dummy', 'different']):
      with self.assertRaisesRegex(ValueError, 'do not match'):
        builder.read_password(args)

  def test_workspace_and_guestfish_paths(self):
    with tempfile.TemporaryDirectory() as temp:
      path = Path(temp) / 'private'
      self.assertEqual(builder.workspace(path), path)
      self.assertEqual(path.stat().st_mode & 0o777, 0o700)
      link = Path(temp) / 'linked'
      link.symlink_to(path)
      with self.assertRaises(ValueError):
        builder.workspace(link)
      with self.assertRaises(ValueError):
        builder.quote('/tmp/unsafe\ncommand')

  def test_workspace_rejects_repository_through_symlink_parent_before_mutation(self):
    with tempfile.TemporaryDirectory() as temp:
      repository = Path(temp) / 'repo'
      repository.mkdir(mode=0o755)
      alias = Path(temp) / 'alias'
      alias.symlink_to(repository, target_is_directory=True)
      before = repository.stat().st_mode
      with patch.object(builder, 'REPO', repository):
        for path in [repository, alias / 'secrets', Path('/nix/store')]:
          with self.assertRaises(ValueError):
            builder.workspace(path)
      self.assertEqual(repository.stat().st_mode, before)
      self.assertFalse((repository / 'secrets').exists())

  def test_runtime_ssh_payload_preserves_home_manager_config(self):
    with tempfile.TemporaryDirectory() as temp:
      directory = Path(temp)
      ssh = directory / 'ssh'
      ssh.mkdir()
      managed_config = directory / 'managed-config'
      managed_config.write_text('Host github.com\n')
      (ssh / 'config').symlink_to(managed_config)
      dummy_key = directory / 'dummy-key'
      dummy_key.write_bytes(b'dummy-private-fixture')
      builder.write_ssh_payload(ssh, dummy_key, b'dummy-public-fixture')
      self.assertTrue((ssh / 'config').is_symlink())
      self.assertEqual(managed_config.read_text(), 'Host github.com\n')
      self.assertEqual((ssh / 'id_nixos_vm_github').read_bytes(), b'dummy-private-fixture')
      self.assertEqual((ssh / 'id_nixos_vm_github').stat().st_mode & 0o777, 0o600)
      self.assertIn('github.com ssh-ed25519 ', (ssh / 'known_hosts').read_text())
      fresh = directory / 'fresh'
      builder.write_ssh_payload(fresh, dummy_key, b'dummy-public-fixture')
      self.assertFalse((fresh / 'config').exists())

  def test_identity_scrub_mounts_esp_and_removes_only_explicit_identity_files(self):
    commands = builder.preparation_commands('/dev/sda1: vfat\n/dev/sda2: ext4\n', '/private/payload.tar')
    self.assertEqual(commands[:2], ['mount /dev/sda2 /', 'mount /dev/sda1 /boot'])
    self.assertIn('rm-f /boot/loader/random-seed', commands)
    self.assertIn('rm-f /etc/machine-id', commands)
    self.assertIn('rm-f /var/lib/dbus/machine-id', commands)
    self.assertIn('rm-f /var/lib/systemd/random-seed', commands)
    self.assertIn('rm-f /etc/ssh/ssh_host_ed25519_key', commands)
    self.assertFalse(any('*' in command or 'authorized_keys' in command or 'id_nixos_vm_github' in command for command in commands))
    self.assertEqual(commands[-3:], ['tar-in "/private/payload.tar" /', 'sync', 'umount-all'])
    for layout in ['/dev/sda2: ext4\n', '/dev/sda1: vfat\n/dev/sda2: ext4\n/dev/sda3: ext4\n']:
      with self.assertRaises(ValueError):
        builder.preparation_commands(layout, '/private/payload.tar')

  def test_snapshot_preserves_unpushed_history_and_excludes_dirty_files(self):
    with tempfile.TemporaryDirectory() as temp:
      source = Path(temp) / 'source'
      source.mkdir()
      def git(*args):
        return subprocess.check_output(['git', *args], cwd=source, stderr=subprocess.DEVNULL).decode().strip()
      git('init', '-b', 'test-branch')
      git('config', 'user.name', 'Test User')
      git('config', 'user.email', 'test@example.invalid')
      (source / 'tracked').write_text('committed\n')
      git('add', 'tracked')
      git('commit', '-m', 'base')
      remote = git('rev-parse', 'HEAD')
      git('update-ref', 'refs/remotes/origin/test-branch', remote)
      (source / 'second').write_text('unpushed\n')
      git('add', 'second')
      git('commit', '-m', 'local only')
      head = git('rev-parse', 'HEAD')
      (source / 'tracked').write_text('dirty\n')
      (source / 'private-untracked').write_text('dummy\n')
      destination = Path(temp) / 'clone'
      with patch.object(builder, 'REPO', source):
        self.assertEqual(builder.snapshot(destination, head), head)
      self.assertEqual((destination / 'tracked').read_text(), 'committed\n')
      self.assertFalse((destination / 'private-untracked').exists())
      self.assertEqual(subprocess.check_output(['git', 'rev-parse', 'origin/test-branch'], cwd=destination).decode().strip(), remote)
      self.assertFalse((destination / '.git/hooks').exists())
      self.assertFalse((destination / '.git/objects/info/alternates').exists())


if __name__ == '__main__':
  unittest.main()
