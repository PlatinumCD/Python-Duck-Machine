"""
Duck Machine model DM2018S CPU
"""

from instr_format import Instruction, OpCode, CondFlag, decode
from memory import Memory
from register import Register, ZeroRegister
from alu import ALU
from mvc import MVCEvent, MVCListenable

from typing import List, Tuple

import logging
logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

class CPUStep(MVCEvent):
    """CPU is beginning step with PC at a given address"""

    def __init__(self, subject: "CPU", pc_addr: int,
                 instr_word: int, instr: Instruction)-> None:
        self.subject = subject
        self.pc_addr = pc_addr
        self.instr_word = instr_word
        self.instr = instr

class CPU(MVCListenable):
    """The CPU is converts instructions into actions. This CPU contains 16 registers."""

    def __init__(self, memory):
        super().__init__()
        self.memory = memory
        self.alu = ALU()
        self.registers = [ZeroRegister(), Register(), Register(), Register(),
                          Register(), Register(), Register(), Register(),
                          Register(), Register(), Register(), Register(),
                          Register(), Register(), Register(), Register()]

        self.pc = self.registers[15]
        self.condition = CondFlag.ALWAYS
        self.halted = False

    def step(self) -> None:
        """Each step of the CPU is performed here"""

        word = self.memory.get(self.pc.get())

        instr = decode(word)

        self.notify_all(CPUStep(self, self.pc.get(), word, instr))

        if self.condition & instr.cond:
            regsrc1 = self.registers[instr.reg_src1].get()
            regsrc2 = self.registers[instr.reg_src2].get()
            regsrc2 = regsrc2 + instr.offset

            self.pc.put(self.pc.get() + 1)

            result, condition = ALU().exec(instr.op, regsrc1, regsrc2)
            self.condition = condition

            if instr.op == OpCode.LOAD:
                self.registers[instr.reg_target].put(self.memory.get(result))
            elif instr.op == OpCode.STORE:
                self.memory.put(result, self.registers[instr.reg_target].get())
            elif instr.op == OpCode.HALT:
                self.halted = True
            else:
                self.registers[instr.reg_target].put(result)
        else:
            self.pc.put(self.pc.get() + 1)
        return

    def run(self, from_addr=0, single_step=False) -> None:
        """This method starts the CPU from a specific memory address"""
        step_count = 1
        self.pc.put(from_addr)
        while not self.halted:
            self.step() #self.step()
            if single_step:
                input("Step {}; press enter".format(step_count))
                step_count += 1

# Create a class CPU, subclassing MVCListenable.
# It should have 16 registers (a list of Register objects),
# and the first of them should be the special ZeroRegister
# object that is always zero regardless of what is stored.
# It should have a CondFlag with the current condition.
# It should have a boolean "Halted" flag, and execution of
# the "run" method should halt with the Halted flag is True
# (set by the HALT instruction). The CPU does not contain
# the memory, but has a connection to a Memory object
# (specifically a MemoryMappedIO object).
# See the project web page for more guidance. 

