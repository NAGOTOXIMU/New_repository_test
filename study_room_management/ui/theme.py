"""全站样式的入口：把 design-preview 的 v3 设计注入 Streamlit。

CSS 本体在同目录的 theme.css，类名与设计稿完全一致（.page-title / .panel / .pill / .metric
/ .table-wrap ...），所以页面代码可以直接照抄设计稿的 HTML 结构。

分成 .css 文件是为了改样式不用重启：Streamlit 不会重新加载已经 import 过的 .py 模块，
而 apply() 每次都从磁盘读 .css，改完刷新浏览器就生效。

用法：在入口 app.py 里调用一次 apply()。每轮 rerun 都要重新注入，不要做去重。
"""
from pathlib import Path

import streamlit as st

_CSS_PATH = Path(__file__).with_name("theme.css")

# 设计稿里的品牌 mark：一本翻开的书（不是三条杠那种「汉堡菜单」符号）
BOOK_SVG = (
    '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 6.6C10.4 5.2 8.4 4.5 6 4.5H4v13h2c2.4 0 4.4.7 6 2.1 1.6-1.4 3.6-2.1 '
    '6-2.1h2v-13h-2c-2.4 0-4.4.7-6 2.1z"/><path d="M12 6.6v13"/></svg>'
)


def brand_html(name="自习室预约系统", sub="Study Room Booking"):
    """设计稿的 .brand 结构，登录卡片和侧边栏共用。"""
    return (
        f'<div class="brand"><div class="brand-mark">{BOOK_SVG}</div>'
        f'<div><div class="brand-name">{name}</div><div class="brand-sub">{sub}</div></div></div>'
    )


def apply():
    """注入全站样式。每轮都要调用（DOM 会重建），不做去重。"""
    st.markdown(f"<style>{_CSS_PATH.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True)
