from veteos.contract import Contract
from veteos.core import *
import timeout_decorator


@timeout_decorator.timeout(5)
def get_func_wrapper(emul: Contract, funcname: str):
    '''
    a wrapper function for initialize function
    '''
    try:
        func = emul.get_VetFunction(funcname, True)
    except:
        raise TimeoutError("get func timeout: "+funcname)
    return func


@timeout_decorator.timeout(5)
def get_emul_wrapper(file: str):
    '''
    a wrapper function for initialize contract
    '''
    try:
        return Contract(file)
    except:
        raise TimeoutError("init Emul timeout")


def search_func(emul: Contract, fname: tuple, tar: str, parent: list) -> list:
    '''
    recursively search a target function called from a function, return the call sequence
    '''
    np = []
    for p in parent:
        np.append(p)
    np.append(fname)
    f = emul.get_VetFunction(fname[1], False)
    imports = emul.emul.ana.imports_func
    importn = len(imports)
    exfunc = []
    db_ins = []
    for i in f.get_instructions():
        if i.is_call_ins:
            fid = int(i.get_ins_interpretation().split()[1])
            if fid < importn:  # library (import) funcs
                impn = imports[fid][1]
                if tar in impn:
                    addi((i, impn), db_ins)
                    # print(impn)
            else:
                # Done: sometimes function not in import has name
                # exfn = '$func%d' % fid
                exfn = emul.get_func_name(fid)
                # addi(exfn, exfunc)
                # same func name possible in different instr
                exfunc.append((i, exfn))
    # if len(db_ins) == 0 and len(exfunc) == 0:
    #     return []
    res = []
    if len(db_ins) != 0:
        res.append(np+[db_ins])
    for e in exfunc:
        # TODO: possible infinite loops
        visited_flag = 0
        for p in np:
            # TODO: only consider func name
            if p[1] == e[1]:
                visited_flag = 1
        if visited_flag == 1:
            continue    # avoid loop
        res += search_func(emul, e, tar, np)
    return res


def table_name_analysis(emul: Contract, data):
    '''
    analyze the table names from database operation instructions
    '''
    fn = set()
    for path in data:
        for item in path:
            if type(item) == tuple:
                fn.add(item[1])
    funcs = {}
    for f in fn:
        funcs[f] = emul.get_VetFunction(f, True)

    table_dic = {}
    key_read = 'read'
    key_write = 'write'
    key_io = 'io'
    for path in data:
        curr_fn = path[-2][1]
        print('curr:', curr_fn)
        func = funcs[curr_fn]
        # print(func)
        for i, n in path[-1]:
            print('ins:', n)
            # TODO: error occurred when analyzing 'next', temp skip
            if 'db_next' in n:
                continue
            ins = func.get_instructions()[i.offset]
            tn = get_table_name(ins, n, path, funcs, emul)
            if tn not in table_dic.keys():
                table_dic[tn] = {key_write: [], key_read: [], key_io: -1}
            if 'db_store' in n or 'db_update' in n:
                # table_dic[tn][key_write].append((i, n))
                addi((i, n), table_dic[tn][key_write])
            elif 'db_get' in n:
                # table_dic[tn][key_read].append((i, n))
                addi((i, n), table_dic[tn][key_read])
            # TODO: update if any other APIs
    for k in table_dic.keys():
        if len(table_dic[k][key_read]) > 0 and len(table_dic[k][key_write]) > 0:
            table_dic[k][key_io] = 1
        else:
            table_dic[k][key_io] = 0
    # printdic(table_dic)
    return table_dic


@timeout_decorator.timeout(30)
def table_analysis(emul: Contract, actions: list):
    '''
    analyze the tables name relation between different tables
    '''
    log = ''
    table_paths = []
    for a in actions:
        fn = a.name
        print('>> Actions:' + fn + '\n')
        log += '>> Actions:' + fn + '\n'
        table_ins = search_func(emul, (None, fn), 'db_', [])
        res = show_func_flow(table_ins)
        log += res+'\n'
        for i in table_ins:
            existed_flag = 0
            for p in table_paths:
                # if the last func name already exited
                if p[-2][1] == i[-2][1]:
                    existed_flag = 1
                    break
            if existed_flag == 0:
                table_paths.append(i)
    res_dic = table_name_analysis(emul, table_paths)
    return res_dic, log


