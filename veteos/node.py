class Node():
    '''
    a node class for building Tree structures
    '''

    def __init__(self, data) -> None:
        self.data = data
        self.parents = []
        self.children = []

    def __str__(self):
        return str(self.as_dict())

    def as_dict(self):
        return {  # 'data': str(self.data),
            'parents': str(self.parents),
            'children': str(self.children)}
