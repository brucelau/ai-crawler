#!/usr/bin/env python3
"""
ai-crawler CLI - 基于 Scrapy 的电商爬虫

用法:
    scrapy crawl runtime -a query="inflatable" -a pages=3
    scrapy crawl runtime -a sites="amazon,walmart,target" -a query="chair" -a pages=1
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(__file__)), "src"))

from scrapy import cmdline

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    cmdline.execute(["scrapy", "crawl", "runtime", "-a", "query=inflatable", "-a", "pages=1"])
