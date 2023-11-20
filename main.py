import argparse


def main():
    parser = argparse.ArgumentParser(
        description="Security Analysis tool for EOSIO Smart Contracts in WebAssembly format.")

    # Define the arguments
    parser.add_argument("-f", "--file", type=str,
                        help='binary file (.wasm)',
                        metavar='WASMMODULE')
    parser.add_argument("-g", "--graph", action="store_true",
                        help="generate the analysis summary graph")
    parser.add_argument("-v", "--veteos", action="store_true",
                        help="run vetEOS terminal")
    parser.add_argument("-d", "--dump", action="store_true",
                        help="dump the results")

    args = parser.parse_args()

    if args.file:
        dump_graph = False
        dump_text = False
        if args.graph:
            dump_graph = True
        if args.dump:
            dump_text = True
        from veteos.analyses import get_emul_wrapper
        from veteos.solver import Solver
        emul = get_emul_wrapper(args.file)
        g = Solver(emul)
        g.graph_viz(dump_text=dump_text, dump_graph=dump_graph)

    if not args.file and args.veteos:
        from veteos.terminal import Terminal
        Terminal().run()

    if not args.file and not args.veteos:
        parser.print_help()


if __name__ == "__main__":
    main()
