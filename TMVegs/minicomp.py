# Usage: cat <machine_yaml_file_name> | python3 minicomp.py > tape.init

from ruamel.yaml import YAML


def main():
        yaml = YAML(typ='safe')
        file = []
        while True:
                try: file.append(input())
                except EOFError: break

        machine_yaml = yaml.load("\n".join(file))

        # print(machine_yaml)

        inp = machine_yaml['input']

        Q = set()
        Gamma = set()
        all_transitions = {}
        for name, transitions in machine_yaml["table"].items():
                Q.add(name)
                if transitions is None: transitions = {}
                for k, v in transitions.items():
                        qp = v.get('R', v.get('L', name))
                        if qp is None: qp = name
                        d = 'R' if 'R' in v else 'L'
                        if type(k) in (int, str):
                                k = str(k)
                                Gamma.add(k)
                                gp = str(v.get('write', k))
                                all_transitions[(name, k)] = (qp, gp, d)
                                continue
                        for sym in k:
                                sym = str(sym)
                                Gamma.add(sym)
                                gp = str(v.get('write', sym))
                                all_transitions[(name, sym)] = (qp, gp, d)

        for q in Q:
                for g in Gamma:
                        if (q, g) not in all_transitions:
                                all_transitions[(q, g)] = (q, g, 'R')

        s = machine_yaml["start state"]
        assert s in Q
        t = "accept"
        assert t in Q
        r = "reject"
        assert r in Q
        left = inp[0]
        assert left in Gamma
        blank = machine_yaml['blank']
        assert blank in Gamma
        Sigma = Gamma - {left, blank}

        Q = list(Q)
        Gamma = list(Gamma)
        Sigma = list(Sigma)

        prefix_bits = ('0'*len(Q) + '1' + '0'*len(Gamma) + '1' + '0'*len(Sigma)
                + '1' + '0'*Q.index(s) + '1' + '0'*Q.index(t)
                + '1' + '0'*Q.index(r) + '1' + '0'*Gamma.index(left)
                + '1' + '0'*Gamma.index(blank) + '1')

        table_bits = "".join(
                [table_entry(trans, Q, Gamma) for trans in all_transitions.items()])

        machine_bits = prefix_bits + table_bits


        inp = inp[1:]

        input_bits = "".join(['0'*Gamma.index(sym) + '1' for sym in inp])


        print(f"{machine_bits}#{input_bits}")


def table_entry(trans, Q, Gamma):
        # print(trans)
        q = trans[0][0]
        g = trans[0][1]
        qp = trans[1][0]
        gp = trans[1][1]
        i = '0' if trans[1][2] == 'L' else '1'

        return ('0'*Q.index(q) + '1' + '0'*Gamma.index(g) + '1'
                + '0'*Q.index(qp) + '1' + '0'*Gamma.index(gp) + '1' + i)


if __name__ == "__main__":
        main()
