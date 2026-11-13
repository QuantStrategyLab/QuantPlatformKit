"""Execute the actual embedded staging code on safe and hostile offline bundles."""
import hashlib
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import zipfile


def main():
    checked = 0
    for workflow in sorted(Path('.github/workflows').glob('*.yml')):
        text = workflow.read_text()
        if "Stage the approved hosted input bundle" not in text:
            continue
        source = text.split("          python - <<'PYCODE'\n", 1)[1].split('          PYCODE', 1)[0]
        source = '\n'.join(line[10:] for line in source.splitlines())
        compile(source, str(workflow), 'exec')
        for kind in ('valid', 'digest', 'traversal', 'backslash', 'symlink'):
            with tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                destination = root / 'approved-input'
                destination.mkdir()
                archive = destination / 'fixture.zip'
                member = zipfile.ZipInfo({
                    'traversal': '../escaped.txt', 'backslash': 'bad\\file',
                }.get(kind, 'wheels/fixture.txt'))
                if kind == 'symlink':
                    member.create_system = 3
                    member.external_attr = (stat.S_IFLNK | 0o777) << 16
                with zipfile.ZipFile(archive, 'w') as bundle:
                    bundle.writestr(member, 'offline synthetic input')
                digest = hashlib.sha256(archive.read_bytes()).hexdigest()
                env = dict(os.environ, RUNNER_TEMP=str(root), HOSTED_INPUT_ASSET=archive.name,
                           HOSTED_INPUT_SHA256='0' * 64 if kind == 'digest' else digest)
                result = subprocess.run([sys.executable, '-c', source], cwd=root, env=env,
                                        capture_output=True, timeout=20, check=False)
                if (result.returncode == 0) != (kind == 'valid'):
                    raise SystemExit(f'{workflow.name}: {kind} staging acceptance failed')
                if kind == 'valid':
                    assert (root / 'hosted-inputs/wheels/fixture.txt').is_file()
                else:
                    assert not (root / 'hosted-inputs').exists()
                    assert not (root / 'escaped.txt').exists()
                checked += 1
    if not checked:
        raise SystemExit('no hosted staging code was checked')
    print(f'Hosted input staging: {checked} offline cases passed')


if __name__ == '__main__':
    main()
