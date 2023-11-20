from veteos.octopus.arch.wasm.emulator import WasmSSAEmulatorEngine
from veteos.function import VetFunction
from veteos.utils import *
from veteos.core import *
from veteos.misc import *


class Contract:
    '''
    for contract initialization
    '''

    def __init__(self, filename: str) -> None:
        def init_emul(filename: str) -> WasmSSAEmulatorEngine:
            '''
            initialize the emulator
            '''
            fp = open(filename, 'rb')
            octo_bytecode = fp.read()
            emul = WasmSSAEmulatorEngine(octo_bytecode)
            fp.close()
            return emul

        self.filename = filename
        self.emul = init_emul(filename)
        self.funcs = {}
        self.vetfuncs = {}
        self.actions = []
        self.edges_from = {}
        self.edges_to = {}

    def analyze(self, func_name: list):
        '''
        analyze functions
        '''
        if len(func_name) > 0:
            self.emul.emulate_functions(func_name)
        # try to emulate main by default
        else:
            self.emul.emulate_functions()

    def show_cfg(self, func_name: list):
        '''
        generate CFGs
        '''
        from veteos.octopus.analysis.graph import CFGGraph
        filename = os.path.join(
            OUTPUT_PATH, self.filename.split(os.path.sep)[-1]+'.cfg.gv')
        ssa_cfg = CFGGraph(self.emul.cfg, filename=filename)
        if func_name != None and len(func_name) > 0:
            for fname in func_name:
                if fname in self.vetfuncs.keys():
                    self.vetfuncs[fname].writeback_instructions()
            ssa_cfg.view_functions(only_func_name=func_name,
                                   simplify=False,
                                   ssa=True)
        else:
            ssa_cfg.view(simplify=False, ssa=True)

    def show_call_graph(self):
        '''
        generate call graph
        '''
        from veteos.octopus.arch.wasm.cfg import WasmCFG
        fp = open(self.filename, 'rb')
        octo_bytecode = fp.read()
        octo_cfg = WasmCFG(octo_bytecode)
        fp.close()
        octo_cfg.visualize_call_flow()
        return

    def init_edges(self):
        '''
        initialize the edges
        '''
        if len(self.edges_from) > 0:
            return
        nodes, edges = self.emul.cfg.get_functions_call_edges()
        for e in edges:
            fr = e.node_from
            to = e.node_to
            if fr not in self.edges_from.keys():
                self.edges_from[fr] = []
            if to not in self.edges_to.keys():
                self.edges_to[to] = []
            self.edges_from[fr].append(to)
            self.edges_to[to].append(fr)

    def get_call_edges_from(self, func_name: str, full: bool = False) -> list:
        '''
        get the edges started from a function
        '''
        '''
        return all the callee functions of a funtion
        - return a list of str
        - no duplicated names when full == False
        '''
        if len(self.edges_from) == 0:
            self.init_edges()
        if func_name in self.edges_from.keys():
            edges = self.edges_from[func_name]
            if not full:
                return list(set(edges))
            else:
                return edges
        return None

    def get_call_edges_to(self, func_name: str, full: bool = False) -> list:
        '''
        get the edges connected to a function, return None if N/A

        return all the caller functions of a funtion
        - return a list of str
        - no duplicated names when full == False
        '''
        if len(self.edges_to) == 0:
            self.init_edges()
        if func_name in self.edges_to.keys():
            edges = self.edges_to[func_name]
            if not full:
                return list(set(edges))
            else:
                return edges
        return None

    def get_edges(self, func_name: list) -> list:
        '''
        return the edges in specific functions
        func_name: a list of function names
        '''
        functions = self.emul.cfg.functions
        edges = self.emul.cfg.edges     # all edges in graph

        if len(func_name) > 0:
            functions = [
                func for func in self.emul.cfg.functions if func.name in func_name]
            functions_block = [func.basicblocks for func in functions]
            block_name = [
                b.name for block_l in functions_block for b in block_l]
            edges = [edge for edge in edges if (
                edge.node_from in block_name or edge.node_to in block_name)]
        return edges

    def get_import_len(self) -> int:
        '''
        return the number of import functions
        '''
        return len(self.emul.ana.imports_func)

    def get_VetFunction(self, name: str, ssa: bool = True) -> VetFunction:
        '''
        return a VetFunction object, return None if not found the name
        '''
        def get_function(name: str):
            '''
            reutrn a octopus.function object, return None if not found
            '''
            # return self.emul.cfg.get_function(name)
            for f in self.emul.cfg.functions:
                if f.name == name:
                    return f
            return None

        func_dic = self.vetfuncs if ssa else self.funcs
        if name not in func_dic.keys():
            if ssa:
                self.analyze([name])
            func = get_function(name)
            if func == None:
                print('function name not found:', name)
                return None
            func_dic[name] = VetFunction(func, self, ssa)
        return func_dic[name]

    def get_func_name(self, index: int) -> str:
        '''
        retrun the function name using the index
        '''
        try:
            return self.emul.ana.func_prototypes[int(index)][0]
        except:
            return None

    def check_func_name(self, name: str):
        '''
        check whther the function is in the contract
        '''
        for f in self.emul.ana.func_prototypes:
            if name in f[0]:
                return f[0]
        return None

    def get_func_prototype(self, name: str):
        '''
        retrun the function prototype using the name
        '''
        for p in self.emul.ana.func_prototypes:
            if p[0] == name:
                return p
        return None

    def get_all_function_names(self) -> list:
        '''
        return a list containing all function names
        '''
        return [f.name for f in self.emul.cfg.functions]

    def get_actions(self) -> list:
        '''
        return a list containing the action names of a contract
        '''
        if self.actions != None and len(self.actions) == 0:
            self.init_edges()
            self.actions = self.get_call_edges_to('read_action_data')
        return self.actions if self.actions != None else []

    def get_action_strings_from_apply(self) -> list:
        '''
        search for the strings in apply, return the action names
        '''
        apply = self.get_VetFunction('apply', False)
        res = []
        if apply is None:
            return res
        instrs = apply.get_instructions()
        for i, ins in enumerate(instrs):
            if ins.is_cmp_ins and i > 1:
                idx = -1
                if 'i64.const' in instrs[i-1].name and 'local 2' in instrs[i-2].get_ins_interpretation():
                    idx = i-1
                elif 'i64.const' in instrs[i-2].name and 'local 2' in instrs[i-1].get_ins_interpretation():
                    idx = i-2
                if idx != -1:
                    name = instrs[idx].get_ins_interpretation().split()[-1]
                    res.append([idx, name, eosio_name_decoder(int(name))])
        return res

    def get_strings_from_function(self, name: str) -> list:
        '''
        search for all strings in a function
        '''
        func = self.get_VetFunction(name, False)
        res = []
        for ins in func.get_instructions():
            if 'i64.const' in ins.name:
                s = eosio_name_decoder(
                    int(ins.get_ins_interpretation().split()[-1]))
                if len(s) > 0:
                    res.append(s)
        return res

    def get_return_values(self) -> list:
        '''
        return the list of return values
        '''
        return self.emul.return_values

    def get_func_call_tree(self):
        '''
        generate the function call tree started from `apply`
        '''
        def find_calls(fn: str) -> list:
            return self.get_call_edges_from(fn)

        def find(node: str, visited: list) -> list:
            next_calls = find_calls(node)
            if next_calls == None:
                return
            node_dic = {}
            for nc in next_calls:
                if nc not in visited:
                    node_dic[nc] = find(nc, visited+[nc])
            return node_dic

        res = {}
        apply = 'apply'
        res[apply] = find(apply, [apply])
        acn = self.get_actions()
        app = []
        if res[apply] != None and len(res[apply]) > 0:
            app = list(res[apply].keys())
        for ac in acn:
            if ac in app:
                continue
            res[ac] = find(ac, [ac])
        return res

    def external_check(self, func: VetFunction):
        '''
        check the dataflow in external functions
        '''
        def ex_fun(func: VetFunction) -> list:
            '''
            find all external function call, return the names
            '''
            # the number of import funcs
            # importn = len(self.emul.ana.imports_func)
            importn = self.get_import_len()
            res = []
            ins = func.vet_instructions
            for _, i in enumerate(ins):
                if i.is_call_ins:
                    if int(i.get_ins_interpretation().split()[1]) < importn:
                        continue    # ignore library (import) funcs
                    if _+1 < len(ins) and ins[_+1].is_drop_ins:
                        continue    # ignore if drop the return value
                    if i.ssa.args is None or i.ssa.new_assignement is None:
                        continue    # ignore if no parameter or return value
                    res.append(i)
            return res

        def para_taint(func: VetFunction) -> bool:
            '''
            check whether the parameters of a function is tainted
            '''
            # Step 1: detect the number of parameters
            paras = func.get_param()
            n = len(paras)  # number of paras
            # Step 2: select all instructions containing parameters
            locals = ['local %d' % i for i in range(n)]
            new_ins = []
            for i in func.get_instructions():
                for l in locals:
                    if i.ssa is not None and l in i.ssa.format() and i.is_get_local_ins:
                        new_ins.append(i)
            related_ins = new_ins
            while len(new_ins) > 0:
                # Step 3: execute taint analysis upon para-related instructions
                for i in new_ins:
                    tmp_ins = track_next(i, func.get_instructions())
                    for t in tmp_ins:
                        addi(t, related_ins)
                new_ins = []
                new_var = []
                for i in related_ins:
                    if i.is_set_tee_ins:
                        istr = i.get_ins_interpretation()
                        tmp_var = istr[istr.index('_')+1:]
                        if tmp_var not in locals and tmp_var not in new_var:
                            new_var.append((tmp_var, i))
                            locals.append(tmp_var)
                for v in new_var:
                    var, ins = v
                    var_ssa = local_ssa(var, func.BasicBlockNet)
                    ssa_ins = track_next_ssa('%{:02X}'.format(
                        ins.ssa.args[0].ssa.new_assignement), var_ssa)
                    for i in ssa_ins:
                        if i.data not in related_ins:
                            new_ins.append(i.data)
                            related_ins.append(i.data)
            for i in func.return_values:
                if i in related_ins:
                    return True
            return False

        print('external check start:')
        exfunc = ex_fun(func)   # get the external functions
        # fns = ['$func%s' % f.get_ins_interpretation().split()[1] for f in exfunc]
        fns = [self.get_func_name(
            f.get_ins_interpretation().split()[1]) for f in exfunc]
        print('Exfunc: ', fns)
        for f in exfunc:
            # fn = '$func%s' % f.get_ins_interpretation().split()[1]
            fn = self.get_func_name(f.get_ins_interpretation().split()[1])
            print('>>'+fn)
            # res = para_taint(Func(func.emul, fn))
            res = para_taint(self.get_VetFunction(fn))
            print(res)
            f.set_dataflow(str(res))
        print('external check end.')

    def dataflow_analysis(self, funcname: str):
        '''
        analyze the dataflow in a function
        '''
        func = self.get_VetFunction(funcname, True)
        self.external_check(func)
        memo_instr = func.get_memo_instr()   # find memory instructions
        locals = get_locals(memo_instr)     # find memory-related locals
        param = func.get_param()
        param_locals = ['local %d' % i for i in range(len(param))]
        print(param)
        print(param_locals+locals)
        locals = param_locals+locals
        # handle list of locals
        localssa = []
        for local in locals:
            print('>>>local: ', local)
            localssa += local_ssa(local, func.BasicBlockNet)
        printl(localssa)
        # return
        # convert locals to specific variable names (tanslate load and store)
        memo_tmp = get_memory_ssa(memo_instr, locals, func)
        printl(memo_tmp)
        memo_slot = []
        for i in memo_tmp:
            i = str(i)
            if i[0] != '%':
                addi(i.split(' = ')[0], memo_slot)
        # print(memo_slot)
        print('>>>memory SSA')
        memo_ssa = []
        for m in memo_slot:
            memo_l = memory_ssa(m, func.BasicBlockNet,
                                func.instr2block, memo_tmp)
            printl(memo_l)
            memo_ssa += memo_l
        for i in localssa+memo_ssa:
            i.data.set_dataflow(str(i))
            # print(i.data)
        self.show_cfg([funcname])
        return

    def find_db_from_tree(self, target: str, full: bool = False) -> list:
        '''
        find a datebase operation function from the function call tree
        '''
        def dfs(node: dict, visited: list) -> list:
            res = []
            if type(node) != dict:
                return []
            for k in node.keys():
                if is_db_find(k):
                    visited += [k]
                elif target in k or (target == 'db_store' and is_db_store(k)):
                    return [visited+[k]]
                else:
                    res += dfs(node[k], visited+[k])
            return res

        def bfs_full(node: dict, visited: list, res: list):
            if type(node) != dict:
                return
            tmp = []
            for k in node.keys():
                if is_db_find(k):
                    visited += [k]
                elif target in k or (target == 'db_store' and is_db_store(k)):
                    res += [visited+[k]]
                else:
                    tmp.append(k)
            for k in tmp:
                bfs_full(node[k], visited+[k], res)
            return

        res = []
        tree = self.get_func_call_tree()
        if full:
            bfs_full(tree, [], res)
        else:
            res = dfs(tree, [])
        return res

    def find_func_from_tree(self, target: str, passes: str = None, full: bool = False, cmp=lambda t, k: t in k) -> list:
        '''
        finding a function from the function call tree
        '''
        def dfs(node: dict, visited: list) -> list:
            res = []
            if type(node) != dict:
                return []
            for k in node.keys():
                if passes != None and passes in k:
                    visited += [k]
                elif cmp(target, k):
                    return [visited+[k]]
                else:
                    res += dfs(node[k], visited+[k])
            return res

        def bfs_full(node: dict, visited: list, res: list):
            if type(node) != dict:
                return
            tmp = []
            for k in node.keys():
                if passes != None and passes in k:
                    visited += [k]
                elif cmp(target, k):
                    res += [visited+[k]]
                else:
                    tmp.append(k)
            for k in tmp:
                bfs_full(node[k], visited+[k], res)
            return

        res = []
        tree = self.get_func_call_tree()
        if full:
            bfs_full(tree, [], res)
        else:
            res = dfs(tree, [])
        return res
