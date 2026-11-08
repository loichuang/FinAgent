"""Query cleaning before BM25: keep the words that tell passages apart."""


from finagent.search import tokenize

# English stop words of NLTK (corpus "stopwords", file "english", 179 words), copied here
# to avoid a dependency. Checked against the 16 labels of CONCEPTS: the only label words
# it contains are "of", "and" and "by", which carry no financial meaning.
# Change this list only for a reason written in a comment, never by looking at a score.
STOPWORDS = frozenset("""
i me my myself we our ours ourselves you you're you've you'll you'd your yours yourself
yourselves he him his himself she she's her hers herself it it's its itself they them
their theirs themselves what which who whom this that that'll these those am is are was
were be been being have has had having do does did doing a an the and but if or because
as until while of at by for with about against between into through during before after
above below to from up down in out on off over under again further then once here there
when where why how all any both each few more most other some such no nor not only own
same so than too very s t can will just don don't should should've now d ll m o re ve y
ain aren aren't couldn couldn't didn didn't doesn doesn't hadn hadn't hasn hasn't haven
haven't isn isn't ma mightn mightn't mustn mustn't needn needn't shan shan't shouldn
shouldn't wasn wasn't weren weren't won won't wouldn wouldn't
""".split())

months = ("september","october","november","december","january","february","march","april","may","june","july","august")

# Words that any question about a 10-K may use and that every passage of a 10-K shares.
# Each one is here for a reason that holds for any question, never for a score.
REPORT_WORDS = frozenset({
    "k",       # left of "10-K" once the digits are gone: every document is a 10-K
    "fiscal",  # every figure of an annual report belongs to a fiscal year
    "year",    # same reason, and the year itself is already chosen by the filter
    "ended",   # part of the date expression ("year ended ..."), like the month and day
    "report",  # asking what a company reports says nothing about which figure
    "much",    # quantity word of "how much", absent from the NLTK list, carries no topic
})


def clean_query(question: str, company: str) -> str:
    """The question without the words that cannot tell apart the passages of one report.

    The search already keeps only the passages of this company and fiscal year, so
    the company name and the date no longer separate anything; stop words never did.

    Limit: every number is removed, so a question that quotes an amount to check
    ("confirm that revenue was 391 billion") loses it. The generated questions never
    quote their answer; the LLM still receives the original question.
    """
    q = tokenize(question)
    c = tokenize(company)
    clean_question= ""
    for word in q : 
        if word in STOPWORDS or word in c :  
            continue 
        if word in months : 
            continue 
        if word.isdigit():
            continue
        if word in REPORT_WORDS:
            continue
        clean_question += f" {word}"
    return clean_question
