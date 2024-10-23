import sys
import os

from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QLineEdit, QLabel, QFileDialog
from PyQt5.QtCore import QThread, pyqtSignal, QObject, Qt
import requests
from urllib.parse import urlencode
from tqdm import tqdm

# 爬虫部分
base_url = 'https://weibo.com/ajax/profile/getImageWall?'


class OutputEmitter(QObject):
    update_msg = pyqtSignal(str)


def get_page(uid, headers, since_id=None):
    params = {
        'uid': f"{uid}",
        'sinceid': since_id,
        'has_album': "true"
    }
    img_base = "https://wx1.sinaimg.cn/large/"
    url = base_url + urlencode(params)
    img_urls = []
    video_urls = []
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        json_data = response.json()
        items = json_data.get('data')
        data = json_data.get('data')["list"]
        next_since_id = items['since_id']
        for item in data:
            if item.get('type') == 'pic':
                img_urls.append(img_base + item['pid'] + ".jpg")
            elif item.get('type') == 'livephoto':
                video_urls.append(item['video'])
        return img_urls, video_urls, next_since_id


def download_media(img_urls, video_urls, img_dir, video_dir, headers, output_emitter):
    for img_src in img_urls:
        img_data = requests.get(url=img_src, headers=headers).content
        img_name = img_src.split('/')[-1]
        with open(os.path.join(img_dir, img_name), 'wb+') as fp:
            fp.write(img_data)

    for video_url in video_urls:
        response = requests.get(url=video_url, headers=headers)
        response.raise_for_status()
        video_data = response.content
        video_name = video_url.split('.')[-2] + ".mp4"
        with open(os.path.join(video_dir, video_name), 'wb+') as fp:
            fp.write(video_data)


def start_crawl(uid, cookies, img_dir, video_dir, output_emitter):
    output_emitter.update_msg.emit("开始了")
    headers = {
        "Cookie": f"{cookies}",
        "referer": f"https://weibo.com/u/{uid}?tabtype=album",
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0'
    }
    progress_bar = tqdm(desc="Downloading", unit="page")
    next_id = None
    total_imgs = 0
    total_videos = 0
    page=1
    while True:
        imgs, videos, next_id = get_page(uid, headers, next_id)
        if next_id == 0:
            output_emitter.update_msg.emit("已经到达最后一页，没有更多数据。")
            break
        download_media(imgs, videos, img_dir, video_dir, headers, output_emitter)
        total_imgs += len(imgs)
        total_videos += len(videos)
        output_emitter.update_msg.emit(f"第{page}页下载{len(imgs)}张图片，{len(videos)}个实况")
        page+=1
        progress_bar.update(1)

    output_emitter.update_msg.emit(f"下载完成共计{total_imgs}张图片，{total_videos}个实况")


class WorkerThread(QThread):
    def __init__(self, uid, cookies, img_dir, video_dir, output_emitter):
        super().__init__()
        self.uid = uid
        self.cookies = cookies
        self.img_dir = img_dir
        self.video_dir = video_dir
        self.output_emitter = output_emitter

    def run(self):
        start_crawl(self.uid, self.cookies, self.img_dir, self.video_dir, self.output_emitter)


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.output_emitter = OutputEmitter()
        self.output_emitter.update_msg.connect(self.onUpdateText)

    def initUI(self):
        self.setWindowTitle('烨的微博下载器')
        layout = QVBoxLayout()
        self.setFixedSize(600, 800)  # 设置固定窗口大小
        icon_path = os.path.join(os.path.dirname(__file__), 'favicon.ico')
        self.setWindowIcon(QIcon(icon_path))
        layout.addWidget(QLabel('用户ID:'))
        self.uid_input = QLineEdit(self)
        layout.addWidget(self.uid_input)


        layout.addWidget(QLabel('Cookies:'))
        self.cookies_input = QLineEdit(self)
        layout.addWidget(self.cookies_input)

        layout.addWidget(QLabel('图片保存路径:'))
        self.img_dir_input = QLineEdit(self)
        layout.addWidget(self.img_dir_input)
        self.img_dir_button = QPushButton('选择路径', self)
        self.img_dir_button.clicked.connect(self.select_img_directory)
        layout.addWidget(self.img_dir_button)

        layout.addWidget(QLabel('实况保存路径:'))
        self.video_dir_input = QLineEdit(self)
        layout.addWidget(self.video_dir_input)
        self.video_dir_button = QPushButton('选择路径', self)
        self.video_dir_button.clicked.connect(self.select_video_directory)
        layout.addWidget(self.video_dir_button)

        self.start_button = QPushButton('开始任务', self)
        self.start_button.clicked.connect(self.startWorker)
        layout.addWidget(self.start_button)

        self.text = QTextEdit()
        self.text.setReadOnly(True)
        layout.addWidget(self.text)
        self.author_info = QLabel('作者:患得患失的小椰子', self)

        layout.addWidget(self.author_info)
        self.link = QLabel('<a href="https://weibo.com/u/6388107214">访问作者的微博</a>', self)
        self.link.setOpenExternalLinks(True)  # 允许打开外部链接
        layout.addWidget(self.link)
        disclaimer = QLabel("免责声明: 本程序仅用于学习和研究目的，使用时请遵守相关法律法规。")
        disclaimer.setAlignment(Qt.AlignCenter)
        layout.addWidget(disclaimer)

        self.setLayout(layout)

    def select_img_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择图片保存路径")
        if directory:
            self.img_dir_input.setText(directory)

    def select_video_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "选择实况保存路径")
        if directory:
            self.video_dir_input.setText(directory)

    def startWorker(self):
        uid = self.uid_input.text()
        cookies = self.cookies_input.text()
        img_dir = self.img_dir_input.text()
        video_dir = self.video_dir_input.text()

        self.thread = WorkerThread(uid, cookies, img_dir, video_dir, self.output_emitter)
        self.thread.start()

    def onUpdateText(self, message):
        self.text.append(message)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
#库安装。
#pip install -r requirements.txt