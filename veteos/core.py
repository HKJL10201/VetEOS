from veteos.instruction import VetInstruction
from veteos.ssa import SSAnode
from veteos.utils import *


def local_ssa(local: str, BasicBlockNet: dict):
    '''
    SSA analysis function
    '''
    local_idx = 0
    block_idx = {}
    res = []
    for k in sorted(BasicBlockNet.keys()):
        b = BasicBlockNet[k].data
        for i in b.instructions:
            i = VetInstruction(i)
            if i.get_ins_interpretation() and local in i.get_ins_interpretation():
                # print(i.ssa.format())
                block = k
                if i.is_set_tee_ins:
                    asmt = i.ssa.method_name.split(
                        '_')[-1].replace(' ', '')+'_'+str(local_idx)
                    block_idx[block] = {'ssa': asmt, 'offset': i.offset}
                    args = ''
                    if i.ssa.args is not None:
                        args += ', '.join('%{:02X}'.format(arg.ssa.new_assignement)
                                          for arg in i.ssa.args)
                    # out=' = '.join([asmt,args])
                    # res.append(out)
                    res.append(SSAnode(i, asmt, args))
                    local_idx += 1
                elif 'get' in i.name:
                    args = merge_local_ssa(block, BasicBlockNet, block_idx, [])
                    if args == '':  # there is no assignment to this local before
                        args = local.replace(' ', '')+'(undefined)'
                    asmt = ''
                    if i.ssa.new_assignement is not None:
                        asmt += '%{:02X}'.format(i.ssa.new_assignement)
                    # out=' = '.join([asmt,args])
                    # res.append(out)
                    res.append(SSAnode(i, asmt, args))
    # printl(res)
    return res


def merge_local_ssa(block: str, Bnet: dict, block_idx: dict, visited: list):
    '''
    the merge step in SSA algorithm
    '''
    if block in block_idx.keys():
        return block_idx[block]['ssa']
    else:
        addi(block, visited)   # mark block as visited
        res = []
        parents = Bnet[block].parents
        if len(parents) == 0:   # no source of local
            return ''
        for p in parents:
            if p in visited:  # avoid loop
                continue
            mer = merge_local_ssa(p, Bnet, block_idx, visited)
            if len(mer) > 0:
                addi(mer, res)
        ssa = ''
        if len(res) > 1:
            ssa += 'Final('+', '.join(res)+')'
        elif len(res) == 1:
            ssa += res[0]
        block_idx[block] = {'ssa': ssa, 'offset': -1}
        return ssa


def memory_ssa(memo: str, BasicBlockNet: dict, ins2blk: dict, memo_ins: list):
    '''
    generate SSA for memory model
    '''
    memo_l = []
    for i in memo_ins:
        if memo in str(i):
            memo_l.append(i)
    local_idx = 0
    block_idx = {}
    res = []
    for m in memo_l:
        i = m.data
        block = ins2blk[i.offset]
        if i.is_store_ins:
            asmt = m.asmt.replace(' ', '')+'_'+str(local_idx)
            block_idx[block] = {'ssa': asmt, 'offset': i.offset}
            res.append(SSAnode(i, asmt, m.args))
            local_idx += 1
        if i.is_load_ins:
            args = merge_local_ssa(block, BasicBlockNet, block_idx, [])
            if len(args) == 0:
                args = m.args.replace(' ', '')
            res.append(SSAnode(i, m.asmt, args))
    # printl(res)
    return res


def get_memory_ssa(memo_instr: list, locals: list, func) -> list:
    '''
    translate 'load' and 'store' instructions: \n
    convert their arguments to 'local(base address) + offset' \n
    parameters:
    - memo_instr: a list containing memory instructions
    - locals: the name of locals related to the memo_instr
    - func: an VetFunction object containing memo_instr
    '''
    # TODO: this function based on an unroubust assumption:
    # the args of load & store are directly linked to the results of local.get
    localssa = []
    # get ssa for all locals
    for local in locals:
        localssa += local_ssa(local, func.BasicBlockNet)
    # convert locals to specific variable names (tanslate load and store)
    res = []
    for i in memo_instr:
        # get the source ins of memo, which is a local.get (or global.get)
        pre_ins = track_prev_all(i.ssa.args[-1], func)  # second para
        local_ins = None
        for p in pre_ins:
            if 'get' in p.name:
                local_ins = p
                break
        local0 = get_ins_ssa(local_ins, localssa)
        istr = i.ssa.format()
        ll = istr.find(',')
        rr = istr.find('(')
        offset = istr[ll+2:rr]
        if i.is_load_ins:
            asmt, _ = istr.split(' = ')
            args = local0+' + '+offset
        elif i.is_store_ins:
            args = istr[rr+1:istr.rfind(',')]
            asmt = local0+' + '+offset
        res.append(SSAnode(i, asmt, args))

    return res


def get_ins_ssa(instr: VetInstruction, ssalist: list) -> str:
    '''
    return the ssa form of the argument of instruction\n
    parameters:
    - instr: the instruction whose argument is local or memo or global 
    (usually a 'get' or 'load' instr)
    - ssalist: a list containing all ssa of the target variable
    '''
    for s in ssalist:
        if instr == s.data:
            return s.args


def get_local_source(instr: VetInstruction, func):
    '''
    return the data source of a local, i.e. return a local.set instruction\n
    parameters:
    - instr: the instruction using a local, i.e. a local.get instruction
    - func: the function containing the instr
    '''
    local = instr.get_local_global_name()
    localssa = local_ssa(local, func.BasicBlockNet)
    # the local in ssa format (with ssa index)
    local0 = get_ins_ssa(instr, localssa)
    if local0 is None:    # cannot find the local (should not happen)
        return None
    for s in localssa:
        if s.asmt == local0:    # found the source
            return s.data
    return None  # source not found


