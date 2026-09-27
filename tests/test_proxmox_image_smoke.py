import importlib.machinery
import contextlib
import io
from pathlib import Path
import socket
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

PATH = Path(__file__).resolve().parents[1] / 'bin/test-proxmox-base-image'
loader = importlib.machinery.SourceFileLoader('image_smoke', str(PATH))
smoke = types.ModuleType(loader.name)
smoke.__file__ = str(PATH)
loader.exec_module(smoke)


class SmokeHelperTests(unittest.TestCase):
  def test_password_source_defaults_and_explicit_alternatives(self):
    positional = ['dummy.qcow2']
    self.assertEqual(smoke.arguments(positional).password_op_item, 'yklwrusohu3uus3bpnua7v27ky')
    self.assertEqual(smoke.arguments(positional + ['--password-op-item', 'a' * 26]).password_op_item, 'a' * 26)
    self.assertIsNone(smoke.arguments(positional + ['--skip-console']).password_op_item)
    with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
      smoke.arguments(positional + ['--skip-console', '--password-op-item', 'a' * 26])

  def test_acceleration_is_explicit_and_missing_kvm_falls_back(self):
    with patch.object(smoke.os.path, 'exists', return_value=False):
      self.assertEqual(smoke.acceleration('auto'), 'tcg')
      self.assertEqual(smoke.acceleration('tcg'), 'tcg')
      with self.assertRaises(ValueError):
        smoke.acceleration('kvm')
    with patch.object(smoke.os.path, 'exists', return_value=True), patch.object(smoke.os, 'access', return_value=True):
      self.assertEqual(smoke.acceleration('auto'), 'kvm')

  def test_console_timeout_does_not_disclose_buffer(self):
    connection = Mock()
    connection.recv.side_effect = [b'dummy-sensitive-value', b'']
    with self.assertRaises(ValueError) as error:
      smoke.await_text(connection, b'not-matched', 1)
    self.assertNotIn('dummy-sensitive-value', str(error.exception))
    connection.recv.side_effect = [socket.timeout(), b'log', b'in: ']
    smoke.await_text(connection, rb'login: *$', 1)

  def test_identity_records_total_and_available_root_bytes(self):
    guest = smoke.Guest.__new__(smoke.Guest)
    guest.ssh = Mock(return_value=types.SimpleNamespace(stdout=(
      b'0123456789abcdef0123456789abcdef\n'
      b'256 SHA256:dummy root@guest (ED25519)\n'
      b'  20000000000    7000000000\n')))
    identity = guest.identity()
    self.assertEqual(identity['root_bytes'], 20000000000)
    self.assertEqual(identity['root_available_bytes'], 7000000000)
    self.assertEqual(identity['host_key'], 'SHA256:dummy')

  def test_pde_rejects_shared_desktop_identity_and_enabled_agent(self):
    guest = Mock()
    settings = b'user git\nidentitiesonly yes\nidentityagent none\nstricthostkeychecking true\naddkeystoagent false\nidentityfile ~/.ssh/id_nixos_vm_github\n'
    guest.ssh.return_value.stdout = settings
    with patch.object(smoke, 'print'):
      smoke.check_pde(guest, 'test')
      guest.ssh.return_value.stdout = settings + b'identityfile ~/.ssh/id_github\n'
      with self.assertRaisesRegex(ValueError, 'only the dedicated'):
        smoke.check_pde(guest, 'test')
      guest.ssh.return_value.stdout = settings.replace(b'identityagent none', b'identityagent /run/user/1000/agent')
      with self.assertRaisesRegex(ValueError, 'Unexpected GitHub SSH behavior'):
        smoke.check_pde(guest, 'test')

  def test_effective_ssh_settings_parse_without_a_pipe_and_only_report_auth_options(self):
    guest = Mock()
    guest.ssh.return_value.stdout = b' PasswordAuthentication no\r\n KbdInteractiveAuthentication no \nPermitRootLogin no\nHostKey /irrelevant/path\n'
    smoke.check_ssh_settings(guest)
    self.assertNotIn('|', guest.ssh.call_args.args[0])
    guest.ssh.side_effect = [types.SimpleNamespace(stdout=b'passwordauthentication yes\nkbdinteractiveauthentication no\npermitrootlogin no\nhostkey /irrelevant/path\n'),
      types.SimpleNamespace(stdout=b'ExecStart=/nix/store/sshd -D -f /etc/ssh/sshd_config')]
    with self.assertRaises(ValueError) as error:
      smoke.check_ssh_settings(guest)
    self.assertIn('"passwordauthentication": "yes"', str(error.exception))
    self.assertIn('ExecStart=', str(error.exception))
    self.assertNotIn('/irrelevant/path', str(error.exception))

  def test_authentication_probe_checks_server_offered_methods(self):
    guest = smoke.Guest.__new__(smoke.Guest)
    guest.ssh = Mock(return_value=types.SimpleNamespace(returncode=255,
      stderr=b'debug1: Authentications that can continue: publickey\r\n'))
    guest.reject_password_ssh()
    guest.ssh.return_value.stderr = b'debug1: Authentications that can continue: publickey,password\r\n'
    with self.assertRaises(ValueError):
      guest.reject_password_ssh()
    guest.ssh.return_value.stderr = b'Connection refused'
    with self.assertRaises(ValueError):
      guest.reject_password_ssh()

  def test_qemu_boots_only_private_copy_and_keeps_original_unchanged(self):
    with tempfile.TemporaryDirectory() as temp:
      directory = Path(temp)
      original = directory / 'original.qcow2'
      original.write_bytes(b'dummy-image')
      original.chmod(0o400)
      before = original.stat()
      code = directory / 'OVMF_CODE.fd'
      variables = directory / 'OVMF_VARS.fd'
      code.write_bytes(b'code')
      variables.write_bytes(b'variables')
      def fake_run(command):
        if command[1] == 'convert':
          Path(command[-1]).write_bytes(b'dummy-copy')
        return b''
      process = Mock()
      process.poll.return_value = 0
      args = types.SimpleNamespace(memory_mib=2048, cpus=2, ssh_port=22222)
      with patch.object(smoke.socket, 'socket'), patch.object(smoke.builder, 'run', side_effect=fake_run), patch.object(smoke.subprocess, 'Popen', return_value=process) as popen:
        guest = smoke.Guest(args, directory / 'copy', original, (code, variables), 'tcg', 28)
        guest.close()
      command = popen.call_args.args[0]
      self.assertFalse(any(str(original) in argument for argument in command))
      self.assertTrue(any(str(guest.image) in argument for argument in command))
      self.assertEqual(guest.image.stat().st_mode & 0o777, 0o600)
      self.assertEqual(guest.directory.stat().st_mode & 0o777, 0o700)
      self.assertEqual(original.read_bytes(), b'dummy-image')
      self.assertEqual(original.stat().st_mtime_ns, before.st_mtime_ns)
      self.assertEqual(original.stat().st_mode & 0o777, 0o400)


if __name__ == '__main__':
  unittest.main()
