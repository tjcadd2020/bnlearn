"""This function provides techniques for structure learning.
  
    import bnlearn as bnlearn


    Description
    -----------
    Structure learning: Given a set of data samples, estimate a DAG that captures the dependencies between the variables.
    Structure learning for *discrete*, *fully observed* networks:
        * Score-based structure estimation (BIC/BDeu/K2 score; exhaustive search, hill climb/tabu search)
        * Constraint-based structure estimation (PC)
        * Hybrid structure estimation (MMHC)


    Example
    -------

    import bnlearn as bnlearn

    # Load example dataframe from sprinkler
    df = bnlearn.import_example()
    # Structure learning
    model = bnlearn.structure_learning.fit(df)
    # Plot
    G = bnlearn.plot(model)

    # Compute structure for many different parameters
    model_hc_k2   = bnlearn.structure_learning.fit(df, methodtype='hc', scoretype='k2')

    # Compare networks
    bnlearn.compare_networks(model, model_hc_k2, pos=G['pos'])

    # Example compare networks
    # Load asia DAG
    model = bnlearn.import_DAG('asia')
    # plot ground truth
    G = bnlearn.plot(model)
    # Sampling
    df = bnlearn.sampling(model, n=10000)
    # Structure learning of sampled dataset
    model_sl = bnlearn.structure_learning.fit(df, methodtype='hc', scoretype='bic')
    # Plot based on structure learning of sampled data
    bnlearn.plot(model_sl, pos=G['pos'])
    # Compare networks and make plot
    bnlearn.compare_networks(model, model_sl, pos=G['pos'])

"""

# ------------------------------------
# Name        : structure_learning.py
# Author      : E.Taskesen
# Contact     : erdogant@gmail.com
# Licence     : See licences
# ------------------------------------


# %% Libraries
import os
import pandas as pd
import networkx as nx
import matplotlib as mpl
import matplotlib.pyplot as plt
import pgmpy
# STRUCTURE LEARNING
from pgmpy.estimators import BdeuScore, K2Score, BicScore
from pgmpy.estimators import ExhaustiveSearch, HillClimbSearch, ConstraintBasedEstimator
# CUSTOM
from bnlearn.helpers.df2onehot import df2onehot
# ASSERTS
from packaging import version  # For pgmpy versioning check for black_list/white_list
assert (nx.__version__)=='1.11', 'This function requires networkx to be v1.11. Try to: pip install networkx==v1.11'
assert (mpl.__version__)=='2.2.3', 'This function requires matplotlib to be v2.2.3. Try to: pip install matplotlib==v2.2.3'
curpath = os.path.dirname(os.path.abspath(__file__))
PATH_TO_DATA=os.path.join(curpath,'DATA')


