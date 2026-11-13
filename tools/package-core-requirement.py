#!/usr/bin/env python3
"""Read the WCF minimum version by package identity, not dependency order."""
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def read_requirement(path):
    root = ET.parse(path).getroot()
    for parent in root:
        if parent.tag.rsplit('}', 1)[-1] != 'requiredpackages':
            continue
        for node in parent:
            if node.tag.rsplit('}', 1)[-1] == 'requiredpackage' and (node.text or '').strip() == 'com.woltlab.wcf':
                return node.get('minversion', '')
    return ''


if __name__ == '__main__':
    try:
        print(read_requirement(Path(sys.argv[1])))
    except (OSError, ET.ParseError, IndexError) as error:
        print(f'Cannot read WCF requirement: {error}', file=sys.stderr)
        raise SystemExit(1)
