"""
Author: Cameron Ford Durbin

Assembler for DM2018W assembly language.

This assembler is for fully resolved instructions,
which may be the output of assm_xform.py, which
transforms instructions with symbolic addresses into
instructions with fully resolved (PC-relative) addresses.
"""
from instr_format import Instruction, instruction_from_dict
import memory
import argparse

from typing import Union, List
from enum import Enum, auto

import sys
import io
import re
import logging
logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

# Configuration constants
ERROR_LIMIT = 5    # Abandon assembly if we exceed this

# Exceptions raised by this module
class SyntaxError(Exception):
    pass

###
# The whole instruction line is encoded as a single
# regex with capture names for the parts we might
# refer to. Error messages will be crappy (we'll only
# know that the pattern didn't match, and not why), but
# we get a very simple match/process cycle.  By creating
# a dict containing the captured fields, we can determine
# which optional parts are present (e.g., there could be
# label without an instruction or an instruction without
# a label).
###


# To simplify client code, we'd like to return a dict with
# the right fields even if the line is syntactically incorrect.
DICT_NO_MATCH = { 'label': None, 'opcode': None, 'predicate': None,
                      'target': None, 'src1': None, 'src2': None,
                      'offset': None, 'comment': None }


###
# Although the DM2018W instruction set is very simple, a source
# line can still come in several forms.  Each form (even comments)
# can start with a label.
###

class AsmSrcKind(Enum):
    """Distinguish which kind of assembly language instruction
    we have matched.  Each element of the enum corresponds to
    one of the regular expressions below.
    """
    # Blank or just a comment, optionally
    # with a label
    COMMENT = auto()
    # Fully specified  (all addresses resolved)
    FULL = auto()
    # A data location, not an instruction
    DATA = auto()
    SYMBOL = auto()

ASM_SYMBOL_PAT = re.compile(r"""
   # Optional label 
   (
     (?P<label> [a-zA-Z]\w*):
   )?
   # The instruction proper 
   \s*
    (?P<opcode>    LOAD | STORE | JUMP)           # Opcode
    (/ (?P<predicate> [a-zA-Z]+) )?   # Predicate (optional)
    \s+
    ( (?P<target>   r[0-9]+), )?
    (?P<symbol> [\w]+)    # Offset (optional)
   # Optional comment follows # or ; 
   (
     \s*
     (?P<comment>[\#;].*)
   )?       
   \s*$             
   """, re.VERBOSE)

ASM_COMMENT_PAT = re.compile(r"""
   # Optional label 
   (
     (?P<label> [a-zA-Z]\w*):
   )?
   \s*
   # Optional comment follows # or ; 
   (
     (?P<comment>[\#;].*)
   )?       
   \s*$             
   """, re.VERBOSE)

# Instructions with fully specified fields. We can generate
# code directly from these.  In the transformation phase we
# pass these through unchanged, just keeping track of how much
# room they require in the final object code.
ASM_FULL_PAT = re.compile(r"""
   # Optional label 
   (
     (?P<label> [a-zA-Z]\w*):
   )?
   # The instruction proper 
   \s*
    (?P<opcode>    [a-zA-Z]+)           # Opcode
    (/ (?P<predicate> [a-zA-Z]+) )?   # Predicate (optional)
    \s+
    (?P<target>    r[0-9]+),            # Target register
    (?P<src1>      r[0-9]+),            # Source register 1
    (?P<src2>      r[0-9]+)             # Source register 2
    (\[ (?P<offset>[-]?[0-9]+) \])?     # Offset (optional)
   # Optional comment follows # or ; 
   (
     \s*
     (?P<comment>[\#;].*)
   )?       
   \s*$             
   """, re.VERBOSE)

# Defaults for values that ASM_FULL_PAT makes optional
INSTR_DEFAULTS = [ ('predicate', 'ALWAYS'), ('offset', '0') ]

# A data word in memory; not a DM2018W instruction
#
ASM_DATA_PAT = re.compile(r""" 
   # Optional label 
   (
     (?P<label> [a-zA-Z]\w*):
   )?
   # The instruction proper  
   \s*
    (?P<opcode>    DATA)           # Opcode
   # Optional data value
   \s*
   (?P<value>  (0x[a-fA-F0-9]+)
             | ([0-9]+))?
    # Optional comment follows # or ; 
   (
     \s*
     (?P<comment>[\#;].*)
   )?       
   \s*$             
   """, re.VERBOSE)


PATTERNS = [(ASM_FULL_PAT, AsmSrcKind.FULL),
            (ASM_DATA_PAT, AsmSrcKind.DATA),
            (ASM_COMMENT_PAT, AsmSrcKind.COMMENT),
            (ASM_SYMBOL_PAT, AsmSrcKind.SYMBOL)
            ]

