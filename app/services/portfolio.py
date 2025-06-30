import pandas as pd
import quantstats as qs
from typing import List


class protfolio:
    def __init__(self, symbol: List[str]):
        self.symbol = symbol
        self.report_html = qs.reports.html(self.symbol, "SPY")
