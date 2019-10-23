import networkx as nx
import os
import pickle as pkl
import csv


def joern_edge_to_edgelist(edge_file):
    ''' converts an edges.csv file generated by Joern into a simple edgelist '''
    edge_list = {}
    with open(edge_file, 'r') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter='\t')
        first_line = True
        for row in csv_reader:
            # Skip first line
            if first_line:
                first_line = False
                continue
            if row[0] not in edge_list:
                edge_list[row[0]] = [ (row[1], row[2]) ]
            else:
                edge_list[row[0]].append((row[1], row[2]))

    return edge_list


def joern_to_networkx(nodes_file,  edge_file, func_names=None):
    ''' Converts a joern nodes.csv and edges.csv into a list of NetworkX graphs '''

    edge_list = joern_edge_to_edgelist(edge_file)

    graphs = []
    with open(nodes_file, 'r') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter='\t')
        first_line = True
        processing_func = False
        curr_meta = {}
        for row in csv_reader:
            # Skip first line
            if first_line:
                first_line = False
                continue
            if row[2] == "Function":
                if processing_func: # New function so stop previous function processing
                    # add edges
                    for src_n in curr_meta['graph'].nodes():
                        if src_n in edge_list:
                           for (dst_n, e_type) in edge_list[src_n]:
                               curr_meta['graph'].add_edge(src_n, dst_n, type=e_type)
                    graphs.append(curr_meta)
                    processing_func = False
                    curr_meta = {}

                # Found a new function
                # row[4] is function name
                # row[5] is function location in line_num:x:x:x
                if not func_names or row[3] in func_names:
                    curr_meta['location'] = row[4]
                    curr_meta['graph'] = nx.MultiDiGraph()
                    curr_meta['name'] = row[3]
                    processing_func = True
            else:
                # not a function start.  so just see if we processing or not
                if processing_func:
                    curr_meta['graph'].add_node(row[1]) # add node to graph
                    curr_meta['graph'].node[row[1]]['type'] = row[2]
                    curr_meta['graph'].node[row[1]]['code'] = row[3]
                    curr_meta['graph'].node[row[1]]['functionId'] = row[5]
        # end of csv file
        # lets check to make sure we didnt end on a function we were processing
        if processing_func:
            # need to finish off this function
            # add edges
            for src_n in curr_meta['graph'].nodes():
                if src_n in edge_list:
                    for (dst_n, e_type) in edge_list[src_n]:
                        curr_meta['graph'].add_edge(src_n, dst_n, type=e_type)
            graphs.append(curr_meta)
            processing_func = False
    # now we have processed both the nodes.csv and edges.csv for this source code file
    return graphs

def tripleize(G):
    ''' Turns a graph into a set of code -> Relationship -> Code triples '''
    # Need to add DOM/POST_DOM relationships
    G_trips=set([])
    for n in G.nodes():
        for nbor in G.neighbors(n):
            if G.node[n]['code'] != '':
                first = G.node[n]['code']
            else:
                first = G.node[n]['type']
            if G.node[nbor]['code'] != '':
                second = G.node[nbor]['code']
            else:
                second = G.node[nbor]['type']

            # Possible to have multiple edges.  Add a triplet for each
            for e in G[n][nbor].values():
                rela=e['type']
                G_trips.add((first,rela,second))

    # loop through graph again, this time building out DOM/POST_DOM rels
    for n in G.nodes():
        dom_nodes = set([])
        num_changes = 0
        
        for nbor in G.neighbors(n):
            for e in G[n][nbor].values():
                if e['type'] == 'DOM':
                    dom_nodes.add(nbor)

        num_dom_nodes_before = len(dom_nodes)
        num_dom_nodes_after = -1
        while num_dom_nodes_before != num_dom_nodes_after:
            num_dom_nodes_before = len(dom_nodes)
            for dom_n in list(dom_nodes):
                for nbor in G.neighbors(dom_n):
                    for e in G[dom_n][nbor].values():
                        if e['type'] == 'DOM':
                            dom_nodes.add(nbor)
            num_dom_nodes_after = len(dom_nodes)

        # Now we should have ALL nodes dominated by n
        if G.node[n]['code'] != '':
            first = G.node[n]['code']
        else:
            first = G.node[n]['type']
        for dom_node in dom_nodes:
            if G.node[dom_node]['code'] != '':
                second = G.node[dom_node]['code']
            else:
                second = G.node[dom_node]['type']
            G_trips.add((first, 'DOM', second))

    # Yikes now we do sam ething for POST DOM
    for n in G.nodes():
        post_dom_nodes = set([])
        num_changes = 0

        for nbor in G.neighbors(n):
            for e in G[n][nbor].values():
                if e['type'] == 'POST_DOM':
                    post_dom_nodes.add(nbor)

        num_post_dom_nodes_before = len(post_dom_nodes)
        num_post_dom_nodes_after = -1
        while num_post_dom_nodes_before != num_post_dom_nodes_after:
            num_post_dom_nodes_before = len(post_dom_nodes)
            for post_dom_n in list(post_dom_nodes):
                for nbor in G.neighbors(post_dom_n):
                    for e in G[post_dom_n][nbor].values():
                        if e['type'] == 'POST_DOM':
                            post_dom_nodes.add(nbor)
            num_post_dom_nodes_after = len(post_dom_nodes)

        # Now we should have ALL nodes dominated by n
        if G.node[n]['code'] != '':
            first = G.node[n]['code']
        else:
            first = G.node[n]['type']
        for post_dom_node in post_dom_nodes:
            if G.node[post_dom_node]['code'] != '':
                second = G.node[post_dom_node]['code']
            else:
                second = G.node[post_dom_node]['type']
            G_trips.add((first, 'POST_DOM', second))

            

    return G_trips