# %% Structure Learning
def fit(df, methodtype='hc', scoretype='bic', black_list=None, white_list=None, max_indegree=None, verbose=3):
    """Structure learning fit model.

    Parameters
    ----------
    df:         [pd.DataFrame] Pandas DataFrame containing the data
                   f1  ,f2  ,f3
                s1 0   ,0   ,1
                s2 0   ,1   ,0
                s3 1   ,1   ,0

    methodtype:  [STRING] Search strategy for structure_learning.
                'hc' or 'hillclimbsearch' (default) : HillClimbSearch implements a greedy local search if many more nodes are involved
                'ex' or 'exhaustivesearch' : Exhaustive search for very small networks
                'cs' or 'constraintsearch' : Constraint-based Structure Learning by first identifing independencies in the data set using hypothesis test (chi2)

    scoretype:   [STRING]: Scoring function for the search spaces
                 'bic' (default)
                 'k2'
                 'bdeu'

    max_indegree: [int] or [None] If provided and unequal None, the procedure only searches among models where all nodes have at most `max_indegree` parents. Defaults to None.
                  None (default) Works only in case of methodtype='hc'

    black_list:   [list] or [None],  If a list of edges is provided as `black_list`, they are excluded from the search and the resulting model will not contain any of those edges.
                  None (default) Works only in case of methodtype='hc'

    white_list:   [list] or [None], If a list of edges is provided as `white_list`, the search is limited to those edges. The resulting model will then only contain edges that are in `white_list`.
                  None (default) Works only in case of methodtype='hc'

    verbose:    [INT] Print messages to screen.
                0: NONE
                1: ERROR
                2: WARNING
                3: INFO (default)
                4: DEBUG
                5: TRACE

    Returns
    -------
    model

    """

    assert isinstance(pd.DataFrame(), type(df)), 'df must be of type pd.DataFrame()'
    assert (scoretype=='bic') | (scoretype=='k2') | (scoretype=='bdeu'), 'scoretype must be string: "bic", "k2" or "bdeu"'
    assert (methodtype=='hc') | (methodtype=='ex')| (methodtype=='cs') | (methodtype=='exhaustivesearch')| (methodtype=='hillclimbsearch')| (methodtype=='constraintsearch'), 'Methodtype string is invalid'

    config = dict()
    config['verbose'] = verbose
    config['method'] = methodtype
    config['scoring'] = scoretype
    config['black_list'] = black_list
    config['white_list'] = white_list
    config['max_indegree'] = max_indegree

    # Show warnings
    PGMPY_VER = version.parse(pgmpy.__version__[1:])>version.parse("0.1.9")  # Can be be removed if pgmpy >v0.1.9
    if PGMPY_VER and ((black_list is not None) or (white_list is not None)):  # Can be be removed if pgmpy >v0.1.9
        if config['verbose']>=2: print('[BNLEARN][STRUCTURE LEARNING] Warning: black_list and white_list only works for pgmpy > v0.1.9')  # Can be be removed if pgmpy >v0.1.9

    if df.shape[1]>10 and df.shape[1]<15:
        if config['verbose']>=2: print('[BNLEARN][STRUCTURE LEARNING] Warning: Computing DAG with %d nodes can take a very long time!' %(df.shape[1]))
    if (black_list is not None) and methodtype!='hc':
        if config['verbose']>=2: print('[BNLEARN][STRUCTURE LEARNING] Warning: blacklist only works in case of methodtype="hc"')
    if (white_list is not None) and methodtype!='hc':
        if config['verbose']>=2: print('[BNLEARN][STRUCTURE LEARNING] Warning: white_list only works in case of methodtype="hc"')
    if (max_indegree is not None) and methodtype!='hc':
        if config['verbose']>=2: print('[BNLEARN][STRUCTURE LEARNING] Warning: max_indegree only works in case of methodtype="hc"')

    # Make sure columns are of type string
    df.columns = df.columns.astype(str)
    # Make onehot
    # df,labx = _makehot(df, y_min=y_min)

    """
    Search strategies for structure learning
    The search space of DAGs is super-exponential in the number of variables and the above scoring functions allow for local maxima.
    http://pgmpy.chrisittner.de/pages/gsoc-proposal.html

    To learn model structure (a DAG) from a data set, there are three broad techniques:
        1. Score-based structure learning
            a. exhaustivesearch
            b. hillclimbsearch
        2. Constraint-based structure learning
            a. chi-square test
        3. Hybrid structure learning (The combination of both techniques)

        Score-based Structure Learning
        This approach construes model selection as an optimization task. It has two building blocks:
        A scoring function sD:->R that maps models to a numerical score, based on how well they fit to a given data set D.
        A search strategy to traverse the search space of possible models M and select a model with optimal score.
        Commonly used scoring functions to measure the fit between model and data are Bayesian Dirichlet scores such as BDeu or K2
        and the Bayesian Information Criterion (BIC, also called MDL). See [1], Section 18.3 for a detailed introduction on scores.
        As before, BDeu is dependent on an equivalent sample size.
    """

    if config['verbose']>=3: print('[BNLEARN][STRUCTURE LEARNING] Computing best DAG using [%s]' %(config['method']))

    # ExhaustiveSearch can be used to compute the score for every DAG and returns the best-scoring one:
    if config['method']=='ex' or config['method']=='exhaustivesearch':
        """
        The first property makes exhaustive search intractable for all but very small networks,
        the second prohibits efficient local optimization algorithms to always find the optimal structure.
        Thus, identifiying the ideal structure is often not tractable.
        Despite these bad news, heuristic search strategies often yields good results
        If only few nodes are involved (read: less than 5).
        """
        if (df.shape[1]>15) and (config['verbose']>=3):
            print('[BNLEARN][STRUCTURE LEARNING] Warning: Structure learning with more then 15 nodes is computationally not feasable with exhaustivesearch. Use hillclimbsearch or constraintsearch instead!!')
        out = _exhaustivesearch(df, scoretype=config['scoring'], verbose=config['verbose'])

    # HillClimbSearch
    if config['method']=='hc' or config['method']=='hillclimbsearch':
        """
        Once more nodes are involved, one needs to switch to heuristic search.
        HillClimbSearch implements a greedy local search that starts from the DAG
        "start" (default: disconnected DAG) and proceeds by iteratively performing
        single-edge manipulations that maximally increase the score.
        The search terminates once a local maximum is found.
        """
        out = _hillclimbsearch(df, scoretype=config['scoring'], verbose=config['verbose'], black_list=config['black_list'], white_list=config['white_list'], max_indegree=config['max_indegree'])

    # Constraint-based Structure Learning
    if config['method']=='cs' or config['method']=='constraintsearch':
        """
        Constraint-based Structure Learning
        A different, but quite straightforward approach to build a DAG from data is this:
        Identify independencies in the data set using hypothesis tests
        Construct DAG (pattern) according to identified independencies (Conditional) Independence Tests
        Independencies in the data can be identified using chi2 conditional independence tests.
        To this end, constraint-based estimators in pgmpy have a test_conditional_independence(X, Y, Zs)-method,
        that performs a hypothesis test on the data sample. It allows to check if X is independent from Y given a set of variables Zs:
        """
        out = _constraintsearch(df, verbose=config['verbose'])

    # Setup simmilarity matrix
    adjmat = pd.DataFrame(data=False, index=out['model'].nodes(), columns=out['model'].nodes()).astype('Bool')
    # Fill adjmat with edges
    edges=out['model'].edges()
    for edge in edges:
        adjmat.loc[edge[0],edge[1]]=True

    # Store
    out['adjmat']=adjmat
    # return
    return(out)


