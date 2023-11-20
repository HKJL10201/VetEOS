from veteos.octopus.arch.wasm.cfg import Function
from veteos.instruction import VetInstruction
from veteos.node import Node
from veteos.utils import *
from veteos.core import *


class VetFunction(Function):
    '''
    VetEOS Function, for function initialization (WIP)
    '''

    def __init__(self, function: Function, contract, ssa: bool = True):
        # super().__init__(function.start_offset, function.start_instr,
        #                  function.name, function.prefered_name)
        self.start_offset = function.start_offset
        self.start_instr = function.start_instr
        self.name = function.name
        self.prefered_name = function.prefered_name
        self.size = function.size
        self.end_offset = function.end_offset
        self.end_instr = function.end_instr
        self.basicblocks = function.basicblocks
        self.instructions = function.instructions

        self.function = function
        self.BasicBlockNet = {}
        self.sorted_basicblocks = []
        self.vet_instructions = []
        self.offset2instr = {}
        self.instr2block = {}
        self.return_values = []
        self.param = None
        self.param_num = None
        self.param_size = None
        self.stack_size = None

        def init_instructions():
            for i in self.instructions:
                vet_ins = VetInstruction(i)
                self.vet_instructions.append(vet_ins)
                self.offset2instr[i.offset] = vet_ins

        def init_return_values():
            self.return_values = contract.get_return_values()
            for vet_ins in self.vet_instructions:
                if vet_ins.is_return_ins:
                    if vet_ins.ssa.args:
                        for a in vet_ins.ssa.args:
                            addi(a, self.return_values)

        def init_basicblocks():
            for b in self.basicblocks:
                # TODO: the format_block_name adding zeros, error occur
                # key = self.format_block_name(b.name)
                key = b.name
                if key not in self.BasicBlockNet.keys():
                    self.BasicBlockNet[key] = Node(b)
            edges = contract.get_edges([self.name])

            for e in edges:
                # TODO: the format_block_name adding zeros, error occur
                # parent = self.format_block_name(e.node_from)
                # child = self.format_block_name(e.node_to)
                parent = e.node_from
                child = e.node_to
                if parent not in self.BasicBlockNet.keys():
                    print(parent)
                    print(list(self.BasicBlockNet.keys()))
                addi(child, self.BasicBlockNet[parent].children)
                addi(parent, self.BasicBlockNet[child].parents)

            for k in sorted(self.BasicBlockNet.keys()):
                self.sorted_basicblocks.append(self.BasicBlockNet[k].data)
                for i in self.BasicBlockNet[k].data.instructions:
                    self.instr2block[i.offset] = self.BasicBlockNet[k].data.name

        init_instructions()
        if ssa:
            init_return_values()
            init_basicblocks()

    def format_block_name(self, name: str) -> str:
        '''
        adding zeros before the block number
        '''
        max_ins = len('%x' % (self.vet_instructions[-1].offset))
        si = name.rfind('_')+1
        bn = name[si:]
        bn = '0'*(max_ins-len(bn))+bn
        return name[:si]+bn

    def print_net(self):
        '''
        print the basic block net
        '''
        for k in sorted(self.BasicBlockNet.keys()):
            print(k+':'+str(self.BasicBlockNet[k]))

    def get_memo_instr(self) -> list:
        '''
        get all instructions related to memory operations
        '''
        memo_ins = []
        for i in self.get_instructions():
            if i.is_load_ins or i.is_store_ins:
                addi(i, memo_ins)
        return memo_ins

    def init_param(self):
        '''
        initialize function parameters
        '''
        if self.param == None:
            fn = self.prefered_name
            self.param = fn[fn.index('(')+1:fn.index(')')].split()
            self.param_num = len(self.param)
            param_size = []
            for pa in self.param:
                if '32' in pa:
                    param_size.append(4)
                elif '64' in pa:
                    param_size.append(8)
            self.param_size = param_size

    def get_param(self) -> list:
        '''
        return the parameters
        '''
        if self.param == None:
            self.init_param()
        return self.param

    def get_param_num(self) -> int:
        '''
        return the parameters
        '''
        if self.param_num == None:
            self.init_param()
        return self.param_num

    def get_param_size(self) -> list:
        '''
        return the parameters
        '''
        if self.param_size == None:
            self.init_param()
        return self.param_size

    def get_stack_size(self) -> int:
        '''
        return the size of function stack
        '''
        if self.stack_size == None:
            instrs = self.vet_instructions
            for idx, ins in enumerate(instrs):
                if ins.is_get_global_ins and idx+2 < len(instrs):
                    if 'i32.const' in instrs[idx+1].name \
                            and 'i32.sub' in instrs[idx+2].name:
                        res = instrs[idx+1].get_ins_interpretation().split()[1]
                        self.stack_size = int(res)
                        return self.stack_size
            self.stack_size = -1  # cannot determine
        return self.stack_size

    def get_instructions(self) -> list:
        return self.vet_instructions

    def is_parameter(self, instr: VetInstruction) -> bool:
        '''
        determine if an instruction is reading parameters
        '''
        if instr.is_get_local_ins:
            pn = self.get_param_num()
            para_index = instr.get_ins_interpretation().split()[1]
            # if int(para_index) < pn-1:
            if int(para_index) < pn:
                return True
        elif instr.is_load_ins:
            stack_size = self.get_stack_size()
            offset = int(instr.get_ins_interpretation().split()[-1])
            param_size = sum(self.get_param_size())
            if offset >= stack_size-param_size:
                return True
        return False

    def set_local_ssa(self, num: str):
        '''
        set ssa format dataflow
        '''
        local = 'local '+str(num)
        localssa = local_ssa(local, self.BasicBlockNet)
        for i in localssa:
            i.data.set_dataflow(str(i))
        return

    def writeback_instructions(self):
        '''
        write VetInstruction objects to original Instructions (CFG generation)
        '''
        for basicblock in self.function.basicblocks:
            new_ins = []
            for ins in basicblock.instructions:
                offset = ins.offset
                new_ins.append(self.offset2instr[offset])
            basicblock.instructions = new_ins
