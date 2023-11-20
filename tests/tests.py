import sys
import os
import subprocess

dataset_path = os.path.join('samples', 'opensource')
dataset_file = dataset_path+'.tar.gz'


def find_db_source(emul):
    def dfs(fn: str):
        res = []
        pref = emul.get_call_edges_to(fn)
        # print(fn,' pref ',pref)
        if pref == None or len(pref) == 0:
            return [fn]
        for pf in pref:
            res += dfs(pf)
        return res
    dbs = []  # all db_store APIs
    emul.init_edges()
    for k in emul.edges_to.keys():
        if is_db_store(k):
            dbs.append(k)
    # print('dbs',dbs)
    res = []
    for db in dbs:
        res += dfs(db)
    return list(set(res))


def find_inline_source(emul):
    def dfs(fn: str, visited: list):
        res = []
        pref = emul.get_call_edges_to(fn)
        # print(fn,' pref ',pref)
        if pref == None or len(pref) == 0 or fn in visited:
            return [visited+[fn]]
        for pf in pref:
            res += dfs(pf, visited+[fn])
        return res
    emul.init_edges()
    res = dfs('send_inline', [])
    return res


def find_func_source(emul, target: str):
    def dfs(fn: str, visited: list):
        res = []
        pref = emul.get_call_edges_to(fn)
        # print(fn,' pref ',pref)
        if pref == None or len(pref) == 0 or fn in visited:
            return [visited+[fn]]
        for pf in pref:
            res += dfs(pf, visited+[fn])
        return res
    emul.init_edges()
    res = dfs(target, [])
    return res


def get_test_file_list():
    if not os.path.exists(dataset_path):
        # Extract the file
        tar_command = 'tar -xzf %s -C "samples"' % dataset_file
        try:
            subprocess.run(tar_command, shell=True, check=True)
            print(f"Extracted {dataset_file} to {dataset_path}")
        except subprocess.CalledProcessError as e:
            print(f"Error executing the command: {e}")
            print(
                f"Please manually extract the file {dataset_file} to {dataset_path}")
            exit(1)
    files = os.listdir(dataset_path)
    res = []
    for f in files:
        if f.endswith('.wasm'):
            res.append(os.path.join(dataset_path, f))
    return res


def find_entry(emul):
    inlines = []  # search all strings in inline actions
    # inlinep=find_func_from_tree_new(emul,'send_inline')
    inlinep = find_inline_source(emul)
    for inp in inlinep:
        for i in inp[1:]:
            strs = emul.get_strings_from_function(i)
            if 'active' in strs:
                inlines += strs
                break
    # print(inlines)

    actions = emul.get_action_strings_from_apply()
    # print(actions)
    tmp = []
    # filter the actions
    for ac in actions:
        if ac[2] != 'onerror':
            tmp.append(ac)
    actions = tmp
    # print(actions)
    names = []

    paths = emul.find_db_from_tree('db_store')
    # print(paths)
    if len(paths) == 0:
        roots = find_db_source(emul)
        # print(roots)
        for idx, rt in enumerate(roots):
            if idx > len(actions)-1:
                break
            names.append(actions[idx]+[-2, rt])
    else:
        direct = []
        indirect = []
        for p in paths:
            if 'apply' in p[0]:
                if len(p) > 1 and p[1] not in direct:
                    direct.append(p[1])
            else:
                indirect.append(p[0])
        indirect = list(set(indirect))

        apply = emul.get_VetFunction('apply', False)
        for di in direct:
            idx = -1
            # find the correct call instr
            for i, ins in enumerate(apply.get_instructions()):
                if ins.is_call_ins and di in emul.get_func_name(ins.get_ins_interpretation().split()[-1]):
                    idx = i
                    break
            for i, ac in enumerate(actions):
                if idx > ac[0]:
                    if i == len(actions)-1:  # ac is the last one
                        names.append(ac+[idx, di])
                    elif idx < actions[i+1][0]:
                        names.append(ac+[idx, di])
        for idx, ind in enumerate(indirect):
            if idx > len(actions)-1:
                break
            names.append(actions[idx]+[-1, ind])

    names = sorted(names)
    for idx in range(len(names)-1, -1, -1):
        na = names[idx]
        if na[2] in inlines:
            names.remove(na)  # deleted all actions called by inline
        elif emul.get_call_edges_to(na[4]) != None and len(emul.get_call_edges_to(na[4])) > 1:
            # deleted all actions called by other func except apply
            names.remove(na)
    printl(names)
    return names


def find_entry_test():
    logfile = get_test_file_list()
    cnte = 0
    i = 0
    for file in logfile:
        i += 1
        print('Analyzing: '+file)
        try:
            emul = get_emul_wrapper(file)
            find_entry(emul)
        except:
            cnte += 1
            continue
    print('>>>results:')
    print('samples:' + str(i))
    print('error:' + str(cnte))
    return


