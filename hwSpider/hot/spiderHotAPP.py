import sys
import tkinter as tk
from tkinter import messagebox
import asyncio
import httpx
from threading import Thread
import pandas as pd

from IOStream import ConsoleRedirector
from tkinter import filedialog

from timeutils import convert_timestamp_to_beijing_time


class AsyncSpider:
    def __init__(self):
        self.url = 'https://sgw-cn.c.huawei.com/forward/club/feeds_h5/circleHotPost/1'
        self.headers = {
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Content-Type': 'application/json',
            'Origin': 'https://cn.club.vmall.com',
            'Referer': 'https://cn.club.vmall.com/',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'cross-site',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'X-Requested-With': 'XMLHttpRequest',
            'request-source': 'H5',
            'sec-ch-ua': '"Chromium";v="118", "Google Chrome";v="118", "Not=A?Brand";v="99"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"macOS"',
            'site': 'zh_CN',
            'SGW-APP-ID': 'EDCF82D77A5AB59706CD5F2163F67427',
        }

    async def fetch_comments(self, client, thread_id):
        url = 'https://sgw-cn.c.huawei.com/forward/club/content_h5/queryThreadDetail/1'

        # 初始值
        data = f'{{"threadId":"{thread_id}","pageIndex":1,"pageSize":20,"orderBy":1}}'
        page_index = 1
        comments = []

        while True:
            response = await client.post(url, headers=self.headers, data=data)
            response_json = response.json()

            # 如果没有更多评论数据，退出循环
            if not response_json.get("data", {}).get("postList"):
                break

            post_list = response_json["data"]["postList"]

            # 提取评论的 authorInfo 和 text
            for post in post_list:
                comments.append({
                    "name": post.get("authorInfo", {}).get("name", ""),
                    "userId": post.get("authorInfo", {}).get("userId", ""),
                    "text": post.get("text", ""),
                    "likes": post.get("likes", 0),
                    "replies": post.get("replies", 0)
                })

            # 更新下一页的 pageIndex
            page_index += 1
            data = f'{{"threadId":"{thread_id}","pageIndex":{page_index},"pageSize":20,"orderBy":1}}'

        return comments

    async def fetch_userinfo(self, client, authorId):
        url = "https://sgw-cn.c.huawei.com/forward/myhuawei/bffuserservice_h5/gethome_new/2"
        data = f'{{"userId":"{authorId}"}}'
        response = await client.post(url, headers=self.headers, data=data)
        response_json = response.json()
        userList = response_json["data"]
        userInfo = {"昵称": userList["nickName"],
                    "IP地址": userList["ipLocation"],
                    "标签": userList["titles"],
                    "关注数": int(userList["following"]),
                    "粉丝数": int(userList["follower"])}
        url2 = "https://sgw-cn.c.huawei.com/forward/club/content_h5/newsListByUserId/1"
        data2 = f'{{"userId":"{authorId}","curPage":1,"pageSize":20}}'
        response2 = await client.post(url2, headers=self.headers, data=data2)
        response2_json = response2.json()
        numOfPosts = response2_json['data']['threadCount']
        userInfo["发帖数"] = numOfPosts
        return userInfo

    async def fetch_thread_data(self, client, target_count):
        page_index = 1
        result = []
        # print(target_count)
        while len(result) < target_count:
            response = await client.post(self.url, headers=self.headers,
                                         data='{"isIntelligenceOn":false,"circleId":"10000001","pageIndex":' + str(
                                             page_index) + ',"pageSize":20}')
            response_json = response.json()

            # 如果没有更多数据，退出循环
            if not response_json.get("data", {}).get("threadBeanList"):
                break

            json_data = response_json["data"]["threadBeanList"]

            # 提取特定字段
            for item in json_data:
                # 获取评论
                # comments = await self.fetch_comments(client, item["threadId"])
                # 获取话题内容，如果没有则为“空”
                # 获取发帖人信息
                userInfo = await self.fetch_userinfo(client, item["authorId"])
                circle_hashtag = item.get("circleHashtag")

                if isinstance(circle_hashtag, dict):
                    topic = circle_hashtag.get("title")
                else:
                    topic = "空"

                # 获取图片数量
                picNum = 0
                if isinstance(item["imgUrl"], list):
                    picNum = len(item["imgUrl"])

                result.append({
                    "帖子ID": str(item["threadId"]),
                    "总回复数": item["allReplies"],
                    "发帖人信息": userInfo,
                    "用户组（等级）": item["groupName"],
                    "帖子标题": item["title"],
                    "点赞数": item["likes"],
                    "网址": item["threadShareUrl"],
                    "话题": topic,
                    "图片数量": picNum,
                    "发布时间": convert_timestamp_to_beijing_time(int(item["dateline"])).strftime(
                        "%Y-%m-%d %H:%M:%S %Z"),
                    # "评论": comments
                })

                # 输出日志信息
                print(f"爬取帖子 {item['title']}（ID: {item['threadId']}）完成，当前已获取{len(result)}条数据")

                # 如果已经爬取到 target_count 条数据，退出循环
                if len(result) >= target_count:
                    break

            # 更新下一页的 pageIndex
            page_index += 1

        return result

    async def main(self, target_count):
        async with httpx.AsyncClient() as client:
            result = await self.fetch_thread_data(client, target_count)
        # 保存结果到本地
        # save_file(result)
        save_file_to_excel(result)
        # with open('result_with_comments_httpx.json', 'w', encoding='utf-8') as f:
        #     json.dump(result, f, indent=2, ensure_ascii=False)
        # print(f"已爬取到 {target_count} 条数据，结果已保存到文件")

    def run(self, target_count):
        asyncio.run(self.main(target_count))


