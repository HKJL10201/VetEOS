from veteos.instruction import VetInstruction
from veteos.function import VetFunction
from veteos.contract import Contract
from veteos.core import *
from veteos.misc import *
import pprint


class Terminal():
    '''
    VetEOS Terminal
    '''

    def __init__(self) -> None:
        # \u2500: box drawings light horizontal
        # \u2501: box drawings heavy horizontal
        # \u2015: horizontal bar
        self.hline = '\u2500'
        self.middot = '\u00b7'
        self.ins_max = 30

    def set_color(self, string: str, color: str = None, bold: bool = False, underline: bool = False) -> str:
        '''
        return a colored string\n
        parameters:
        - string: the string need to colored
        - color: possible value: 'r'/'red', 'g'/'green', 'y'/'yellow', 'b'/'blue', 
                                'p'/'purple', 'c'/'cyan', 'dc'/'darkcyan'
        - bold: bolden the string if True
        - underline: underline the string if True
        '''
        class Color:
            RED = '\033[91m'
            GREEN = '\033[92m'
            YELLOW = '\033[93m'
            BLUE = '\033[94m'
            PURPLE = '\033[95m'
            CYAN = '\033[96m'
            DARKCYAN = '\033[36m'
            BOLD = '\033[1m'
            UNDERLINE = '\033[4m'
            END = '\033[0m'

        res = ''
        if color != None:
            color_l = color.lower()
            if color_l in ['r', 'red']:
                res += Color.RED
            elif color_l in ['g', 'green']:
                res += Color.GREEN
            elif color_l in ['y', 'yellow']:
                res += Color.YELLOW
            elif color_l in ['b', 'blue']:
                res += Color.BLUE
            elif color_l in ['p', 'purple']:
                res += Color.PURPLE
            elif color_l in ['c', 'cyan']:
                res += Color.CYAN
            elif color_l in ['dc', 'darkcyan']:
                res += Color.DARKCYAN

        if bold:
            res += Color.BOLD
        if underline:
            res += Color.UNDERLINE
        res += string+Color.END
        return res

    def get_term_size(self) -> int:
        '''
        return the size of terminal
        '''
        import os
        return os.get_terminal_size().columns

    def get_hbar(self) -> str:
        '''
        return a horizontal bar
        '''
        term_size = self.get_term_size()
        return self.hline*term_size

    def print_ins_list(self, ins_list: list, targets: list = [], full=False):
        '''
        print the instruction list
        '''
        default_formatter = [8, 16, 16, 32]

        def get_ins_formatter(instr_list: list) -> list:
            '''
            return a formatter list, containing the max length for each component
            '''
            res = [0, 0, 0, 0]
            for ins in instr_list:
                try:
                    ins.offset
                except:
                    continue
                offset_l = len(str(ins.offset))

                byte_l = len(ins.insn_byte.hex())
                byte_l = byte_l//2 - 1 + byte_l

                name_l = len(ins.name)
                ssa_l = len(ins.ssa.format())

                for i, t in enumerate([offset_l, byte_l, name_l, ssa_l]):
                    if t > res[i]:
                        res[i] = t
            return res

        def ins2str(instr: VetInstruction, formatter: list = default_formatter) -> str:
            '''
            return a formated string of an instruction
            '''
            def break_byte(byte: str) -> list:
                res = []
                for i in range(0, len(byte), 2):
                    res.append(byte[i:i+2])
                return res

            # 0 indicates the argument's index passed to str.format()
            offset = ('0x{0:0>%d}' % formatter[0]).format(
                hex(instr.offset).replace('0x', ''))

            insn_byte = instr.insn_byte.hex()
            insn_byte = ' '.join(break_byte(insn_byte))
            insn_byte = ('{0: <%d}' % formatter[1]).format(insn_byte)

            name = ('{0: <%d}' % formatter[2]).format(instr.name)
            ssaf = instr.ssa.format()
            # ssa = ('{0: <%d}'%formatter[3]).format(ssaf)
            # opcode = '0x{0:0>2}'.format(hex(instr.opcode).replace('0x', ''))
            return '  '.join([offset, insn_byte, name, ssaf])

        def ins_list2str(ins_list: list) -> str:
            '''
            convert a instruction list to a string
            '''
            res = ''
            for ins in ins_list:
                if type(ins) == str:    # block name
                    res += self.set_color(' '*prelen+'<'+ins+'>\n', 'c')
                elif len(targets) > 0 and ins.offset in targets:
                    res += self.set_color('> ' + ins2str(ins,
                                                         formatter)+'\n', 'g', True)
                else:
                    res += ' '*prelen+ins2str(ins, formatter)+'\n'
            return res

        def get_ins_sets(ins_list: list, targets: list) -> list:
            def get_ins_index(offset: int, ins_list: list) -> int:
                for i, ins in enumerate(ins_list):
                    try:
                        ins.offset
                    except:
                        continue
                    if ins.offset == offset:
                        return i
                return -1

            def size_fit(left: int, right: int, lower: int, upper: int):
                '''
                fit the size [left, right] not exceeding [lower, upper]
                '''
                if left < lower and right > upper:
                    return lower, upper
                elif left < lower:
                    return lower, min(upper, right+(lower-left))
                elif right > upper:
                    return max(lower, left-(right-upper)), upper
                else:
                    return left, right

            def merge_sets(sets: list, max_index: int) -> list:
                def is_intersect(a: list, b: list) -> bool:
                    left, right = sorted([a, b])
                    return left[-1] >= right[0]

                def union_sets(a: list, b: list) -> list:
                    left, right = sorted([a, b])
                    return left[:-1]+right[1:]

                def get_set_size(aset: list) -> int:
                    return aset[-1]-aset[0]+1

                def sets_len_sum(sets: list) -> int:
                    return sum([get_set_size(s) for s in sets])

                def increase_set(aset: list, size: int, max_index: int, low_index: int = 0) -> list:
                    '''
                    increase the set to the target size
                    '''
                    set_size = get_set_size(aset)
                    if set_size >= size:
                        return aset
                    dis = size-set_size
                    left = aset[0]-dis//2
                    right = aset[-1]+(dis-dis//2)
                    left, right = size_fit(left, right, low_index, max_index)
                    return [left]+aset[1:-1]+[right]

                setl = sets
                intersect = True
                while intersect and len(setl) > 1:
                    intersect = False
                    for i in range(len(setl)-1):
                        for j in range(i+1, len(setl)):
                            if is_intersect(setl[i], setl[j]):
                                intersect = True
                                tmp_set = union_sets(setl[i], setl[j])
                                setl.pop(j)  # first pop bigger
                                setl.pop(i)
                                len_sum = sets_len_sum(setl)
                                tmp_set = increase_set(
                                    tmp_set, self.ins_max-len_sum, max_index)
                                setl.append(tmp_set)
                                break
                        if intersect:
                            break
                return sorted(setl)

            sets = []
            lens = self.ins_max//len(targets)
            for t in targets:
                ti = get_ins_index(t, ins_list)
                left_t = ti-lens//2
                right_t = ti+(lens-lens//2)
                left_t, right_t = size_fit(left_t, right_t, 0, len(ins_list)-1)
                set_t = [left_t, ti, right_t]
                sets.append(set_t)
            return merge_sets(sets, len(ins_list)-1)

        prelen = 2
        res = ''
        hbar = self.get_hbar()
        res += hbar+'\n'
        formatter = get_ins_formatter(ins_list)
        if full:
            res += ins_list2str(ins_list)
        else:
            dash = '-'*self.get_term_size()
            dots = ' ' * prelen + self.middot*3
            if len(targets) > 0:
                sets = get_ins_sets(ins_list, targets)
                if len(sets) > 0 and sets[0][0] > 0:
                    res += dots+'\n'+dash+'\n'
                for i, s in enumerate(sets):
                    tmp_list = ins_list[s[0]:s[-1]+1]
                    res += ins_list2str(tmp_list)
                    if i < len(sets)-1:
                        res += dash+'\n'+dots+'\n'+dash+'\n'
                if len(sets) > 0 and sets[-1][-1] < len(ins_list)-1:
                    res += dash+'\n'+dots+'\n'
            else:
                tmp_list = ins_list[:self.ins_max]
                res += ins_list2str(tmp_list)
                if len(tmp_list) < len(ins_list):
                    res += dash+'\n'+dots+'\n'
        res += hbar
        print(res)

    def func2list(self, func: VetFunction) -> list:
        '''
        Convert a function to a string list
        '''
        res = []
        for b in func.basicblocks:
            res.append(b.name)
            for i in b.instructions:
                i = VetInstruction(i)
                res.append(i)
        return res

    def test(self):
        file = EXAMPLE
        emul = Contract(file)
        func = emul.get_VetFunction('apply')
        tar = func.vet_instructions
        self.print_ins_list(tar, [0])
        return emul, func

    def run(self):
        def print_fn(fn: str):
            hbar = self.get_hbar()
            print(hbar)
            print('Function: '+self.set_color(fn, 'y'))

        def check_emul():
            if emul == None:
                print(ERROR+'Please load the file.')
                return False
            return True

        def check_func():
            if not check_emul():
                return False
            if func == None:
                print(ERROR+'Please initialize the function.')
                return False
            return True

        def check_ins():
            try:
                len(ins)
            except:
                print(ERROR+'Please indicate the instruction.')
                return False
            if len(ins) == 0:
                print(ERROR+'Please indicate the instruction.')
                return False
            return True

        def myinput(prompt=''):
            res = input(prompt)
            if not isatty:
                print(res)
            return res

        PROMPT = self.set_color('VetEOS> ', 'b', True)
        ERROR = self.set_color('Error: ', 'r', True)
        WARNING = self.set_color('Warning: ', 'y', True)
        emul = None
        func = None
        ins = []
        import sys
        isatty = sys.stdin.isatty()
        # main loop
        while True:
            s = myinput(PROMPT)
            if s.lower() in ['q', 'exit']:
                break

            elif s == 't':
                emul, func = self.test()

            elif s == 'load':
                filename = myinput('Please input file path: ')
                try:
                    emul = Contract(filename)
                except:
                    print(ERROR+'File loading failed.')
                    continue
                func = None
                ins = []
                print('Loaded file: '+filename)
                print('Function available:')
                print([x.name for x in emul.emul.cfg.functions])

            elif s == 'f' or s.startswith('f '):
                if not check_emul():
                    continue

                func_name = ''
                # if the input is 'f'
                if len(s.split()) == 1:
                    func_name = myinput('Function name: ').strip()
                else:
                    func_name = s.replace('f ', '').strip()
                if len(func_name.split()) > 1:
                    print(WARNING+'Only accept 1 function name.')
                try:
                    func = emul.get_VetFunction(func_name)
                except:
                    print(ERROR+'Invalid function name: ' +
                          self.set_color(func_name, 'y'))
                    continue
                ins = []
                print_fn(func.prefered_name)
                self.print_ins_list(self.func2list(func))

            elif s == 'i' or s.startswith('i '):
                if not check_func():
                    continue

                i_offset = ''
                # if the input is 'i'
                if len(s.split()) == 1:
                    i_offset = myinput('Instruction offset: ').strip()
                else:
                    i_offset = s.replace('i ', '').strip()
                input_ins = i_offset.split()
                ins = []
                error = False
                for i in input_ins:
                    base = 10
                    if i.lower().startswith('0x'):
                        base = 16
                    try:
                        i = int(i, base)
                    except:
                        print(ERROR+'Invalid offset: ' +
                              self.set_color(i, 'y'))
                        error = True
                        break
                    ins.append(i)
                if error:
                    ins = []
                    continue
                print_fn(func.prefered_name)
                self.print_ins_list(self.func2list(func), ins)

            elif s == 'p':
                if not check_ins():
                    continue

                pre_ins = []
                for i_offset in ins:
                    pre = track_prev_one(func.offset2instr[i_offset])
                    if pre != None:
                        pre_ins += pre
                ins = []
                for pi in pre_ins:
                    ins.append(pi.offset)
                print_fn(func.prefered_name)
                self.print_ins_list(self.func2list(func), ins)

            elif s == 'n':
                if not check_ins():
                    continue

                next_ins = []
                for i_offset in ins:
                    nexti = track_next_one(
                        func.offset2instr[i_offset], func.vet_instructions)
                    if nexti != None:
                        next_ins += nexti
                ins = []
                for ni in next_ins:
                    ins.append(ni.offset)
                print_fn(func.prefered_name)
                self.print_ins_list(self.func2list(func), ins)

            elif s == 'fi':
                if not check_func():
                    continue
                print_fn(func.prefered_name)
                self.print_ins_list(self.func2list(func), ins, full=True)

            elif s == 'acg':
                if not check_emul():
                    continue
                tree = emul.get_func_call_tree()
                res = pprint.pformat(tree)
                acn = emul.get_actions()
                for ac in acn:
                    res = res.replace(ac, self.set_color(ac, 'y'))
                # inline = 'send_inline'
                # res = res.replace(inline, self.set_color(inline, 'g'))
                print(res)

            elif s == 'dfg':
                if not check_func():
                    continue
                emul.dataflow_analysis(func.name)
