import sys
import tkinter as tk
from tkinter import filedialog
import asyncio
import httpx
import json
import threading

import pandas as pd

from IOStream import ConsoleRedirector
from timeutils import convert_timestamp_to_beijing_time


class AsyncHuaweiCommunityCrawler:
    def __init__(self, url, headers):
        self.url = url
        self.headers = headers

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

    async def fetch_comments(self, client, thread_id):
        comments_url = 'http://sgw-cn.c.huawei.com/forward/club/content_h5/queryThreadDetail/1'
        page_index = 1
        comments = []

        while True:
            data = {
                "threadId": thread_id,
                "pageIndex": page_index,
                "pageSize": 20,
                "orderBy": 1
            }

            response = await client.post(comments_url, headers=self.headers, json=data)
            response_json = response.json()

            if not response_json.get("data", {}).get("postList"):
                break

            post_list = response_json["data"]["postList"]

            for post in post_list:
                comments.append({
                    "name": post.get("authorInfo", {}).get("name", ""),
                    "userId": post.get("authorInfo", {}).get("userId", ""),
                    "text": post.get("text", ""),
                    "likes": post.get("likes", 0),
                    "replies": post.get("replies", 0)
                })

            page_index += 1

        return comments

    async def fetch_data(self, client, circle_tag, target_count):
        page_index = 1
        result = []
        cursor = 0
        lastThreadId = 0
        startTime = 0
        while len(result) < target_count:
            data = {
                "isIntelligenceOn": False,
                "circleId": "10000001",
                "circleTag": circle_tag,
                "pageIndex": page_index,
                "cursor": cursor,
                "lastThreadId": lastThreadId,
                "startTime": startTime,
                "pageSize": 20
            }
            # print(data)
            response = await client.post(self.url, headers=self.headers, json=data)
            response_json = response.json()

            if not response_json.get("data", {}).get("threadBeanList"):
                print("没有数据了")
                break

            json_data = response_json["data"]["threadBeanList"]
            for item in json_data:
                comments = await self.fetch_comments(client, item["threadId"])

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
                    "帖子ID": item["threadId"],
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
                    "评论": comments
                })
                print(f"爬取帖子 {item['title']}（ID: {item['threadId']}）完成，当前已获取{len(result)}条数据")
                if len(result) >= target_count:
                    print("你要的数据量已经够了")
                    break

            page_index += 1
            cursor = response_json["data"]["cursor"]
            lastThreadId = response_json["data"]["lastThreadId"]
            startTime = response_json["data"]["startTime"]
            # print(cursor)

        return result


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

def start_crawler(target_count, circle_tag, tag_mapping, output_text):
    url = 'https://sgw-cn.c.huawei.com/forward/club/content_h5/allPost/3'
    headers = {
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
        'Content-Type': 'application/json',
        'Origin': 'https://cn.club.vmall.com',
        'Referer': 'https://cn.club.vmall.com/',
        'SGW-APP-ID': 'EDCF82D77A5AB59706CD5F2163F67427',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'cross-site',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'X-Requested-With': 'XMLHttpRequest',
        'request-source': 'H5',
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"macOS"',
        'site': 'zh_CN'
    }
    crawler = AsyncHuaweiCommunityCrawler(url, headers)

    async def run_crawler():
        async with httpx.AsyncClient() as client:
            data = await crawler.fetch_data(client, circle_tag, target_count)
            # output_text.insert(tk.END, json.dumps(data, ensure_ascii=False, indent=4))
            # 保存结果到文件
            # with open('result.json', 'w', encoding='utf-8') as file:
            #     json.dump(data, file, ensure_ascii=False, indent=4)
            # save_file(data)
            save_file_to_excel(data)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_crawler())


def on_start_button_click(entry, tag_var, tag_mapping, output_text):
    try:
        target_count = int(entry.get())
        circle_tag = tag_mapping[tag_var.get()]
        threading.Thread(target=start_crawler, args=(target_count, circle_tag, tag_mapping, output_text)).start()
    except ValueError:
        print("请输入有效的数字")


# GUI 界面设置
tag_mapping = {
    "HarmonyOS4": "a50f93ab-d9d4-41d9-b368-cfabf07bd1b5",
    "HarmonyOS3": "e23c04a8-0639-11ed-80c7-abe65529ca53",
    "HarmonyOS2": "6e955caa-684f-11ec-a893-8d6acc597352",
    "内测/公测": "9d97f7d3-684f-11ec-976c-3b13b8660d34",
    "玩机技巧": "e9338f89-6852-11ec-976c-99d8ee2bdc7d",
    "版本更新": "7e969f65-6852-11ec-9d2b-055d9cd70172",
    "Harmony桌面": "97122bc1-6852-11ec-a893-09e4eb1f76be",
    "场景设计": "97122bc2-6852-11ec-a893-2b3b390454c8",
    "畅联": "97122bc3-6852-11ec-a893-41a09c8288fe",
    "HUAWEI HiCar": "2b317b7d-6853-11ec-bdd3-f7dd23ece1af",
    "长辈关怀": "64302215-c61d-11ec-bc75-633d9aba7d18",
    "无障碍": "2b317b7e-6853-11ec-bdd3-4fc76c47b0ec",
    "EMUI 11": "2b317b81-6853-11ec-bdd3-dffb392f74fd",
    "EMUI 10&EMUI 10.1/Magic UI 3": "2b317b82-6853-11ec-bdd3-a73e9b98c74e",
    "EMUI其他": "2b317b83-6853-11ec-bdd3-47f9956ffc18",
    "其他": "2b317b84-6853-11ec-bdd3-b1346dac8e61",
    "问题与建议": "2b317b86-6853-11ec-bdd3-3f57f6634d3d"
}
window = tk.Tk()
window.title("华为社区版块爬虫(除热门)")
window.geometry("600x400")

label = tk.Label(window, text="请输入要爬取的数据数量:")
label.pack()

entry = tk.Entry(window)
entry.pack()

tag_var = tk.StringVar(window)
tag_var.set("选择一个版块")
tag_menu = tk.OptionMenu(window, tag_var, *tag_mapping.keys())
tag_menu.pack()

start_button = tk.Button(window, text="开始爬取",
                         command=lambda: on_start_button_click(entry, tag_var, tag_mapping, output_text))
start_button.pack()
# 输出部分
output_text = tk.Text(window, height=20)
output_text.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

# 重定向标准输出到文本框
sys.stdout = ConsoleRedirector(output_text)
# output_text = tk.Text(window, height=10)
# output_text.pack(fill=tk.BOTH, expand=True)

window.mainloop()
