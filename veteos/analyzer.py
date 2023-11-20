from veteos.instruction import VetInstruction
from veteos.function import VetFunction
from veteos.contract import Contract
from veteos.core import *
from veteos.misc import *


class Analyzer:
    '''
    main analyzer class
    '''

    def __init__(self, ssa: bool = False) -> None:
        self.ssa = ssa  # enable SSA mode

    def ins2str(self, ins: VetInstruction, target: str = None):
        '''
        convert the instruction to string
        '''
        def add_note(itp: str):
            res = ''
            if '6138663591592764928' in itp:
                res += ' ("eosio.token")'
            elif '-3617168760277827584' in itp:
                res += ' ("transfer")'
            elif '3617214756542218240' in itp:
                res += ' ("active")'
            elif target != None and target == 'apply' and 'local 1' in itp:
                res += ' (code)'
            elif target != None and target == 'apply' and 'local 2' in itp:
                res += ' (action)'
            elif target != None and 'call' in itp:
                res += ' (%s)' % target
            elif 'i64.const' in itp:
                res += ' ("%s")' % eosio_name_decoder(int(itp.split()[-1]))
            # convert to html
            return res.replace('(', '<').replace(')', '>')

        itp = ins.ssa.format() if ins.ssa != None else ins.get_ins_interpretation()
        itp += add_note(ins.get_ins_interpretation())
        return str(ins.offset)+': '+itp

    def find_call_ins(self, emul: Contract, funcname: str, target: str, full: bool = False, index_only: bool = False, reverse: bool = False, start_index: int = 0):
        '''
        find the instruction which calling the function indicated by the function name
        '''
        func = emul.get_VetFunction(funcname, self.ssa)
        if func == None:
            print('function not found:', funcname)
        instrs = func.get_instructions()
        res = []
        for idx in (range(start_index, -1, -1) if reverse else range(start_index, len(instrs))):
            ins = instrs[idx]
            if 'call' in ins.name:
                fid = ins.get_ins_interpretation().split()[-1]
                tarname = emul.get_func_name(int(fid))
                if target in tarname or (target == 'db_find' and is_db_find(tarname)) or (target == 'db_store' and is_db_store(tarname)):
                    if index_only:
                        return idx
                    tmp = [
                        funcname+':'+self.ins2str(i, tarname) for i in instrs[max(idx-4, 0):idx+1]]
                    if full:
                        res.append(tmp)
                    else:
                        return tmp
        return res if len(res) > 0 else None

    def pay2play(self, emul: Contract):
        '''
        detect the pay to play patterns (listening "transfer" notification in "apply")
        '''
        funcname = 'apply'
        app = emul.get_VetFunction(funcname, self.ssa)
        if app == None:
            return False
        eosio_token = False
        transfer = False
        res = {'eosio.token': None,
               'transfer': None}
        instrs = app.get_instructions()
        for idx, ins in enumerate(instrs):
            if 'i64.const' in ins.name and (instrs[idx+1].is_cmp_ins or instrs[idx+2].is_cmp_ins):
                if not eosio_token and ins.operand == EOSIO_TOKEN:
                    eosio_token = True
                    left, right = idx, min(idx+4, len(instrs))
                    if instrs[idx+1].is_cmp_ins:
                        left, right = max(left-1, 0), right-1
                    res['eosio.token'] = [
                        funcname+':' + self.ins2str(i, funcname) for i in instrs[left:right]]
                if not transfer and ins.operand == TRANSFER:
                    transfer = True
                    left, right = idx, min(idx+4, len(instrs))
                    if instrs[idx+1].is_cmp_ins:
                        left, right = max(left-1, 0), right-1
                    res['transfer'] = [
                        funcname+':'+self.ins2str(i, funcname) for i in instrs[left:right]]
                if eosio_token and transfer:
                    return res
        return None

    def notify(self, emul: Contract):
        '''
        detect the notify functions
        '''
        def inline_eos_trans(emul: Contract):
            '''
            similar to find_action_chain() in txn_ana()
            '''
            def find_strings(func: VetFunction) -> dict:
                funcname = func.name
                eosio_token = False
                transfer = False
                active = False
                res = {'eosio.token': None,
                       'transfer': None,
                       'active': None}
                instrs = func.get_instructions()
                for idx, ins in enumerate(instrs):
                    if 'i64.const' in ins.name and idx+1 < len(instrs) and 'i64.store' in instrs[idx+1].name:
                        if ins.operand == b'\x00':
                            continue
                        if not eosio_token and ins.operand == EOSIO_TOKEN:
                            eosio_token = True
                            res['eosio.token'] = [
                                funcname+':'+self.ins2str(i, target) for i in instrs[idx:idx+2]]
                        if not transfer and ins.operand == TRANSFER:
                            transfer = True
                            res['transfer'] = [
                                funcname+':'+self.ins2str(i, target) for i in instrs[idx:idx+2]]
                        if not active and ins.operand == ACTIVE:
                            active = True
                            res['active'] = [
                                funcname+':'+self.ins2str(i, target) for i in instrs[idx:idx+2]]
                        if eosio_token and transfer and active:
                            return res
                return None

            target = 'send_inline'
            actions = emul.find_func_from_tree(target)
            for ac in actions:
                idx = len(ac)-2
                while idx >= 0:
                    func_name = ac[idx]
                    func = emul.get_VetFunction(func_name, self.ssa)
                    res = find_strings(func)
                    if res != None:
                        res['inline'] = self.find_call_ins(
                            emul, ac[-2], target)[-4:]
                        return res
                    idx -= 1
            return None

        receipt = 'require_recipient'
        res = {receipt: []}
        reci = emul.get_call_edges_to(receipt)
        if reci != None:
            rc = reci[-1]
            rc_ins = self.find_call_ins(emul, rc, receipt)[-2:]
            res[receipt] = rc_ins
        inline = inline_eos_trans(emul)
        res['eosio.token::transfer'] = inline
        if reci != None or inline != None:
            return res
        else:
            return None

    def stateIO(self, emul: Contract, read: bool = True, full=True):
        '''
        detect the write and read of global states
        '''
        def find_db_find(flist: list) -> int:
            for i in range(len(flist)-1, -1, -1):
                if is_db_find(flist[i]):
                    return i
            return -1

        def find_caller_callee(flist: list, idx: int):
            caller, callee = -1, -1
            for i in range(idx-1, -1, -1):
                if is_db_find(flist[i]):
                    continue
                else:
                    caller = i
                    break
            for i in range(idx+1, len(flist)):
                if is_db_find(flist[i]):
                    continue
                else:
                    callee = i
                    break
            return caller, callee

        def find_caller(flist: list, idx: int):
            caller = -1
            for i in range(idx-1, -1, -1):
                if 'db_' in flist[i]:
                    continue
                else:
                    caller = i
                    break
            return caller

        dbfind = 'db_find'
        dbget = 'db_get' if read else 'db_store'
        dbr = emul.find_db_from_tree(dbget, full=True)
        # return dbr if len(dbr)>0 else None
        res = []
        if len(dbr) > 0:
            for ac in dbr:
                tmp = {dbfind: None,
                       dbget: None}
                idx = find_db_find(ac)
                if idx < 1:  # 'db_find' not found in the same chain
                    dbfs = emul.find_func_from_tree(
                        dbfind, cmp=lambda _, k: 'db_' in k and 'find_i' in k)
                    if len(dbfs) > 0:
                        dbf = dbfs[0]  # select the first chain
                        tmp[dbfind] = self.find_call_ins(
                            emul, dbf[-2], 'find_i')
                    if len(dbfs) == 0:  # 'db_find' not found, to find other finding APIs
                        dbfs = emul.find_func_from_tree(
                            dbfind, cmp=lambda _, k: is_db_find(k))
                        if len(dbfs) == 0:
                            continue
                        dbf = dbfs[0]  # select the first chain
                        tmp[dbfind] = self.find_call_ins(
                            emul, dbf[-2], dbfind)
                else:
                    caller, callee = find_caller_callee(ac, idx)
                    caller, callee = ac[caller], ac[callee]
                    idx_cget = self.find_call_ins(
                        emul, caller, callee, index_only=True)
                    tmp[dbfind] = self.find_call_ins(
                        emul, caller, dbfind, reverse=True, start_index=idx_cget)
                    if tmp[dbfind] == None:
                        tmp[dbfind] = self.find_call_ins(
                            emul, caller, dbfind)
                    # tmp[dbfind]=Component.find_call_ins(emul,caller,dbfind,full=True)
                tmp[dbget] = self.find_call_ins(
                    emul, ac[find_caller(ac, len(ac)-1)], dbget)[-1]
                if not full and tmp[dbget] != None:
                    return tmp
                res.append(tmp)
        return res if len(res) > 0 else None

    def checkCondition(self, emul: Contract):
        '''
        detect the condition check of user input and secret
        '''
        def is_get_parameter(ins: VetInstruction, paran: int) -> bool:
            if ins.is_get_local_ins:
                para_index = ins.get_ins_interpretation().split()[1]
                if int(para_index) < paran:
                    return True
            return False

        def get_stack_size(instrs: list):
            for idx, ins in enumerate(instrs):
                if ins.is_get_global_ins and idx+2 < len(instrs):
                    if 'i32.const' in instrs[idx+1].name and 'i32.sub' in instrs[idx+2].name:
                        res = instrs[idx+1].get_ins_interpretation().split()[1]
                        return int(res)

        def is_load_parameter(ins: VetInstruction, stack_size: int, param_size: int) -> bool:
            if ins.is_load_ins and stack_size != None:
                offset = ins.get_ins_interpretation().split()[-1]
                offset = int(offset, 16) if offset.startswith(
                    '0x') else int(offset)
                if offset >= stack_size-param_size:
                    return True
            return False

        acs = emul.get_actions()
        for ac in acs:
            func = emul.get_VetFunction(ac, self.ssa)
            fn = func.prefered_name
            param = fn[fn.index('(')+1:fn.index(')')].split()
            paran = len(param)
            if paran < 1:
                continue
            param_size = 0
            for pa in param:
                if '32' in pa:
                    param_size += 4
                elif '64' in pa:
                    param_size += 8
            instrs = func.get_instructions()
            stack_size = get_stack_size(instrs)
            for idx, ins in enumerate(instrs):
                if is_get_parameter(ins, paran) or is_load_parameter(ins, stack_size, param_size):
                    if idx+1 < len(instrs) and instrs[idx+1].is_cmp_ins:
                        end = idx+1
                    elif idx+2 < len(instrs) and instrs[idx+2].is_cmp_ins:
                        end = idx+2
                    else:
                        continue
                    res = []
                    for idxx, inss in enumerate(instrs[end-2:end+2]):
                        tmps = ''
                        if inss == instrs[idx]:
                            tmps = ' <user input>'
                        elif idxx < 2:
                            tmps = ' <global state>'
                        res.append(ac + ':' + self.ins2str(inss) + tmps)
                    return res
        return None

    def createSecret(self, emul: Contract, full=False):
        '''
        detect the secret creation process, similar to rem_ana()
        '''
        def write_rem(emul: Contract, funcname: str, full: bool = False):
            func = emul.get_VetFunction(funcname, self.ssa)
            if func == None:
                return False
            res = []
            tmp = []
            # tmp_idx=0
            for i in func.get_instructions():
                if '.rem_' in i.name:
                    tmp = [funcname+':'+self.ins2str(i)]
                    # tmp_idx=0
                elif len(tmp) == 1 and (i.is_set_tee_ins or i.is_store_ins):
                    # if tmp_idx>3: # threshold
                    #     continue
                    tmp.append(funcname+':'+self.ins2str(i))
                    if not full:
                        return tmp
                    res.append(tmp)
                    tmp = []
                # tmp_idx+=1
            return res if len(res) > 0 else None

        acns = emul.get_all_function_names()    # all funcs
        for acn in acns:
            res = write_rem(emul, acn, full)
            if res != None:
                return res
        return None