def vectorize(G):
    vector_dims = [ 'FLOWS_TO','DECLARES','IS_CLASS_OF','REACHES','CONTROLS','DOM','POST_DOM','USE','DEF','IS_AST_PARENT','CallExpression','Callee','Function','ArgumentList','AssignmentExpr','File','IdentifierDeclStatement','Parameter','Symbol', 'PostIncDecOperationExpression', 'Identifier', 'IncDec', 'ExpressionStatement', 'AssignmentExpression', 'ArrayIndexing','IfStatement', 'Condition', 'AdditiveExpression', 'Argument' , 'PrimaryExpression', 'CastExpression', 'CastTarget', 'PtrMemberAccess','Statement', 'ReturnStatement', 'EqualityExpression', 'ElseStatement', 'ParameterType', 'ParameterList', 'SizeofExpression', 'IdentifierDeclType', 'UnaryOperator', 'MultiplicativeExpression', 'MemberAccess', 'FunctionDef', 'AndExpression', 'CFGEntryNode', 'UnaryOperationExpression', 'ForStatement', 'ForInit', 'ShiftExpression', 'ReturnType', 'Sizeof', 'BreakStatement', 'OrExpression', 'WhileStatement', 'SizeofOperand', 'IdentifierDecl', 'CompoundStatement', 'CFGExitNode', 'RelationalExpression', 'BitAndExpression','CFGErrorNode','ClassDef','ClassDefStatement','ConditionalExpression','ContinueStatement','Decl','DeclStmt','DoStatement','ExclusiveOrExpression','Expression','GotoStatement','InclusiveOrExpression','InitializerList','Label','SwitchStatement','UnaryExpression','InfiniteForNode']
    vec = [0] * len(vector_dims)
    for n in G.nodes():
        t = G.node[n]['type']
        if t in vector_dims:
            vec[vector_dims.index(t)] += 1
        else:
            print("Missing node type: ", t)

    for (n1,n2) in G.edges():
        for e in G[n1][n2]: # multi edges
            t = G[n1][n2][e]['type']
            if t in vector_dims:
                vec[vector_dims.index(t)] += 1
            else:
                print("Missing edge type: ", t)
    return vec




def load_vgraph_db(root):
    vgraph_db=[]
    for repo in os.listdir(root):
        for cve in os.listdir('/'.join([root,repo])):
            for hsh in os.listdir('/'.join([root,repo,cve])):
                for f in os.listdir('/'.join([root,repo,cve,hsh])):
                    for func in os.listdir('/'.join([root,repo,cve,hsh,f])):
                        if func.endswith('_pvg.pkl'):
                            # Found vGraph
                            func_root = str(func[:-len('_pvg.pkl')])
                            cvg=pkl.load(open(root + '/%s/%s/%s/%s/%s_%s'%(repo,cve,hsh,f,func_root,'cvg.pkl'),'rb'))
                            pvg=pkl.load(open(root + '/%s/%s/%s/%s/%s_%s'%(repo,cve,hsh,f,func_root,'pvg.pkl'),'rb'))
                            nvg=pkl.load(open(root + '/%s/%s/%s/%s/%s_%s'%(repo,cve,hsh,f,func_root,'nvg.pkl'),'rb'))
                            vec=pkl.load(open(root + '/%s/%s/%s/%s/%s_%s'%(repo,cve,hsh,f,func_root,'vec.pkl'),'rb'))
                            vgraph_db.append({
                                'repo':repo,
                                'cve':cve,
                                'hsh':hsh,
                                'file':f,
                                'func':func_root,
                                'cvg':cvg,
                                'pvg':pvg,
                                'nvg':nvg,
                                'vec':vec
                            })

    return vgraph_db

def load_target_db(root):
    target_graph_db = []
    for root, dirs, files in os.walk(root):
        for f in files:
            if f.endswith(".gpickle"): # this is a target graph
                base_name = f[:-len('.gpickle')]
                try:
                    target_graph_db.append({
                        'dir': root,
                        'base_name': base_name,
                        'path':"%s/%s" % (root, f),
                        #'graph': nx.read_gpickle("%s/%s" % (root, f)),
                        'triples': pkl.load(open("%s/%s" % (root, base_name + '.triples'), 'rb')),
                        'vec': pkl.load(open("%s/%s" % (root, base_name + '.vec'), 'rb'))
                    })
                except:
                    # error loading target.  skip.
                    continue
    return target_graph_db


