import importlib.machinery
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

PATH = Path(__file__).resolve().parents[1] / 'bin/boot-proxmox-base-image'
loader = importlib.machinery.SourceFileLoader('manual_vm', str(PATH))
manual = types.ModuleType(loader.name)
manual.__file__ = str(PATH)
loader.exec_module(manual)


class ManualBootTests(unittest.TestCase):
  def test_resume_preserves_guest_changes_and_rejects_modified_backing(self):
    with tempfile.TemporaryDirectory() as temporary:
      root = Path(temporary)
      source = root / 'base.qcow2'
      source.write_bytes(b'original-base')
      source.chmod(0o400)
      code, variables = root / 'code.fd', root / 'variables.fd'
      code.write_bytes(b'original-code')
      variables.write_bytes(b'original-vars')
      directory = root / 'vm'
      directory.mkdir(mode=0o700)
      def create_overlay(command):
        Path(command[-1]).write_bytes(b'initial-overlay')
        return b''
      with patch.object(manual.builder, 'run', side_effect=create_overlay):
        manual.prepare_vm(directory, source, (code, variables))
      (directory / 'disk.qcow2').write_bytes(b'saved-user-changes')
      (directory / 'OVMF_VARS.fd').write_bytes(b'saved-firmware-state')
      info = {'format': 'qcow2', 'backing-filename': str(source)}
      with patch.object(manual, 'image_info', return_value=info), patch.object(manual.builder, 'run') as create:
        manual.prepare_vm(directory, source, (code, variables))
        create.assert_not_called()
      self.assertEqual((directory / 'disk.qcow2').read_bytes(), b'saved-user-changes')
      self.assertEqual((directory / 'OVMF_VARS.fd').read_bytes(), b'saved-firmware-state')
      self.assertEqual(source.read_bytes(), b'original-base')
      self.assertEqual((directory / 'disk.qcow2').stat().st_mode & 0o777, 0o600)
      self.assertEqual((directory / 'OVMF_CODE.fd').stat().st_mode & 0o777, 0o400)
      source.chmod(0o600)
      source.write_bytes(b'changed-original')
      source.chmod(0o400)
      with self.assertRaisesRegex(ValueError, 'different or modified'):
        manual.prepare_vm(directory, source, (code, variables))
      self.assertEqual((directory / 'disk.qcow2').read_bytes(), b'saved-user-changes')

  def test_refuses_unrelated_directories_and_incomplete_state(self):
    with tempfile.TemporaryDirectory() as temporary:
      root = Path(temporary)
      source = root / 'base.qcow2'
      source.write_bytes(b'base')
      directory = root / 'existing'
      directory.mkdir(mode=0o755)
      (directory / 'unrelated').write_text('preserve me')
      args = types.SimpleNamespace(vm_dir=str(directory))
      before = directory.stat().st_mode
      with self.assertRaisesRegex(ValueError, 'not empty'):
        manual.vm_directory(args, source)
      self.assertEqual(directory.stat().st_mode, before)
      with self.assertRaisesRegex(ValueError, 'incomplete state'):
        manual.prepare_vm(directory, source, (None, None))
      self.assertEqual((directory / 'unrelated').read_text(), 'preserve me')
      args.vm_dir = str(root)
      with self.assertRaisesRegex(ValueError, 'contain the original'):
        manual.vm_directory(args, source)

  def test_qemu_uses_only_saved_overlay_and_firmware_with_interactive_serial(self):
    args = types.SimpleNamespace(memory_mib=4096, cpus=4, ssh_port=22222)
    directory = Path('/private/manual-vm')
    command = manual.qemu_command(args, directory, 'kvm')
    self.assertIn('-nographic', command)
    self.assertFalse('-serial' in command or '-monitor' in command)
    disks = [command[index + 1] for index, value in enumerate(command) if value == '-drive']
    self.assertEqual(len(disks), 3)
    self.assertTrue(all('file=/private/manual-vm/' in disk for disk in disks))
    self.assertIn('user,id=network,hostfwd=tcp:127.0.0.1:22222-:22', command)


if __name__ == '__main__':
  unittest.main()