# %% Constraint-based Structure Learning
def _constraintsearch(df, significance_level=0.05, verbose=3):
    """.

    test_conditional_independence() returns a tripel (chi2, p_value, sufficient_data),
    consisting in the computed chi2 test statistic, the p_value of the test, and a heuristig
    flag that indicates if the sample size was sufficient.
    The p_value is the probability of observing the computed chi2 statistic (or an even higher chi2 value),
    given the null hypothesis that X and Y are independent given Zs.
    This can be used to make independence judgements, at a given level of significance.
    """

    out=dict()
    # Set search algorithm
    model = ConstraintBasedEstimator(df)

    # Some checks for dependency
    #    print(_is_independent(est, 'Sprinkler', 'Rain', significance_level=significance_level))
    #    print(_is_independent(est, 'Cloudy', 'Rain', significance_level=significance_level))
    #    print(_is_independent(est, 'Sprinkler', 'Rain',  ['Wet_Grass'], significance_level=significance_level))

    """
    DAG (pattern) construction
    With a method for independence testing at hand, we can construct a DAG from the data set in three steps:
        1. Construct an undirected skeleton - `estimate_skeleton()`
        2. Orient compelled edges to obtain partially directed acyclid graph (PDAG; I-equivalence class of DAGs) - `skeleton_to_pdag()`
        3. Extend DAG pattern to a DAG by conservatively orienting the remaining edges in some way - `pdag_to_dag()`

        Step 1.&2. form the so-called PC algorithm, see [2], page 550. PDAGs are `DirectedGraph`s, that may contain both-way edges, to indicate that the orientation for the edge is not determined.
    """
    # Estimate using chi2
    [skel, seperating_sets] = model.estimate_skeleton(significance_level=significance_level)

    print("Undirected edges: ", skel.edges())
    pdag = model.skeleton_to_pdag(skel, seperating_sets)
    print("PDAG edges: ", pdag.edges())
    dag = model.pdag_to_dag(pdag)
    print("DAG edges: ", dag.edges())

    out['undirected']=skel
    out['undirected_edges']=skel.edges()
    out['pdag']=pdag
    out['pdag_edges']=pdag.edges()
    out['dag']=dag
    out['dag_edges']=dag.edges()

    # Search using "estimate()" method provides a shorthand for the three steps above and directly returns a "BayesianModel"
    best_model = model.estimate(significance_level=significance_level)
    out['model']=best_model
    out['model_edges']=best_model.edges()

    print(best_model.edges())

    """
    PC PDAG construction is only guaranteed to work under the assumption that the
    identified set of independencies is *faithful*, i.e. there exists a DAG that
    exactly corresponds to it. Spurious dependencies in the data set can cause
    the reported independencies to violate faithfulness. It can happen that the
    estimated PDAG does not have any faithful completions (i.e. edge orientations
    that do not introduce new v-structures). In that case a warning is issued.
    """
    return(out)


