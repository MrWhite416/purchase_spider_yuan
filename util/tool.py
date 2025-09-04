# development time: 2025-08-21  13:48
# developer: 元英
import json

from lxml import etree
import pandas as pd
import fitz  # PyMuPDF 的导入名是 fitz，不是 pymupdf
import time
import re
from util.infer import AI_filter
from setting import sender_email,sender_auth_code, default_recipients,attachment_paths,is_first_file

import smtplib
from datetime import datetime,timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Optional, List
from email.utils import formatdate




def element_to_text(content:str):
    """
    提取文本并保留网页原始换行结构
    :param content_element: lxml解析后的content节点（即你代码中的 doc_sele.xpath(".//div[@id='mycontent']")[0]）
    :return: 保留换行的纯文本
    """

    # 删除style
    source = re.sub("<style.*?>.*?</style>", "", content, flags=re.DOTALL)

    content_element = etree.HTML(source)

    # 1. 给需要换行的标签手动插入换行符（关键步骤）
    # 网页中常见的“换行触发标签”：<p>段落、<br>换行、<tr>表格行、<li>列表项、项目分类标题（如“一、项目基本情况”所在标签）
    for tag in content_element.xpath('.//p | .//br | .//tr | .//li | .//h1 | .//h2 | .//h3'):
        # 给标签前后插入换行符（根据标签类型调整，避免多余空行）
        if tag.tag == "br":
            # <br>标签直接替换为换行符（本身无内容，插入后删除原标签）
            br_newline = etree.Element("text")
            br_newline.text = "\n"
            tag.addprevious(br_newline)
            tag.getparent().remove(tag)
        else:
            # <p>、<tr>、<li>等标签：前后各加一个换行（模拟网页段落/表格行的换行）
            # 先给标签前面插换行（避免多个标签连续换行）
            prev_elem = tag.getprevious()  # 先获取前一个元素
            # 只有当前一个元素不存在，或存在但不是 text 标签时，才插入换行
            if prev_elem is None or prev_elem.tag != "text":
                pre_newline = etree.Element("text")
                pre_newline.text = "\n"
                tag.addprevious(pre_newline)

            next_elem = tag.getnext()  # 先获取后一个元素
            if next_elem is None or next_elem.tag != "text":
                post_newline = etree.Element("text")
                post_newline.text = "\n"
                tag.addnext(post_newline)

    # 2. 提取文本（此时已保留换行结构）
    text = etree.tostring(content_element, method="text", encoding="utf8").decode("utf8")

    # 3. 清理多余空行（避免标签嵌套导致的连续换行，可选但更整洁）
    # 把“多个连续换行”合并为“单个换行”，“换行+多个空格”转为“换行”
    text = re.sub(r'\n+', '\n', text)  # 多换行→单换行
    text = re.sub(r'\n\s+', '\n', text)  # 换行后接多个空格→仅换行
    text = text.strip()  # 去除首尾多余空行


    return text


def summary_df(file_path:str,df_list:list):
    """
    汇总+存储所有df
    :param df_list:
    :return:
    """

    dfs = []
    for d in df_list:
        if isinstance(d,dict):
            # 校验字典是否为类DataFrame格式（所有值都是等长列表）
            lengths = [len(v) for v in d.values()]
            if len(set(lengths)) > 1:  # 检查所有列表长度是否一致
                raise ValueError(f"字典值列表长度不一致：{d}")
            dfs.append(pd.DataFrame(d))  # 转换为DataFrame
        else:
            dfs.append(d)

    # 2. 纵向合并所有DataFrame（行合并）
    merged_df = pd.concat(dfs, axis=0, ignore_index=True)
    has_no_data = merged_df.empty  # 检查是否没有行数据

    if not has_no_data:
        save_df = AI_filter(merged_df)
    else:
        save_df = merged_df

    # 步骤1：读取已有文件的工作表，获取当前数据的行数（用于定位追加位置）
    try:
        existing_df = pd.read_excel(file_path, sheet_name="Sheet1", engine="openpyxl")
        startrow = len(existing_df)+1  # 追加位置：原有数据的最后一行之后
        need_header = False  # 追加时不写表头
    except FileNotFoundError:
        # 若文件不存在，直接初始化
        # 导出为Excel
        save_df.to_excel("./all_data.xlsx", index=False,sheet_name="Sheet1")
        print(f"文件 {file_path} 不存在，自动创建...")
        return
    except ValueError:
        # 若工作表不存在，直接写入新工作表（mode='a' 支持新增工作表）
        print(f"工作表 Sheet1 不存在，新增工作表并写入数据...")
        startrow = 0  # 新工作表从第 0 行开始写入（含列名）
        need_header = True  # 新工作表需写表头

    # 步骤2：追加写入（mode='a'，append 模式，不覆盖原有数据）
    with pd.ExcelWriter(
            file_path,
            engine="openpyxl",
            mode="a",  # 关键：追加模式
            if_sheet_exists="overlay"  # 工作表已存在时，覆盖指定区域（仅追加，不影响原有数据）
    ) as writer:
        # startrow：从第 N 行开始写入（跳过原有数据的行，不重复写入列名）
        save_df.to_excel(
            writer,
            sheet_name="Sheet1",
            index=False,
            startrow=startrow,  # 核心参数：指定追加的起始行
            header=need_header  # 追加时False（不写表头），新增工作表时True（写表头）
        )
    print(f"成功追加 {len(save_df)} 条数据到 {file_path}（工作表：Sheet）")


