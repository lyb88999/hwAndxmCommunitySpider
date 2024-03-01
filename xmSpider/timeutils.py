from datetime import datetime
import pytz


def convert_timestamp_to_beijing_time(timestamp):
    # 转换为可读的时间格式（UTC）
    dt_utc = datetime.utcfromtimestamp(timestamp / 1000.0)  # 将毫秒转换为秒

    # 设定时区为北京时间
    beijing_timezone = pytz.timezone('Asia/Shanghai')
    dt_beijing = dt_utc.replace(tzinfo=pytz.utc).astimezone(beijing_timezone)

    return dt_beijing

# # 示例用法
# timestamp = 1705631125818
# beijing_time = convert_timestamp_to_beijing_time(timestamp)
# print("转换后的北京时间：", beijing_time)
