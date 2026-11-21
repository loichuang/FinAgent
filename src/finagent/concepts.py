"""The vocabulary shared by the benchmark and the tools: which XBRL names a human label stands for.

CONCEPTS generates the benchmark questions (questions.py) and is what get_fact answers.
RATIO_CONCEPTS holds the extra labels only the ratios need.
"""

# Company names as a user would write them. If the corpus grows, read "entityName"
# from data/xbrl/ instead and strip "Inc." or "Corporation".
names = {
    "AAPL": "Apple",
    "AMZN": "Amazon",
    "GOOGL": "Alphabet",
    "MSFT": "Microsoft",
    "NVDA": "Nvidia",
}


# Label in the question -> XBRL concepts that may carry it, in order of preference.
# For each company and year, the first concept with a value is used.
# Left out on purpose, because Amazon or Alphabet do not report them under this name:
# GrossProfit, Liabilities, ResearchAndDevelopmentExpense.
CONCEPTS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues"],
    "net income": ["NetIncomeLoss"],
    "operating income": ["OperatingIncomeLoss"],
    "diluted earnings per share": ["EarningsPerShareDiluted"],
    "total assets": ["Assets"],
    "total stockholders' equity": ["StockholdersEquity"],
    "cash and cash equivalents": ["CashAndCashEquivalentsAtCarryingValue"],
    "long-term debt": ["LongTermDebtNoncurrent"],
    "net cash provided by operating activities": ["NetCashProvidedByUsedInOperatingActivities"],
    # Nvidia's concept also includes intangible assets: the answer is what each company reports
    "capital expenditures": ["PaymentsToAcquirePropertyPlantAndEquipment",
                             "PaymentsToAcquireProductiveAssets"],
    "cost of revenue": ["CostOfGoodsAndServicesSold", "CostOfRevenue"],
    "income tax expense": ["IncomeTaxExpenseBenefit"],
    "share-based compensation": ["ShareBasedCompensation"],
    "weighted average diluted shares outstanding": [
        "WeightedAverageNumberOfDilutedSharesOutstanding"],
    "total current assets": ["AssetsCurrent"],
    "total current liabilities": ["LiabilitiesCurrent"],
}


# Labels the ratios need beyond CONCEPTS. Kept apart on purpose: CONCEPTS also generates the
# benchmark (all_questions), and a new label there would add questions and reshuffle the frozen
# tuning/test split. "optional": the company may not report the item because it has none, so
# absent means 0. Otherwise absent is an error: a 0 would distort the ratio without a sound.
# Each optional rule was checked against the 10-K text.
RATIO_CONCEPTS = {
    # Debt: all financial debt, whatever its maturity. Cash: cash and current securities
    "long-term debt including current portion": {"xbrl": ["LongTermDebt"], "optional": False},
    # Microsoft and Nvidia 2026: no commercial paper outstanding, nothing tagged
    "commercial paper": {"xbrl": ["CommercialPaper"], "optional": True},
    # Amazon only, under 1 % of its debt
    "short-term borrowings": {"xbrl": ["ShortTermBorrowings"], "optional": True},
    # Nvidia 2026 tags it with its own concept, absent from companyfacts: an error, not a 0
    "current marketable securities": {"xbrl": ["MarketableSecuritiesCurrent",
                                               "ShortTermInvestments"], "optional": False},
    # Cycle
    "accounts receivable": {"xbrl": ["AccountsReceivableNetCurrent"], "optional": False},
    # Alphabet holds no inventory: DIO and CCC are not applicable to it, never 0
    "inventory": {"xbrl": ["InventoryNet"], "optional": False},
    "accounts payable": {"xbrl": ["AccountsPayableCurrent"], "optional": False},
    # Financing. Amazon pays no dividend: a true 0
    "dividends paid": {"xbrl": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
                       "optional": True},
    # Amazon 2025 tags nothing: "no repurchases of our common stock in 2023, 2024, or 2025"
    "share repurchases": {"xbrl": ["PaymentsForRepurchaseOfCommonStock"], "optional": True},
}
