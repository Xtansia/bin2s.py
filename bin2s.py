#!/usr/bin/env python3
#
# Copyright (c) 2017, Thomas Farr
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.

"""Convert binary data/files to GCC assembly modules.

Ported to python from:
https://github.com/devkitPro/general-tools/blob/master/bin2s.c

"""


import argparse
from os.path import basename
import re
import sys
from textwrap import dedent
from typing import IO


def sanitize_identifier(identifier: str) -> str:
    """Sanitizes a C identifier.

    It will do the following:
        * Strip all characters that are not ASCII leters, digits
          or in ``_-./``
        * Replace all of the characters ``-./`` with ``_``
        * Prepend ``_`` if the remaining identifier begins with a digit

    Args:
        identifier: The identifier to sanitize.

    Returns:
        The sanitized identifier.

    Raises:
        ValueError: If `identifier` doesn't contain any legal characters.

    Examples:
        >>> from bin2s import sanitize_identifier
        >>> sanitize_identifier('foo.bin')
        'foo_bin'
        >>> sanitize_identifier('4bit.chr')
        '_4bit_chr'
        >>> sanitize_identifier('$bar$8')
        'bar8'
        >>> sanitize_identifier('~~13/boo')
        '_13_boo'

    """

    identifier = re.sub(r'[^A-Za-z0-9_./-]', '', identifier)

    if len(identifier) == 0:
        raise ValueError('identifier doesn\'t contain any legal characters')

    return re.sub(r'^(\d)', '_\\1', re.sub(r'[./-]', '_', identifier))


def bin2s(identifier: str, input: IO[bytes], output: IO[str],
          alignment: int = 4, line_length: int = 16) -> bool:
    """Convert binary data to a GCC assembly module.

    Will write assembly that defines the following:
        * ``{identifier}``:
            An array of bytes containing the data.
        * ``{identifier}_end``:
            Will be at the location directly after the end of the data.
        * ``{identifier}_size``:
            An unsigned int containing the length of the data in bytes.

    Which is roughly equivalent to this pseudocode:

    .. code-block:: c

        unsigned int identifier_size = ...
        unsigned char identifier[identifier_size] = { ... }
        unsigned char identifier_end[] = identifier + identifier_size

    Args:
        identifier: The identifier to use, will be sanitized with
            :func:`sanitize_identifier`.
        input: The input stream.
        output: The output stream.
        alignment: The boundary alignment, measured in bytes. Must be greater
            than 0.
        line_length: The number of bytes to output per line of assembly. Must
            be greater than 0.

    Returns:
        True if assembly was written. False if `input` has 0 readable bytes.

    Raises:
        ValueError: If `alignment` or `line_length` are not greater than 0.

    Examples:
        >>> from bin2s import bin2s
        >>> from io import BytesIO, StringIO
        >>> output = StringIO()
        >>> bin2s('empty', BytesIO(b''), output)
        False
        >>> bin2s('hello_world', BytesIO(b'Hello World'), output)
        True
        >>> print(output.getvalue())
          .section .rodata
          .balign 4
          .global hello_world
          .global hello_world_end
          .global hello_world_size
        <BLANKLINE>
        hello_world:
          .byte  72,101,108,108,111, 32, 87,111,114,108,100
        <BLANKLINE>
        hello_world_end:
        <BLANKLINE>
          .align
        hello_world_size: .int 11
        <BLANKLINE>

    """

    if not alignment > 0:
        raise ValueError('alignment must be greater than 0')
    if not line_length > 0:
        raise ValueError('line_length must be greater than 0')

    identifier = sanitize_identifier(identifier)

    cur_pos = input.tell()
    input.seek(0, 2)
    size = input.tell() - cur_pos
    input.seek(cur_pos)

    if size == 0:
        return False

    def fprint(string, end='\n'):
        print(string, end=end, file=output)

    fprint(dedent('''\
                    .section .rodata
                    .balign %(align)d
                    .global %(ident)s
                    .global %(ident)s_end
                    .global %(ident)s_size

                  %(ident)s:''' % {'align': alignment, 'ident': identifier}))

    remaining = size
    while remaining > 0:
        read_bytes = input.read(line_length)
        fprint('  .byte ' + ','.join(['%3u' % b for b in read_bytes]))
        remaining -= len(read_bytes)

    fprint(dedent('''
                  %(ident)s_end:

                    .align
                  %(ident)s_size: .int %(size)lu''' % {'ident': identifier,
                                                       'size': size}))

    return True


if __name__ == '__main__':
    def positive_int(string: str) -> int:
        try:
            value = int(string)
            assert(value > 0)
            return value
        except:
            raise argparse.ArgumentTypeError(
                '%r is not a positive int' % string)

    parser = argparse.ArgumentParser(
        description='''\
Convert binary files to GCC assembly modules.

For each input file it will output assembly defining:

    * {identifier}:
        An array of bytes containing the data.
    * {identifier}_end:
        Will be at the location directly after the end of the data.
    * {identifier}_size:
        An unsigned int containing the length of the data in bytes.

Roughly equivalent to this pseudocode:

    unsigned int identifier_size = ...
    unsigned char identifier[identifier_size] = { ... }
    unsigned char identifier_end[] = identifier + identifier_size

Where {identifier} is the input file's name,
sanitized to produce a legal C identifier, by doing the following:

    * Stripping all character that are not ASCII letters, digits or one of _-./
    * Replacing all of -./ with _
    * Prepending _ if the remaining identifier begins with a digit.

e.g. for gfx/foo.bin {identifier} will be foo_bin,
     and for 4bit.chr it will be _4bit_chr.
''',
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('files',
                        metavar='FILE', nargs='+',
                        type=argparse.FileType('rb'),
                        help='Binary file to convert to GCC assembly')
    parser.add_argument('-a', '--alignment',
                        dest='alignment', type=positive_int, default=4,
                        help='Boundary alignment, in bytes '
                             '[default: %(default)s]')
    parser.add_argument('-l', '--line-length',
                        dest='line_length', type=positive_int, default=16,
                        help='Length of data lines to output, in bytes '
                             '[default: %(default)s]')
    parser.add_argument('-o', '--output',
                        dest='output', type=argparse.FileType('w'),
                        help='Output file, writes to stdout if not provided')
    args = parser.parse_args()

    prog_name = basename(sys.argv[0])

    output = sys.stdout if not args.output else args.output

    print('/* Generated by %s - please don\'t edit manually */' % prog_name,
          file=output)

    for file in args.files:
        if not bin2s(basename(file.name), file, output,
                     alignment=args.alignment, line_length=args.line_length):
            print('%s: warning: skipping empty file %r' % (prog_name,
                                                           file.name),
                  file=sys.stderr)
        file.close()

    if output is not sys.stdout:
        output.close()