def get_memo_source(instr: VetInstruction, func):
    '''
    return the data source of a memory slot, i.e. return a store instruction\n
    parameters:
    - instr: the instruction loading from memory
    - func: the function containing the instr
    '''
    # TODO: currently only analyze in one single function
    memo_instr = func.get_memo_instr()   # find memory instructions
    locals = get_locals(memo_instr)     # find memory-related locals
    memo_ssa = get_memory_ssa(memo_instr, locals, func)
    # the memo in ssa format (with ssa index)
    memo0 = get_ins_ssa(instr, memo_ssa)
    if memo0 is None:    # cannot find the ins (should not happen)
        return None
    for s in memo_ssa:
        if s.asmt == memo0:    # found the source
            return s.data
    return None  # source not found


def track_prev_all(instr: VetInstruction, func) -> list:
    '''
    return a list containing all previous instructions of an instruction
    parameters:
    - instr: the instruction need to be analyzed
    - func: the function containing the instr
    '''
    # func = emul.get_Func(func_name)
    instr = convert_instruction(instr)
    ins = instr
    res = [ins]
    if ins.is_constant_ins:
        return res
    elif ins.is_get_local_ins:
        # the data comes from a local, usually no arg
        tmp = get_local_source(ins, func)
        if tmp is not None:
            ins = tmp
            res.append(ins)
        else:
            return res
    elif ins.is_load_ins:
        base_addr = instr.ssa.args
        tmp = get_memo_source()
        if tmp is not None:
            ins = tmp
            res.append(ins)
        else:
            # TODO: it is possible that cannot find the
            # source of a memo in the same function
            # currently skip this situation
            return res
    elif ins.is_call_ins:
        # TODO: interprocedural trace back
        return res
    if ins.ssa.args is not None:
        for arg in ins.ssa.args:
            res += track_prev_all(arg, func)
    return res


def track_prev(instr: VetInstruction):
    '''
    track the previous instruction
    '''
    # if instr.ssa.is_constant:
    #     return []
    instr = convert_instruction(instr)
    ins = [instr]
    if not instr.ssa.is_constant and instr.ssa.args is not None:
        for arg in instr.ssa.args:
            ins += track_prev(arg)
    return ins


def track_prev_with_local(instr: VetInstruction, func):
    '''
    track the previous instruction, including the local variables
    '''
    # 1st step
    pre_ins = track_prev(instr)
    locals = []
    local_ins = []
    new_ins = []
    for p in pre_ins:
        if 'local' in p.name:
            addi(p.get_local_global_name(), locals)
            local_ins.append(p)
    for local in locals:    # for each local
        localssa = local_ssa(local, func.BasicBlockNet)
        # printl(localssa)
        for l in local_ins:  # find the ins using local
            local0 = None
            for s in localssa:
                if l == s.data:  # must be get_local
                    local0 = s.args
                    # print(s)
                    break
            if local0 is None:
                # cannot find the local (should not happen)
                print('error', local)
                continue
            for s in localssa:
                if s.asmt == local0:  # add the get_local to ins
                    addi(s.data, new_ins)
    res = []+pre_ins
    for i in new_ins:
        res += track_prev(i)
    # for i in res:
    #     print(i.ssa.format())
    # TODO: second (multiple) level of locals
    # exit(0)
    return res


def get_prev_source(prev_ins: list) -> VetInstruction:
    '''
    return the source instruction from a sequence of instructions
    '''
    return prev_ins[-1]


def track_prev_one(instr: VetInstruction):
    '''
    find the previous one instruction
    '''
    if instr.is_constant_ins:
        return None
    # if is_call_ins(instr):
    #     return None
    if instr.ssa.args:
        return convert_instruction(instr.ssa.args)
    return None


def track_next(instr: VetInstruction, ins_list: list) -> list:
    '''
    return a list containing all next instructions of an instruction
    '''
    ins = track_next_one(instr, ins_list)
    for i in ins:
        ins += track_next(i, ins_list)
    return ins


def track_next_one(instr: VetInstruction, ins_list: list) -> list:
    '''
    return one next instruction of an instruction
    '''
    ins = []
    for i in ins_list:
        if i.ssa is not None and type(i.ssa.args) == list:
            if instr in i.ssa.args:
                ins.append(i)
    return ins


def track_next_ssa(var: VetInstruction, ssa_list: list) -> list:
    '''
    return a list of SSA format of next instructions of an instruction
    '''
    res = []
    for s in ssa_list:
        if var in s.args:
            res.append(s)
    for s in res:
        res += track_next_ssa(s.asmt, ssa_list)
    return res


def get_locals(memo_instr: list) -> list:
    '''
    return a list containing all local names used in memory instructions
    parameter: a list containing memory instructions
    '''
    locals = []
    for i in memo_instr:
        pre_ins = track_prev(i.ssa.args[-1])  # second para
        for p in pre_ins:
            if 'local' in p.name or 'global' in p.name:
                addi(p.get_local_global_name(), locals)
    return locals


def convert_instruction(instr) -> VetInstruction:
    if type(instr) is not VetInstruction:
        return VetInstruction(instr)
    else:
        return instr


'''
def get_local_dic(localssa: list) -> dict:
    
    # return a dictionary: keys are variables and values are the local names (ssa form)
    # parameter: a list including the ssa form local instructions
    
    local_dic = {}
    for i in localssa:
        i = str(i)
        if i[0] == '%':
            l, r = i.split(' = ')
            local_dic[l] = r
    return local_dic
'''
