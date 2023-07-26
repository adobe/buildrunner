
import importlib.machinery
import os
import subprocess
import types

SOURCE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

BUILDRUNNER_DIR = os.path.join(SOURCE_DIR, 'buildrunner')
VERSION_FILE = os.path.join(BUILDRUNNER_DIR, 'version.py')
BASE_VERSION = '3.0'

def get_version(print_output=True):
    """
    Call out to the git command line to get the current commit "number".
    """
    if os.path.exists(VERSION_FILE):
        # Read version from file
        loader = importlib.machinery.SourceFileLoader('buildrunner_version', VERSION_FILE)
        version_mod = types.ModuleType(loader.name)
        loader.exec_module(version_mod)
        existing_version = version_mod.__version__  # pylint: disable=no-member
        if print_output:
            print(f'Using existing buildrunner version: {existing_version}')
        return existing_version

    # Generate the version from the base version and the git commit number, then store it in the file
    try:
        cmd = subprocess.Popen(
            args=[
                'git',
                'rev-list',
                '--count',
                'HEAD',
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf8',
        )
        stdout = cmd.communicate()[0]
        output = stdout.strip()
        if cmd.returncode == 0:
            new_version = '{0}.{1}'.format(BASE_VERSION, output)
            print(f'Setting version to {new_version}')

            # write the version file
            if os.path.exists(BUILDRUNNER_DIR):
                with open(VERSION_FILE, 'w', encoding='utf8') as _fobj:
                    _fobj.write("__version__ = '%s'\n" % new_version)
            return new_version
    except Exception as exc:  # pylint: disable=broad-except
        if print_output:
            print(f'Could not generate version from git commits: {exc}')
    # If all else fails, use development version
    return f'{BASE_VERSION}.DEVELOPMENT'

if __name__ == '__main__':
    print(get_version(False))