def pdf_to_text(content:bytes) -> str:
    """ pdf转文本 """

    # 1. 打开 PDF
    doc = fitz.Document(stream=content)
    total_pages = doc.page_count
    full_text = ""


    # 2. 逐页提取文本（批量处理比单页循环更高效）
    for page_num in range(total_pages):
        page = doc[page_num]
        # 提取页面文本，option="text" 表示只取纯文本（跳过图片/注释）
        page_text = page.get_text(option="text")
        full_text += page_text + "\n\n"  # 页间加空行分隔

    return full_text



# 邮件发送函数
def send_163_email(
        subject: str,
        content: str,
        recipients: Optional[List[str]] = None,
        attachments: Optional[List[str]] = None,
        content_type: str = "plain"  # "plain"=纯文本，"html"=HTML格式
) -> bool:
    """
    163邮箱发送函数
    :param subject: 邮件主题（支持中文）
    :param content: 邮件内容
    :param recipients: 收件人列表（默认用EmailConfig.default_recipients）
    :param attachment_paths: 附件路径列表（如["data.xlsx", "log.txt"]，可选）
    :param content_type: 内容格式（纯文本/HTML）
    :return: 发送成功返回True，失败返回False
    """
    # 处理默认参数
    if recipients is None:
        recipients = default_recipients
    if attachments is None:
        attachments = attachment_paths

    try:
        # 1. 构造邮件对象（带附件需用MIMEMultipart）
        msg = MIMEMultipart()
        msg["Message-ID"] = f"<{datetime.now().timestamp()}@{sender_email.split('@')[1]}>"
        msg["Date"] = formatdate(localtime=True)  # 本地时间格式
        msg["From"] = sender_email
        msg["To"] = Header(", ".join(recipients), "utf-8")
        # 邮件主题（中文需用Header处理，避免乱码）
        msg["Subject"] = Header(subject, "utf-8")

        # 2. 添加邮件正文
        content_part = MIMEText(content, content_type, "utf-8")
        msg.attach(content_part)

        # 3. 添加附件（若有）
        for attach_path in attachments:
            try:
                # 二进制读取附件文件
                with open(attach_path, "rb") as f:
                    # 构造附件对象（base64编码，支持所有文件类型）
                    attach = MIMEText(f.read(), "base64", "utf-8")
                    attach["Content-Type"] = "application/octet-stream"
                    # 设置附件显示名称（中文需用Header，避免乱码）
                    attach_filename = attach_path.split("/")[-1]  # 提取文件名
                    attach.add_header(
                        "Content-Disposition",
                        "attachment",
                        filename=(Header(attach_filename, "utf-8").encode())
                    )
                    msg.attach(attach)
                print(f"附件添加成功：{attach_filename}")
            except Exception as e:
                print(f"附件添加失败：{str(e)}")
                continue  # 单个附件失败不影响整体邮件发送

        # 4. 连接163 SMTP服务器并发送
        with smtplib.SMTP_SSL("smtp.163.com", 465) as smtp:
            # 登录SMTP服务器（用163授权码，不是原密码）
            smtp.login(sender_email, sender_auth_code)
            # 发送邮件（from_addr=发件人，to_addrs=收件人列表，msg=邮件字符串）
            smtp.sendmail(
                from_addr=sender_email,
                to_addrs=recipients,
                msg=msg.as_string()
            )

        # 发送成功日志
        print(f"邮件发送成功！主题：{subject} | 收件人：{', '.join(recipients)}")
        return True

    except Exception as e:
        # 发送失败日志（含详细错误堆栈，方便排查）
        print(f"邮件发送失败！主题：{subject} | 错误：{str(e)}")
        return False





def clean_old_data(excel_path, output_path=None):
    """
    清洗Excel中的旧数据，保留3个月内的新数据
    :param excel_path: 原始Excel文件路径
    :param output_path: 清洗后的数据保存路径（默认覆盖原文件）
    """
    # 1. 读取Excel文件
    try:
        df = pd.read_excel(excel_path)
    except Exception as e:
        print(f"读取文件失败：{str(e)}")
        return

    new_release = []
    for tt in df["时间"]:
        # 判断是否为xx年xx月xx（日）
        if "年" in tt:
            n_t = tt.replace("年", "-").replace("月", "-").replace("日", "")[:10]
        # 判断是否为xx.xx.xx
        elif "." in tt:
            n_t = tt.replace(".", "-")[:10]
        else:
            n_t = tt[:10]

        n_t = datetime.strptime(n_t,"%Y-%m-%d").date()
        new_release.append(n_t)

    df["时间"] = new_release

    # 4. 计算3个月前的日期（作为判断新旧的临界点）
    today = datetime.now().date()
    three_months_ago = today - timedelta(days=3 * 30)  # 简化计算：按每月30天

    # 5. 过滤数据：保留 release_time 在3个月内的新数据
    # 条件：release_time > 三个月前 且 时间有效（不是NaT）
    mask = (df["时间"] > three_months_ago) & (df["时间"].notna())
    new_data = df[mask]
    old_data_count = len(df) - len(new_data)

    # 将时间类型转为字符串
    # 对于 datetime.date 类型的列，转换为字符串
    new_data["时间"] = new_data["时间"].apply(lambda x: x.strftime("%Y-%m-%d"))

    # 6. 输出清洗结果
    print(f"清洗完成：原始数据共 {len(df)} 条，过滤旧数据 {old_data_count} 条，保留数据 {len(new_data)} 条")

    # 7. 保存清洗后的数据
    if output_path is None:
        output_path = excel_path  # 默认覆盖原文件
    try:
        new_data.to_excel(output_path, index=False)
        print(f"清洗后的数据已保存至：{output_path}")
    except Exception as e:
        print(f"保存文件失败：{str(e)}")







