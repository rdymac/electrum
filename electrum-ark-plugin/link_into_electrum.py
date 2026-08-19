#!/usr/bin/env python3
"""Link this standalone plugin into an Electrum source tree.

Electrum 4.1 loads plugins from electrum/plugins/<name>/. This project lives
outside that tree on purpose. Run this script to create a symlink (or Windows
directory junction) so Electrum can see the Ark plugin.

Examples:

    python link_into_electrum.py
    python link_into_electrum.py --electrum C:\\Users\\DELL\\Desktop\\Cursor\\GitHub\\electrum
"""

from __future__ import print_function

import argparse
import os
import sys


def default_electrum_root():
    here = os.path.abspath(os.path.dirname(__file__))
    parent = os.path.dirname(here)
    candidate = os.path.join(parent, 'electrum')
    if os.path.isdir(os.path.join(parent, 'electrum', 'plugins')):
        return parent
    if os.path.isdir(os.path.join(here, '..', 'electrum', 'electrum', 'plugins')):
        return os.path.abspath(os.path.join(here, '..', 'electrum'))
    # This repo is itself an Electrum checkout (plugin folder at workspace root).
    if os.path.isdir(os.path.join(parent, 'electrum', 'plugin.py')):
        return parent
    return parent


def link(src, dest):
    if os.path.lexists(dest):
        if os.path.islink(dest) or os.path.isdir(dest):
            print('Already present: %s' % dest)
            return dest
        raise SystemExit('Refusing to overwrite %s' % dest)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    if os.name == 'nt':
        try:
            os.symlink(src, dest, target_is_directory=True)
        except OSError:
            # Junctions do not require Administrator on modern Windows.
            import subprocess
            subprocess.check_call(['cmd', '/c', 'mklink', '/J', dest, src])
    else:
        os.symlink(src, dest)
    print('Linked %s -> %s' % (dest, src))
    return dest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        '--electrum',
        default=os.environ.get('ELECTRUM_ROOT') or default_electrum_root(),
        help='Path to the Electrum repository root',
    )
    args = parser.parse_args(argv)
    plugin_src = os.path.abspath(os.path.join(os.path.dirname(__file__), 'ark'))
    electrum_root = os.path.abspath(args.electrum)
    dest = os.path.join(electrum_root, 'electrum', 'plugins', 'ark')
    if not os.path.isdir(os.path.join(electrum_root, 'electrum', 'plugins')):
        raise SystemExit('Not an Electrum source tree: %s' % electrum_root)
    if not os.path.isdir(plugin_src):
        raise SystemExit('Plugin package missing: %s' % plugin_src)
    link(plugin_src, dest)
    print('Enable the plugin in Electrum: Tools → Plugins → Ark')
    return 0


if __name__ == '__main__':
    sys.exit(main())
