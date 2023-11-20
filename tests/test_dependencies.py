def test():
    f1, f2, f3 = False, False, False
    try:
        import wasm
        print('wasm test passed.')
        f1 = True
    except:
        print('wasm test failed. Please install wasm')
    try:
        import graphviz
        print('graphviz test passed.')
        f2 = True
    except:
        print('graphviz test failed. Please install graphviz')
    try:
        import timeout_decorator
        print('timeout_decorator test passed.')
        f3 = True
    except:
        print('timeout_decorator test failed. Please install timeout_decorator')
    if f1 and f2 and f3:
        print('All dependency tests passed.')


if __name__ == "__main__":
    test()
