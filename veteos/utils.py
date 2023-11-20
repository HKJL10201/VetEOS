import os


def is_db_find(fn: str) -> bool:
    '''
    check if an instruction is used to find the table name
    '''
    return 'db_' in fn and ('find' in fn or 'upperbound' in fn or 'lowerbound' in fn or 'end' in fn)


def is_db_store(fn: str) -> bool:
    '''
    check if an instruction is writing to a table
    '''
    return 'db_' in fn and ('store' in fn or 'update' in fn)


def eosio_name_decoder(value: int) -> str:
    '''
    decode the 64-bit int to a string
    '''
    value = int(value)
    name = ''
    encoding = ".12345abcdefghijklmnopqrstuvwxyz"
    for i in range(59, 0, -5):
        index = (value >> i) & 31
        name += encoding[index]
    dots = 0
    for i in range(len(name)-1, -1, -1):
        if name[i] == '.':
            dots += 1
        else:
            break
    return name[:len(name)-dots]


def addi(item, list: list):
    '''
    add a item to a list if it does not exist in the list
    '''
    if item not in list:
        list.append(item)


def get_file_list(dir_path: str, ends: str = None) -> list:
    '''
    find all files ends with `ends` in `dir_path`
    '''
    res = []
    dir_files = os.listdir(dir_path)  # get file list
    dir_files.sort()
    for file in dir_files:
        file_path = os.path.join(dir_path, file)  # combine path
        if os.path.isfile(file_path):
            if ends != None and not file_path.endswith(ends):
                continue
            res.append(os.path.abspath(file_path))
    return res


def printl(list: list):
    '''
    print a list, one item one line
    '''
    for i in list:
        print(str(i))


def prints(ssa: list):
    '''
    print all SSA format instructions in a list
    '''
    for i in ssa:
        print(i.ssa.format())


def printo(obj):
    '''
    print all attributes of an object
    '''
    print('\n'.join(['%s:%s' % item for item in obj.__dict__.items()]))


def printdic(dic: dict):
    '''
    print a `dict`
    '''
    sp = ' '

    def list2str(lst: list, level: int):
        res = '[\n'
        items = [str(i) for i in lst]
        res += ',\n'.join(items)
        res += '\n]'
        return res

    def dic2str(dic: dict, level: int):
        res = '{\n'
        items = []
        for k in dic.keys():
            # TODO: level
            # tmp += sp*level
            tmp = str(k)+': '
            if type(dic[k]) == dict:
                tmp += '\n'
                tmp += dic2str(dic[k], level+1)
            elif type(dic[k]) == list:
                tmp += '\n'
                tmp += list2str(dic[k], level+1)
            else:
                tmp += str(dic[k])
            items.append(tmp)
        res += ',\n'.join(items)
        res += '\n}'
        return res
    ret = dic2str(dic, 1)
    print(ret)
    return ret
