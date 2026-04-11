#!/bin/bash
# ai-crawler CLI wrapper

cd "$(dirname "$0")"

export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

show_help() {
    echo "Usage: ./crawl.sh <spider> [options]"
    echo ""
    echo "Spiders:"
    echo "  amazon_search    搜索 Amazon"
    echo "  walmart          搜索 Walmart"
    echo "  multi            多站点搜索"
    echo ""
    echo "Options:"
    echo "  -q, --query      搜索关键词 (default: inflatable)"
    echo "  -p, --pages      搜索页数 (default: 1)"
    echo "  -s, --sites      站点列表，仅 multi 蜘蛛用 (default: amazon,walmart,target)"
    echo ""
    echo "Examples:"
    echo "  ./crawl.sh amazon_search -q inflatable -p 3"
    echo "  ./crawl.sh walmart -q \"pool float\" -p 2"
    echo "  ./crawl.sh multi -q chair -s amazon,target -p 1"
}

SPIDER="${1:-multi}"
QUERY="inflatable"
PAGES="1"
SITES="amazon,walmart,target"

shift 2>/dev/null || true

while [[ $# -gt 0 ]]; do
    case $1 in
        -q|--query)
            QUERY="$2"
            shift 2
            ;;
        -p|--pages)
            PAGES="$2"
            shift 2
            ;;
        -s|--sites)
            SITES="$2"
            shift 2
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

cd "$(dirname "$0")"

case $SPIDER in
    amazon_search)
        exec scrapy crawl amazon_search -a query="$QUERY" -a pages="$PAGES"
        ;;
    walmart)
        exec scrapy crawl walmart -a query="$QUERY" -a pages="$PAGES"
        ;;
    multi)
        exec scrapy crawl multi -a query="$QUERY" -a pages="$PAGES" -a sites="$SITES"
        ;;
    *)
        echo "Unknown spider: $SPIDER"
        show_help
        exit 1
        ;;
esac