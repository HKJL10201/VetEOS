class SSAnode():
    '''
    SSA class
    '''

    def __init__(self, data, asmt: str, args: str) -> None:
        self.data = data
        self.asmt = asmt
        self.args = args

    def __str__(self) -> str:
        return ' = '.join([self.asmt, self.args])
