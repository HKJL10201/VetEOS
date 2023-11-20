from veteos.octopus.arch.wasm.instruction import WasmInstruction


class VetInstruction(WasmInstruction):
    '''
    VetEOS Instruction, for instruction initialization (WIP)
    '''

    def __init__(self, instruction: WasmInstruction):
        # super().__init__(instruction.opcode, instruction.name, instruction.imm_struct,
        #                  instruction.operand_size, instruction.insn_byte, instruction.pops,
        #                  instruction.pushes, instruction.description,
        #                  instruction.operand_interpretation, instruction.offset)
        self.opcode = instruction.opcode
        self.offset = instruction.offset
        self.name = instruction.name
        self.description = instruction.description
        self.operand_size = instruction.operand_size
        self.operand = instruction.operand
        self.operand_interpretation = instruction.operand_interpretation
        self.insn_byte = instruction.insn_byte
        self.pops = instruction.pops
        self.pushes = instruction.pushes
        self.imm_struct = instruction.imm_struct
        self.xref = instruction.xref
        self.ssa = instruction.ssa

        self.dataflow = None

    @property
    def is_eq(self) -> bool:
        '''
        return true if instruction is `eq`
        '''
        return '.eq' in self.name

    @property
    def is_ne(self) -> bool:
        '''
        return true if instruction is `ne`
        '''
        return '.ne' in self.name and 'neg' not in self.name and 'nea' not in self.name

    @property
    def is_lt(self) -> bool:
        '''
        return true if instruction is `lt`
        '''
        return '.lt' in self.name

    @property
    def is_gt(self) -> bool:
        '''
        return true if instruction is `gt`
        '''
        return '.gt' in self.name

    @property
    def is_le(self) -> bool:
        '''
        return true if instruction is `le`
        '''
        return '.le' in self.name

    @property
    def is_ge(self) -> bool:
        '''
        return true if instruction is `ge`
        '''
        return '.ge' in self.name and 'get' not in self.name

    @property
    def is_cmp_ins(self) -> bool:
        '''
        return true if instruction is comparison
        '''
        return self.is_eq or self.is_ne or self.is_lt or self.is_gt or self.is_le or self.is_ge

    @property
    def is_load_ins(self) -> bool:
        '''
        return true if instruction is `load`
        '''
        return 'load' in self.name

    @property
    def is_store_ins(self) -> bool:
        '''
        return true if instruction is `store`
        '''
        return 'store' in self.name

    @property
    def is_call_ins(self) -> bool:
        '''
        return true if instruction is `call`
        '''
        return 'call' in self.name

    @property
    def is_constant_ins(self) -> bool:
        '''
        return true if instruction is constant
        '''
        return 'const' in self.name

    @property
    def is_get_local_ins(self) -> bool:
        '''
        return true if instruction is `get local`
        '''
        return 'get_local' in self.name

    @property
    def is_get_global_ins(self) -> bool:
        '''
        return true if instruction is `get global`
        '''
        return 'get_global' in self.name

    @property
    def is_set_tee_ins(self) -> bool:
        '''
        return true if instruction is `set` or `tee`
        '''
        return 'set' in self.name or 'tee' in self.name

    @property
    def is_return_ins(self) -> bool:
        '''
        return true if instruction is `return`
        '''
        return self.name == 'return'

    @property
    def is_drop_ins(self) -> bool:
        '''
        return true if instruction is `drop`
        '''
        return self.name == 'drop'

    def get_ins_interpretation(self) -> str:
        '''
        return the operand_interpretation of an Instruction
        '''
        return self.operand_interpretation if self.operand_interpretation != None else self.name

    def get_local_global_name(self) -> str:
        '''
        return the local/global variable name, e.g. "local 0"
        '''
        return self.operand_interpretation.split('_')[-1]

    def set_dataflow(self, data: str):
        '''
        add dataflow information as strings
        '''
        self.dataflow = ' [%s]' % data
