#!/usr/bin/env python3
#
# Copyright (c) 2017, Thomas Farr
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""bin2s.py: Convert binary files to GCC asm modules.

For gfx/foo.bin it will write foo_bin (an array of char), foo_bin_end, and foo_bin_len (an unsigned int).
For 4bit.chr it will write _4bit_chr, _4bit_chr_end, and _4bit_chr_len.

Ported to python from https://github.com/devkitPro/general-tools/blob/master/bin2s.c"""


from optparse import OptionParser
import os.path
import re
import sys


_default_alignment = 4
_default_line_length = 16
_assembly_template = '''\
/* Generated by BIN2S - please don't edit directly */
  .section .rodata
  .balign {alignment}
  .global {identifier}_size
  .global {identifier}
{identifier}:
{data}

  .global {identifier}_end
{identifier}_end:

  .align
{identifier}_size: .int {size}
'''


def safe_identifier(src):
    return re.sub(r'^(\d)', '_\\1', re.sub(r'[./-]', '_', re.sub(r'[^A-Za-z0-9_./-]', '', src)))


def bin2s(file_path, alignment=_default_alignment, line_length=_default_line_length, output=sys.stdout):
    try:
        with open(file_path, 'rb') as fin:
            fin.seek(0, 2)
            file_len = fin.tell()
            fin.seek(0)

            if file_len == 0:
                print('bin2s: warning: skipping empty file \'%s\'' % file_path, file=sys.stderr)
                return True

            data = ''
            count = file_len
            while count > 0:
                line_bytes = fin.read(line_length)
                data += '  .byte %s\n' % ','.join(map(lambda b: '%3u' % b, line_bytes))
                count -= len(line_bytes)
            data = data[:-1]

            identifier = safe_identifier(os.path.basename(file_path))

            print(_assembly_template.format(identifier=identifier, alignment=alignment, data=data, size=file_len),
                  end='', file=output)

            return True
    except IOError as e:
        print('bin2s: error: could not open \'%s\': %s' % (file_path, e.strerror), file=sys.stderr)
        return False


def main():
    parser = OptionParser(usage='Usage: %prog [options] <files...>')
    parser.add_option('-a', '--alignment',
                      help='Boundary alignment, in bytes [default: %default]',
                      dest='alignment', type='int', default=_default_alignment)
    parser.add_option('-l', '--line-length',
                      help='Length of data lines to output, in bytes [default: %default]',
                      dest='line_length', type='int', default=_default_line_length)
    parser.add_option('-o', '--output',
                      help='Output file [default: %default]',
                      dest='output', default='-')
    (options, args) = parser.parse_args()

    alignment = _default_alignment if options.alignment <= 0 else options.alignment
    line_length = _default_line_length if options.line_length <= 0 else options.line_length

    if len(args) == 0:
        parser.print_usage()
        return 1

    try:
        output = open(options.output, 'w') if options.output != '-' else sys.stdout
    except IOError as e:
        print('bin2s: error: could not open \'%s\' for writing: %s' % (options.output, e.strerror),
              file=sys.stderr)
        return 1

    for file_path in args:
        if not bin2s(file_path, alignment=alignment, line_length=line_length, output=output):
            return 1

    if options.output != '-':
        output.close()

if __name__ == '__main__':
    sys.exit(main())