# %% hillclimbsearch
def _hillclimbsearch(df, scoretype='bic', black_list=None, white_list=None, max_indegree=None, verbose=3):
    out=dict()
    # Set scoring type
    scoring_method = _SetScoringType(df, scoretype)
    # Set search algorithm
    model = HillClimbSearch(df, scoring_method=scoring_method)
    # Compute best DAG
    try:
        best_model = model.estimate(max_indegree=max_indegree, black_list=black_list, white_list=white_list)
        # print("Works only for version > v.0.1.9")
    except:
        best_model = model.estimate(max_indegree=max_indegree)  # Can be be removed if pgmpy >v0.1.9

    # Store
    out['model']=best_model
    out['model_edges']=best_model.edges()
    # Return
    return(out)


# %% ExhaustiveSearch
def _exhaustivesearch(df, scoretype='bic', return_all_dags=False, verbose=3):
    out=dict()

    # Set scoring type
    scoring_method = _SetScoringType(df, scoretype)
    # Exhaustive search across all dags
    model = ExhaustiveSearch(df, scoring_method=scoring_method)
    # Compute best DAG
    best_model = model.estimate()
    # Store
    out['model']=best_model
    out['model_edges']=best_model.edges()

    # Compute all possible DAGs
    if return_all_dags:
        out['scores']=[]
        out['dag']=[]
        # print("\nAll DAGs by score:")
        for [score, dag] in reversed(model.all_scores()):
            out['scores'].append(score)
            out['dag'].append(dag)
            # print(score, dag.edges())

        plt.plot(out['scores'])
        plt.show()

    return(out)


# %% Set scoring type
def _SetScoringType(df, scoretype, verbose=3):
    if verbose>=3: print('[BNLEARN][STRUCTURE LEARNING] Set scoring type at [%s]' %(scoretype))

    if scoretype=='bic':
        scoring_method = BicScore(df)
    elif scoretype=='k2':
        scoring_method = K2Score(df)
    elif scoretype=='bdeu':
        scoring_method = BdeuScore(df, equivalent_sample_size=5)

    return(scoring_method)


# %%
def _is_independent(model, X, Y, Zs=[], significance_level=0.05):
    return model.test_conditional_independence(X, Y, Zs)[1] >= significance_level


# %% Make one-hot matrix
def _makehot(df, y_min=None):
    labx=[]
    colExpand=[]
#    colOK=[]
    Xhot=pd.DataFrame()
    dfOK=pd.DataFrame()
    for i in range(0,df.shape[1]):
        if len(df.iloc[:,i].unique())>2:
            colExpand.append(df.columns[i])
        else:
            if df[df.columns[i]].dtype=='O':
                uicol=df[df.columns[i]].unique()
                dfOK[uicol[0]]=df[df.columns[i]]==uicol[0]
            else:
                dfOK = pd.concat([dfOK, Xhot], axis=1)
                labx.append(df.columns[i])
                #colOK.append(df.columns[i])

    if len(colExpand)>0:
        [_, Xhot, Xlabx, _] = df2onehot(df[colExpand], y_min=y_min, hot_only=True)
        labx.append(Xlabx)
        Xhot=Xhot.astype(int)
    
    out = pd.concat([Xhot, dfOK], axis=1)
    out = out.astype(int)

    return(out, labx[0])


# %% PLOT
# def plot(model, pos=None, scale=1, figsize=(15,8), verbose=3):
#     """Plot the learned stucture.


#     Parameters
#     ----------
#     model : dict
#         Learned model from the .fit() function.
#     pos : graph, optional (default: None)
#         Coordinates of the network. If there are provided, the same structure will be used to plot the network.
#     scale : int, optional (default: 1)
#         Scaling parameter for the network. A larger number will linearily increase the network.
#     figsize : tuple, optional (default: (15,8))
#         Figure size.
#     verbose : int [0-5], optional (default: 3)
#         Print messages.
#         0: (default)
#         1: ERROR
#         2: WARN
#         3: INFO
#         4: DEBUG