def get_table_name(instr, ins_name: str, path: list, funcs: dict, emul):
    '''
    get the name of a table from db_find
    '''
    # must contain table name in param
    if 'db_find' in ins_name or \
        'db_store' in ins_name or \
            'db_lowerbound' in ins_name or\
            'db_upperbound' in ins_name:
        if 'db_find' in ins_name or \
            'db_lowerbound' in ins_name or\
                'db_upperbound' in ins_name:
            table_name = instr.ssa.args[1]  # table name is the 3rd/4 param
            # print('db_find')
        elif 'db_store' in ins_name:
            table_name = instr.ssa.args[4]  # table name is the 2nd/6 param
            # print('db_store')
        pre_ins = track_prev(table_name)
        source = pre_ins[-1]
        if source.ssa.is_constant:
            # print('return:', source.operand)
            return source.operand
        # TODO: complex pre-tracking
    else:   # for update, get, remove, etc.
        # print('others')
        # have to find 'db_find' or '*bound'
        iterator = instr.ssa.args[-1]  # iterator is the 1st param
        pre_ins = track_prev_all(iterator, funcs[path[-2][1]])
        for pi in pre_ins:
            # case 1: 'db_find' in same func
            print(pi.ssa.format())
            if pi.is_call_ins:
                fid = int(pi.get_ins_interpretation().split()[1])
                if fid < len(emul.emul.ana.imports_func):
                    impn = emul.emul.ana.imports_func[fid][1]
                    if 'db_find' in impn or \
                        'db_lowerbound' in impn or\
                            'db_upperbound' in impn:
                        return get_table_name(pi, impn, path, funcs, emul)
                else:
                    print(fid)
                    # TODO: how to handle custom func
        # case 2: cross function
        source = pre_ins[-1]
        # if cross func, the source should be a local
        if source.is_get_local_ins:
            para_index = source.get_ins_interpretation().split()[1]
            print('local', para_index)
            curr_index = len(path)-2
            while curr_index >= 1:
                para_index = int(para_index)
                parent_func_name = path[curr_index-1][1]
                parent_call_ins = path[curr_index][0]
                pfunc = funcs[parent_func_name]
                pcins = pfunc.get_instructions()[parent_call_ins.offset]
                # print(pcins.ssa.format())
                # print(pcins.ssa.args)
                para_index = len(pcins.ssa.args)-1-para_index
                print(pfunc.name)
                print(len(pcins.ssa.args))
                print(para_index)
                para_ins = pcins.ssa.args[para_index]
                pre_para_ins = track_prev_all(para_ins, pfunc)
                for pi in pre_para_ins:
                    # case 1: 'db_find' in same func
                    if pi.is_call_ins:
                        fid = int(pi.get_ins_interpretation().split()[1])
                        # TODO: currently skip all custom functions
                        if fid < len(emul.emul.ana.imports_func):
                            impn = emul.emul.ana.imports_func[fid][1]
                            if 'db_find' in impn or \
                                'db_lowerbound' in impn or\
                                    'db_upperbound' in impn:
                                return get_table_name(pi, impn, path, funcs, emul)
                # case 2: cross function: stay in loop
                # TODO: is source must last one?
                para_source = pre_para_ins[-1]
                if para_source.is_get_local_ins:
                    para_index = para_source.get_ins_interpretation().split()[
                        1]
                curr_index -= 1
            return


def show_func_flow(data: list):
    '''
    only for visulization, print the function call sequence
    '''
    res = ''
    for path in data:
        fp = '->'.join([t[1] for t in path[:-1]])+':'
        ins = []
        for i, inm in path[-1]:
            ins.append(
                ': '.join([str(i.offset), i.get_ins_interpretation(), inm]))
        res += '\n'.join([fp]+ins)
        res += '\n'
    print(res)
    return res