def parse_line(line: str) -> dict:
    """Parse one line of assembly code.
    Returns a dict containing the matched fields,
    some of which may be empty.  Raises SyntaxError
    if the line does not match assembly language
    syntax. Sets the 'kind' field to indicate
    which of the patterns was matched.
    """
    log.debug("\nParsing assembler line: '{}'".format(line))
    # Try each kind of pattern
    for pattern, kind in PATTERNS:
        match = pattern.fullmatch(line)
        if match:
            fields = match.groupdict()
            fields["kind"] = kind
            log.debug("Extracted fields {}".format(fields))
            return fields
    raise SyntaxError("Assembler syntax error in {}".format(line))

def value_parse(int_literal: str) -> int:
    """Parse an integer literal that could look like
    42 or like 0x2a
    """
    if int_literal.startswith("0x"):
        return int(int_literal, 16)
    else:
        return int(int_literal, 10)

def fill_defaults(fields: dict) -> None:
    """Fill in default values for optional fields of instruction"""
    for key, value in INSTR_DEFAULTS:
        if fields[key] == None:
            fields[key] = value


def build_table(lines) -> dict:
    """
    This function returns a dictionary of
    labelled variables and their respected PC - addresses.
    """
    datadict = {}
    address = 0
    for lnum in range(len(lines)):
        line = lines[lnum]
        try:
            fields = parse_line(line)
            if bool(fields["label"]):
                datadict[fields["label"]] = address
                if fields["kind"] != AsmSrcKind.COMMENT:
                    address +=1
            elif fields["kind"] != AsmSrcKind.COMMENT:
                address += 1
        except SyntaxError as e:
            print("Syntax error in line {}: {}".format(lnum, line))
        except KeyError as e:
            print("Unknown word in line {}: {}".format(lnum, e))
        except Exception as e:
            print("Exception encountered in line {}: {}".format(lnum, e))
    return datadict


def resolve_line(current_address, fields, sym_table) -> str:
    """This function returns instructions based on the symbol given."""
    new_addr = sym_table[fields['symbol']] - current_address
    opcode = fields['opcode']
    predicate = fields['predicate']
    if opcode == 'JUMP':
        opcode = 'ADD'
        if bool(predicate):
            instr = '{}/{}  r15,r0,r15[{}]'.format(opcode, predicate, new_addr)
        else:
            instr = '{} r15,r0,r15[{}]'.format(opcode, new_addr)
    else:
        target = fields['target']
        instr = '{}   {},r0,r15[{}]'.format(opcode, target, new_addr)
    return instr


def transform_line(lines: List[str], symb_table) -> list:
    """This function formats lines of assembly code into lines
    that meet .dasm standards."""
    address = 0
    instructions = []
    for lnum in range(len(lines)):
        line = lines[lnum]
        try:
            fields = parse_line(line)
            if fields["kind"] == AsmSrcKind.FULL:
                print(fields)
                fill_defaults(fields)
                instr = instruction_from_dict(fields)
                instructions.append(str(instr))
                address += 1
            elif fields["kind"] == AsmSrcKind.SYMBOL:
                print(fields)
                instr = resolve_line(address, fields, symb_table)
                instructions.append(instr)
                address += 1
            elif fields["kind"] == AsmSrcKind.DATA:
                print(fields)
                word = value_parse(fields["value"])
                fields["value"] = word
                instr = '{}:  DATA {}'.format(fields["label"],fields["value"])
                print(instr)
                instructions.append(instr)
                address += 1
            elif fields["kind"] == AsmSrcKind.COMMENT:
               if bool(fields["label"]) & bool(fields["comment"]):
                   instr = '{}:   {}'.format(fields["label"], fields["comment"])
               elif bool(fields["label"]):
                   instr = '{}:'.format(fields["label"])
               else:
                   instr = '{}'.format(fields["comment"])
               instructions.append(instr)
        except SyntaxError as e:
            print("Syntax error in line {}: {}".format(lnum, line))
        except KeyError as e:
            print("Unknown word in line {}: {}".format(lnum, e))
        except Exception as e:
            print("Exception encountered in line {}: {}".format(lnum, e))
    return instructions


def cli() -> object:
    """Get arguments from command line"""
    parser = argparse.ArgumentParser(description="Duck Machine Assembler (pass 1)")
    parser.add_argument("sourcefile", type=argparse.FileType('r'),
                            nargs="?", default=sys.stdin,
                            help="assembly")
    parser.add_argument("objfile", type=argparse.FileType('w'),
                            nargs="?", default=sys.stdout,
                            help="Duck Machine assembly code file")
    args = parser.parse_args()
    return args


def main():
    """"Assemble a Duck Machine program"""
    args = cli()
    lines = args.sourcefile.readlines()
    symb_table = build_table(lines)
    for word in transform_line(lines,symb_table):
        print(word,file=args.objfile)


if __name__ == "__main__":
    main()
