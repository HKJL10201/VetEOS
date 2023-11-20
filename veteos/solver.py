from veteos.analyzer import Analyzer
from veteos.contract import Contract
import os


class Solver:
    '''
    main GDV detection solver
    '''

    def __init__(self, emul: Contract, ssa: bool = False) -> None:
        self.emul = emul
        self.ssa = ssa
        self.analyzer = Analyzer(ssa)

    def list2str(self, raw: list, c: str = ':'):
        '''
        convert list to string
        '''
        # if len(raw) == 0:
        #     return ''
        title = raw[0].split(c)[0]+c
        return title+('\l' if not title.endswith('\l') else '') + ('\l'.join(raw)).replace(title, '')

    def str2html(self, s: str, title: str):
        '''
        convert string to html format
        '''
        if s.endswith('\l'):
            s = s[:-2]
        fs = 16
        s = s.replace('<', '&lt;').replace('>', '&gt;')
        return '<<table border="0" cellborder="0">\
            <tr><td><font point-size="%d" color="blue">&lt;%s&gt;</font></td></tr>\
                <tr><td align="left"><font point-size="%d">%s</font></td></tr></table>>'\
        % (fs, title, fs, s.replace('\l', '</font></td></tr><tr><td align="left"><font point-size="%d">' % fs)
           .replace('&lt;', '</font><font point-size="%d" color="orange">&lt;' % fs))

    def pay2play_wp(self):
        '''
        wrapper for pay2play detection
        '''
        raw = self.analyzer.pay2play(self.emul)
        if raw == None:
            return 'None'
        res = raw['eosio.token']+raw['transfer']
        return self.list2str(res)+'\l'

    def checkCondition_wp(self):
        '''
        wrapper for checkCondition detection
        '''
        raw = self.analyzer.checkCondition(self.emul)
        if raw == None:
            return 'None'
        return self.list2str(raw)+'\l'

    def createSecret_wp(self):
        '''
        wrapper for createSecret detection
        '''
        # only works for 'rem'
        raw = self.analyzer.createSecret(self.emul)
        if raw == None:
            return 'None'
        return self.list2str(raw)+'\l'

    def notify_wp(self):
        '''
        wrapper for notify detection
        '''
        raw = self.analyzer.notify(self.emul)
        if raw == None:
            return 'None'
        res = ''
        ts = raw['eosio.token::transfer']
        rc = raw['require_recipient']
        tmp = []
        if ts != None:
            for k in ['eosio.token', 'transfer', 'active',]:
                tmp.append(ts[k][0])
            res = [self.list2str(tmp)]
            res.append(self.list2str([ts['inline'][-1]]))
            res = self.list2str(res, '\l')
        if len(rc) > 0:
            res += self.list2str([rc[-1]])
        return res+'\l'

    def stateIO_wp(self):
        '''
        wrapper for stateIO detection
        '''
        def dic_ana(raw: list):
            '''
            return a dict whose keys are table names
            '''
            res = {}
            dbg = 'db_get'
            dbs = 'db_store'
            for dc in raw:
                dbf = dc['db_find']
                key = dbf[-3].split()[-1]
                if key not in res.keys():
                    dbt = dc[dbg] if dbg in dc.keys() else dc[dbs]
                    res[key] = '\l'.join(
                        [self.list2str([dbf[-3], dbf[-1]]), self.list2str([dbt])])
                else:
                    continue
            return res
        rd = self.analyzer.stateIO(self.emul)
        wt = self.analyzer.stateIO(self.emul, read=False)
        if rd == None or wt == None:
            return 'None', 'None', 'None'
        rdd = dic_ana(rd)
        wtd = dic_ana(wt)
        tmp = ''
        rddk = list(rdd.keys())
        wtdk = list(wtd.keys())
        for k in rddk:
            if k in wtdk:
                tmp = k
                break
        secret = wtdk[1] if len(wtdk) > 1 else wtdk[0]
        if tmp != '':
            if secret == tmp and len(wtdk) > 1:
                secret = wtdk[0]
            return rdd[tmp]+'\l', wtd[tmp]+'\l', wtd[secret]+'\l'
        else:
            return rdd[rddk[0]]+'\l', wtd[wtdk[0]]+'\l', wtd[secret]+'\l'

    def graph_viz(self, filename=None, dump_text=False, dump_graph=True):
        '''
        generate analysis summary graph
        '''
        def viz(filename='summary.gv', TB=True):
            from graphviz import Digraph

            def T1():
                with g.subgraph(name='cluster_T1') as c:
                    # c.attr(rank='min')
                    c.attr(label='T1')
                    c.node('createSecret', label=n3)
                    c.node('actionT1m', label='<actionT1m>')
                    c.node('actionT1n', label='<actionT1n>')
                    c.edge('createSecret', 'actionT1m')
                    c.edge('actionT1m', 'actionT1n')

            def T2():
                with g.subgraph(name='cluster_T2') as c:
                    # c.attr(rank='same')
                    c.attr(label='T2')
                    c.node('payToPlay', label=n1)
                    c.node('checkCondition', label=n2)
                    c.node('writeState', label=n4)
                    c.node('notify', label=n5)
                    c.edge('payToPlay', 'checkCondition')
                    c.edge('checkCondition', 'writeState')
                    c.edge('checkCondition', 'notify')
                    c.edge('writeState', 'notify')

            def T3():
                with g.subgraph(name='cluster_T3') as c:
                    # c.attr(rank='max')
                    c.attr(label='T3')
                    c.node('readState', label=n6)
                    c.node('actionT3m', label='<actionT3m>')
                    c.node('actionT3n', label='<actionT3n>')
                    c.edge('readState', 'actionT3m')
                    c.edge('actionT3m', 'actionT3n')
            g = Digraph('G', filename=filename)
            g.attr(overlap='scale')
            g.attr(splines='polyline')
            g.attr(ratio='fill')
            g.attr('node', shape='rectangle')
            g.attr('node', fontsize='16')
            g.attr('graph', style='dashed', color='darkgrey', fontsize='16.0'
                   # ,rankdir='LR'
                   )
            if TB:
                g.attr(rankdir='TB')
                T1()
                T2()
                T3()
            else:
                g.attr(rankdir='LR')
                T3()
                T2()
                T1()
            g.render(filename, view=False)
            return

        thisfile = self.emul.filename.split(os.path.sep)[-1]
        n1 = self.pay2play_wp()
        n2 = self.checkCondition_wp()
        n3 = self.createSecret_wp()
        n6, n4, secret = self.stateIO_wp()
        n5 = self.notify_wp()
        n3 = secret if n3 == 'None' else n3

        result_str = ['Detected Vulnerability Patterns:', 'F1 (Revertable):', n1[:-2], n5, 'F2 (Unpredictably Profitable):',
                      n3, 'F3 (Information Leakage):', n4[:-2], n6, 'F4 (Causal Inference):', n2]
        result_str = '\n'.join(result_str).replace('\l', '\n')
        vul_flag = True
        for pattern in [n1, n2, n3, n4, n5, n6]:
            if pattern == "None":
                vul_flag = False
                break
        if vul_flag:
            result_str += '\nResult:\nDetected Groundhog Day Vulnerability in file %s\nCode:1' % thisfile
        else:
            result_str += '\nResult:\nNo Groundhog Day Vulnerability in file %s\nCode:0' % thisfile
        print(result_str)

        result_dir = 'results'
        if not os.path.exists(result_dir):
            os.makedirs(result_dir)
        if dump_text:
            with open(os.path.join(result_dir, thisfile+'.log'), 'w') as wlog:
                wlog.write(result_str)
        if not dump_graph:
            return vul_flag

        t1 = 'payToPlay'
        t2 = 'checkCondition'
        t3 = 'createSecret'
        t4 = 'writeState'
        t5 = 'notify'
        t6 = 'readState'
        n1 = self.str2html(n1, t1)
        n2 = self.str2html(n2, t2)
        n3 = self.str2html(n3, t3)
        n4 = self.str2html(n4, t4)
        n5 = self.str2html(n5, t5)
        n6 = self.str2html(n6, t6)

        if filename == None:
            filename = thisfile
        viz(os.path.join(result_dir, filename+'.gv'))
        return vul_flag
