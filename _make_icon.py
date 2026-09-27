# -*- coding: utf-8 -*-
"""生成研融科技「干净解压工具」应用图标（专业蓝 + 解压图形）。"""
import os
from PIL import Image, ImageDraw

SIZE = 256
img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# 圆角矩形底色（品牌蓝渐变近似）
def rounded_rect(draw, box, radius, fill):
    x0, y0, x1, y1 = box
    draw.rounded_rectangle(box, radius=radius, fill=fill)

base_blue = (31, 111, 235, 255)
deep_blue = (22, 82, 190, 255)
white = (255, 255, 255, 255)
light = (225, 236, 255, 255)

# 主体：圆角方
rounded_rect(d, (12, 12, 244, 244), 56, base_blue)

# 顶部高光
d.ellipse((60, 30, 196, 120), fill=(90, 150, 250, 120))

# 文件夹图形（代表压缩包/解压）
# 文件夹主体
d.rounded_rectangle((68, 96, 188, 170), radius=16, fill=white)
# 文件夹标签
d.rounded_rectangle((68, 96, 122, 118), radius=8, fill=light)
# 底下的文档（解压出的文件）
d.rounded_rectangle((104, 122, 186, 176), radius=10, fill=white, outline=(210,222,240,255), width=3)

# 解压箭头（向下展开）
# 箭头杆
d.rectangle((140, 148, 152, 178), fill=deep_blue)
# 箭头头部
d.polygon([(132, 164), (146, 184), (160, 164)], fill=deep_blue)
# 三条文件横线
for i, yy in enumerate((120, 134, 148)):
    x0 = 118 + i * 6
    d.rectangle((x0, yy, 168, yy + 5), fill=deep_blue)

# 底部品牌条
d.rectangle((12, 214, 244, 244), fill=deep_blue)
d.rounded_rectangle((12, 214, 244, 244), radius=56, fill=deep_blue)
# 覆盖中间区域形成底部圆角条
d.rectangle((12, 214, 244, 226), fill=deep_blue)

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.ico")
# 保存多尺寸 ico
img.save(out, format="ICO", sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
# 同时导出一张 PNG 便于查看
png = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_icon.png")
img.resize((256,256)).save(png)
print("saved", out, "and", png)
