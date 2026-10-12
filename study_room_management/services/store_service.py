"""门店与座位的管理业务。

预期：list_stores / create_store / update_store / list_seats / batch_add_seats / set_seat_status
权限：店长只能操作自己门店的数据（用 admin.store_id 过滤）。
"""