def dataflow_fp():
    def get_fp(emul):
        actions = emul.get_actions()
        res = []
        # print(actions)
        for ac in actions:
            func = emul.get_VetFunction(ac, False)
            instr = func.get_instructions()
            flag = 0
            read_data_flag = False
            for idx, ins in enumerate(instr):
                if ins.is_call_ins:
                    name = emul.get_func_name(
                        ins.get_ins_interpretation().split()[-1])
                    # print(ins.get_ins_interpretation(),name)
                    if not read_data_flag and 'read_action_data' in name:
                        read_data_flag = True
                    elif read_data_flag and 'memcpy' in name:
                        # print('memcpy')
                        for id in range(idx, -1, -1):
                            tmp = instr[id]
                            if tmp.is_constant_ins:
                                # print(tmp.get_ins_interpretation())
                                length = tmp.get_ins_interpretation(
                                ).split()[-1]
                                res.append(length)
                                flag = 1
                                break
                if flag == 1:
                    break
            if flag == 0:
                res.append('0')
        cnt = 0
        for pl in res:
            if int(pl) % 4 == 0:
                continue
            else:
                cnt += 1
        return res, cnt

    file = get_test_file_list()
    cnte = 0
    sum_case = 0
    sum_fp = 0
    i = 0
    # cnt = 0
    for fn in file:
        i += 1
        print('{0: <2}: '.format(i), end='')
        # print(fn)
        try:
            emul = get_emul_wrapper(fn)
            res, num = get_fp(emul)
            resl = len(res)
            sum_fp += num
            sum_case += resl
            print('::'.join([fn, str(res), str(resl), str(
                num), str(num/resl if resl != 0 else 0)]))
        except:
            cnte += 1
            continue
    msg = 'test cases:' + str(sum_case) + '\nerror:' + str(cnte)
    print(msg)
    return msg


def dataflow_fn():
    def get_fn(emul):
        actions = emul.get_actions()
        res = []
        # print(actions)
        for ac in actions:
            func = emul.get_VetFunction(ac, False)
            instr = func.get_instructions()
            flag = 0
            read_data_flag = False
            para_addr = None
            for idx, ins in enumerate(instr):
                if ins.is_call_ins:
                    name = emul.get_func_name(
                        ins.get_ins_interpretation().split()[-1])
                    # print(get_ins_interpretation(ins),name)
                    if not read_data_flag and 'read_action_data' in name:
                        read_data_flag = True
                    elif read_data_flag and 'memcpy' in name:
                        # print('memcpy')
                        local_src_flag = False
                        cnst1 = False
                        offset = '0'
                        for id in range(idx, -1, -1):
                            tmp = instr[id]
                            if tmp.is_constant_ins:
                                if not cnst1:
                                    cnst1 = True
                                else:
                                    offset = tmp.get_ins_interpretation(
                                    ).split()[-1]
                                # print(tmp.get_ins_interpretation())
                                # length=tmp.get_ins_interpretation().split()[-1]
                                # res.append(length)
                                # flag=1
                                # break
                            elif 'local' in tmp.name:
                                if not local_src_flag:
                                    local_src_flag = True
                                else:
                                    local_id = tmp.get_ins_interpretation(
                                    ).split()[-1]
                                    para_addr = [local_id, offset]
                                    print('>'.join([ac]+para_addr))
                                    break
                elif 'load' in ins.name and para_addr != None:
                    offset = '0'
                    ins_split = ins.get_ins_interpretation().split('offset=')
                    if len(ins_split) > 1:
                        offset = ins_split[1]
                    for id in range(idx, -1, -1):
                        tmp = instr[id]
                        if 'local' in tmp.name:
                            local_id = tmp.get_ins_interpretation().split()[-1]
                            if local_id == para_addr[0] and offset == para_addr[1]:
                                flag = 1
                                break
                if flag == 1:
                    break
            res.append(1 if flag == 1 else 0)

        return res, sum(res)

    file = get_test_file_list()
    cnte = 0
    sum_case = 0
    sum_fp = 0
    i = 0
    # cnt = 0
    for fn in file:
        i += 1
        print('{0: <4}: '.format(i), end='')
        # print(fn)
        try:
            emul = get_emul_wrapper(fn)
            res, num = get_fn(emul)
            resl = len(res)
            sum_fp += num
            sum_case += resl
            print('::'.join([fn, str(res), str(resl), str(
                num), str(num/resl if resl != 0 else 0)]))
        except:
            cnte += 1
            continue
    msg = 'test cases:' + str(sum_case) + '\nerror:' + str(cnte)
    print(msg)
    return msg


def main():
    entrypoint = 'entrypoint'
    dataflow = 'dataflow'
    if len(sys.argv) != 2:
        print("Usage: python tests.py [%s|%s]" % (entrypoint, dataflow))
        sys.exit(1)

    argument = sys.argv[1]

    if argument == entrypoint:
        find_entry_test()
    elif argument == dataflow:
        dtfp = dataflow_fp()
        dtfn = dataflow_fn()
        print('\n>>>results:')
        print('dataflow false positive test:')
        print(dtfp)
        print('dataflow false negative test:')
        print(dtfn)
    else:
        print("Invalid argument. Use %s or %s." % (entrypoint, dataflow))


if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
    sys.path.append(parent_dir)
    from veteos.analyzer import *
    from veteos.analyses import *
    main()