#     Returns
#     -------
#     dict.

#     """

#     out=dict()
#     G = nx.DiGraph()  # Directed graph
#     layout='fruchterman_reingold'

#     # Extract model if in dict
#     if 'dict' in str(type(model)):
#         model = model.get('model', None)

#     # Bayesian model
#     if 'BayesianModel' in str(type(model)) or 'pgmpy' in str(type(model)):
#         if verbose>=3: print('[BNLEARN.plot] Making plot based on BayesianModel')
#         # positions for all nodes
#         pos = network.graphlayout(model, pos=pos, scale=scale, layout=layout)
#         # Add directed edge with weigth
#         # edges=model.edges()
#         edges=[*model.edges()]
#         for i in range(len(edges)):
#             G.add_edge(edges[i][0], edges[i][1], weight=1, color='k')
#     elif 'networkx' in str(type(model)):
#         if verbose>=3: print('[BNLEARN.plot] Making plot based on networkx model')
#         G=model
#         pos = network.graphlayout(G, pos=pos, scale=scale, layout=layout)
#     else:
#         if verbose>=3: print('[BNLEARN.plot] Making plot based on adjacency matrix')
#         G = network.adjmat2graph(model)
#         # Convert adjmat to source target
# #        df_edges=model.stack().reset_index()
# #        df_edges.columns=['source', 'target', 'weight']
# #        df_edges['weight']=df_edges['weight'].astype(float)
# #
# #        # Add directed edge with weigth
# #        for i in range(df_edges.shape[0]):
# #            if df_edges['weight'].iloc[i]!=0:
# #                color='k' if df_edges['weight'].iloc[i]>0 else 'r'
# #                G.add_edge(df_edges['source'].iloc[i], df_edges['target'].iloc[i], weight=np.abs(df_edges['weight'].iloc[i]), color=color)
#         # Get positions
#         pos = network.graphlayout(G, pos=pos, scale=scale, layout=layout)

#     # Bootup figure
#     plt.figure(figsize=figsize)
#     # nodes
#     nx.draw_networkx_nodes(G, pos, node_size=500, with_labels=True, alpha=0.85)
#     # edges
#     colors = [G[u][v].get('color','k') for u,v in G.edges()]
#     weights = [G[u][v].get('weight',1) for u,v in G.edges()]
#     nx.draw_networkx_edges(G, pos, arrowstyle='->', edge_color=colors, width=weights)
#     # Labels
#     nx.draw_networkx_labels(G, pos, font_size=20, font_family='sans-serif')
#     # Get labels of weights
#     # labels = nx.get_edge_attributes(G,'weight')
#     # Plot weights
#     nx.draw_networkx_edge_labels(G, pos, edge_labels=nx.get_edge_attributes(G,'weight'))
#     # Making figure nice
#     ax = plt.gca()
#     ax.set_axis_off()
#     plt.show()

#     # Store
#     out['pos']=pos
#     out['G']=G
#     return(out)


# %% Comparison of two networks
# def compare_networks(model_1, model_2, pos=None, showfig=True, figsize=(15,8), verbose=3):
#     """Compare networks of two models.


#     Parameters
#     ----------
#     model_1 : dict
#         Results of model 1.
#     model_2 : dict
#         Results of model 2.
#     pos : graph, optional (default: None)
#         Coordinates of the network. If there are provided, the same structure will be used to plot the network.
#     showfig : Bool, optional (default: True)
#         Show figure.
#     figsize : tuple, optional (default: (15,8))
#         Figure size.
#     verbose : int [0-5], optional (default: 3)
#         Print messages.
#         0: (default)
#         1: ERROR
#         2: WARN
#         3: INFO
#         4: DEBUG

#     Returns
#     -------
#     dict.

#     """
#     [scores, adjmat_diff] = network.compare_networks(model_1['adjmat'], model_2['adjmat'], pos=pos, showfig=showfig, width=figsize[0], height=figsize[1], verbose=verbose)
#     return(scores, adjmat_diff)
