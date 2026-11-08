from collections.abc import Callable

from finagent.relevance import relevant_ids
from finagent.search import search

def recall_at_k(questions : list[dict], passages: list[dict], k: int = 5, k1: float = 1.2, b: float = 0.75,
                retrieve: Callable[[dict, int], list[dict]] | None = None)->float : 
    """ Share of questions whose answer is in one of the k passages the search returns.

    A question counts as found if at least one of its relevant passages (relevant_ids)
    is among the k results of search, filtered by its company and fiscal year.
    Questions with no relevant passage are left out of the average.

    retrieve, if given, replaces the BM25 search: it takes a question record and k and
    returns k passages (dense search, fusion...). k1 and b are then unused.
    """
    R = 0 #R@k score 
    q = 0 #Number of question which has revelant passages. 
    for question in questions:
        true_passage = relevant_ids(question,passages)
        if len(true_passage) == 0 :
            continue
        q += 1 
        if retrieve is None:
            candidates = search(question["question"],passages, ticker=question["ticker"], fiscal_year=question["fiscal_year"],k=k,k1=k1,b=b)
        else:
            candidates = retrieve(question, k)
        passages_id = set(c["id"] for c in candidates)
        if true_passage.intersection(passages_id) :
            R +=1 
    if q == 0 : 
        raise ValueError("No question has a relevant passage")
    return R/q
        
        