"""全站样式的入口：把 design-preview 的 v3 设计注入 Streamlit。

CSS 本体在同目录的 theme.css。特意拆成 .css 文件：Streamlit 不会重新加载已经导入过的
.py 模块，改 .py 里的样式字符串必须重启进程才生效；而 apply() 每次都从磁盘读 .css，
所以改完样式只要刷新浏览器就能看到。

用法：在入口 app.py 里调用一次 apply()。
注意：每次 rerun（页面切换 / 点按钮）DOM 都会重建，CSS 必须每轮重新注入，
所以别用 session_state 做「只注入一次」的去重。
"""
from pathlib import Path

import streamlit as st

_CSS_PATH = Path(__file__).with_name("theme.css")

# 品牌 mark：一本翻开的书（与原型一致，避免用三条杠那种「汉堡菜单」符号）
BOOK_SVG = (
    '<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="#fff" '
    'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M12 6.6C10.4 5.2 8.4 4.5 6 4.5H4v13h2c2.4 0 4.4.7 6 2.1 1.6-1.4 3.6-2.1 '
    '6-2.1h2v-13h-2c-2.4 0-4.4.7-6 2.1z"/><path d="M12 6.6v13"/></svg>'
)


def brand_html(name="自习室预约系统", sub="Study Room Booking", cls="side-brand"):
    """品牌区 HTML。cls 用 side-brand（侧边栏）或 login-brand（登录卡片）。"""
    return (
        f'<div class="{cls}">'
        f'<div class="mark">{BOOK_SVG}</div>'
        f'<div><div class="name">{name}</div><div class="sub">{sub}</div></div>'
        f'</div>'
    )


def apply():
    """注入全站样式。每轮都要调用（DOM 会重建），不做去重。"""
    st.markdown(f"<style>{_CSS_PATH.read_text(encoding='utf-8')}</style>",
                unsafe_allow_html=True)
