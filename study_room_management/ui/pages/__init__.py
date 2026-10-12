# 包标识文件，保持为空。
#
# ⚠️ 重要：Streamlit 不会自动发现这个目录下的页面！
#    自动多页机制只认「与入口脚本同级的扁平 pages/ 目录」，
#    不会递归 ui/pages/user/、ui/pages/admin/ 这样的子目录。
#    所有页面必须在 app.py 里用 st.Page(...) + st.navigation(...) 显式注册。
