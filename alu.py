"""
The arithmetic logic unit (ALU) is the part of the central
processing unit (CPU, or 'core') that performs arithmetic
operations such as addition, subtraction, etc but also
logical "arithmetic" such as and, or, and shifting.
"""

from instr_format import OpCode, CondFlag
from typing import Tuple


class ALU(object):
    """The arithmetic logic unit (also called a "functional unit"
    in a modern CPU) executes a selected function but does not
    otherwise manage CPU state. A modern CPU core may have several
    ALUs to boost performance by performing multiple operations
    in parallel, but the Duck Machine has just one ALU in one core.
    """
    # The ALU chooses one operation to apply based on a provided
    # operation code. These are just simple functions of two arguments;
    # in hardware we would use a multiplexer circuit to connect the
    # inputs and output to the selected circuitry for each operation.
    ALU_OPS = {
        # Note that DIV is integer division, like // and not like /
        OpCode.ADD: lambda x, y: x + y,
        OpCode.SUB: lambda x, y: x - y,
        OpCode.MUL: lambda x, y: x * y,
        OpCode.DIV: lambda x, y: x // y,
        # For memory access operations load, store, the ALU
        # performs the address calculation
        OpCode.LOAD: lambda x, y: x + y,
        OpCode.STORE: lambda x, y: x + y,
        # Some operations perform no operation
        OpCode.HALT: lambda x, y: 0
    }

    def exec(self, op, in1: int, in2: int) -> Tuple[int, CondFlag]:
        try:
            result = self.ALU_OPS[op](in1, in2)
        except ArithmeticError:
            return 0, CondFlag.V
        except ValueError:
            return 0, CondFlag.V
        if result < 0:
            cc = CondFlag.M
        elif result == 0:
            cc = CondFlag.Z
        elif result > 0:
            cc = CondFlag.P
        else:
            assert False, "Shouldn't reach this point"
        return result, cc
