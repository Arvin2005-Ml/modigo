"""Create the exact Liara upload ZIP, excluding local environments and credentials."""
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
FILES = (
    'Dockerfile', '.dockerignore', '.liaraignore', 'liara.json',
    'scripts/container.py', 'apps/api/requirements.lock',
    'DRAMMA_450_activities_fa.json',
    'content/cooked-examples.md', 'content/demo-extra.json',
    'content/demo-catalog.json', 'content/demo-cook-fixtures.json',
    'apps/web/package.json', 'apps/web/package-lock.json',
    'apps/web/next.config.mjs', 'apps/web/next-env.d.ts', 'apps/web/tsconfig.json',
    'apps/web/postcss.config.mjs', 'apps/web/tailwind.config.ts',
)
DIRECTORIES = ('apps/api/app', 'apps/web/app', 'apps/web/components',
               'apps/web/lib', 'apps/web/public')


def deploy_files(root):
    paths = [root / name for name in FILES]
    paths += [path for name in DIRECTORIES for path in (root / name).rglob('*') if path.is_file()]
    for path in sorted(paths):
        relative = path.relative_to(root)
        if any(part.startswith('.') or part in ('__pycache__', 'node_modules') for part in relative.parts):
            if relative.as_posix() not in ('.dockerignore', '.liaraignore'):
                continue
        if path.suffix in ('.pyc', '.pyo', '.log', '.key', '.pem'):
            continue
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ValueError('Deployment source must not contain symlinks')
        if not path.is_file():
            raise ValueError(f'Missing deployment source: {relative}')
        yield path, relative.as_posix()


def package(root=ROOT):
    destination = root / 'dist/funilo-liara.zip'
    destination.parent.mkdir(parents=True, exist_ok=True)
    paths = list(deploy_files(root))
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as archive:
        for path, name in paths:
            archive.write(path, name)
    return destination, len(paths)


if __name__ == '__main__':
    destination, count = package()
    print(f'Created {destination.relative_to(ROOT)} ({count} files)')