import json


def save_file(content):
    file_path = filedialog.asksaveasfilename(
        defaultextension='.json',
        filetypes=[('JSON files', '*.json')],
        title="保存文件"
    )
    if file_path:
        with open(file_path, 'w', encoding='utf-8') as file:
            json.dump(content, file, ensure_ascii=False, indent=4)  # 将列表序列化为JSON
        print(f"文件已保存到 {file_path}")

def save_file_to_excel(content):
    file_path = filedialog.asksaveasfilename(
        defaultextension='.xlsx',  # 更改默认扩展名为 Excel
        filetypes=[('Excel files', '*.xlsx')],  # 更改文件类型为 Excel
        title="保存文件"
    )
    if file_path:
        # 将列表转换为 DataFrame
        df = pd.DataFrame(content)
        # 将 DataFrame 保存为 Excel 文件
        df.to_excel(file_path, index=False)
        print(f"文件已保存到 {file_path}")


def start_spider():
    try:
        target_count = int(target_count_entry.get())  # 从Tkinter界面获取target_count
    except ValueError:
        messagebox.showerror("错误", "请输入有效的数字")
        return

    spider = AsyncSpider()
    # 在单独的线程中运行爬虫
    Thread(target=spider.run, args=(target_count,), daemon=True).start()


# 创建GUI界面
window = tk.Tk()
window.title('华为社区热门版块爬虫')
window.geometry('500x400')

# 输入部分
input_frame = tk.Frame(window)
input_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

tk.Label(input_frame, text='目标数量:').pack(side=tk.LEFT)
target_count_entry = tk.Entry(input_frame)
target_count_entry.pack(side=tk.LEFT)

start_button = tk.Button(input_frame, text='开始爬取', command=start_spider)
start_button.pack(side=tk.LEFT, padx=5)

# 输出部分
output_text = tk.Text(window, height=10)
output_text.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

# 重定向标准输出到文本框
sys.stdout = ConsoleRedirector(output_text)

# tk.Button(window, text='开始爬取', command=start_spider).pack()  # 按钮绑定到start_spider函数

window.mainloop()
