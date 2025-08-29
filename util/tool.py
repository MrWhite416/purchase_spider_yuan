# development time: 2025-08-21  13:48
# developer: 元英

from lxml import etree
import pandas as pd
import fitz  # PyMuPDF 的导入名是 fitz，不是 pymupdf
import time
import re


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


def summary_df(df_list:list):
    """
    汇总所有df
    :param df_list:
    :return:
    """

    dfs=[]
    for d in df_list:
        # 校验字典是否为类DataFrame格式（所有值都是等长列表）
        lengths = [len(v) for v in d.values()]
        if len(set(lengths)) > 1:  # 检查所有列表长度是否一致
            raise ValueError(f"字典值列表长度不一致：{d}")
        dfs.append(pd.DataFrame(d))  # 转换为DataFrame

    # 2. 纵向合并所有DataFrame（行合并）
    merged_df = pd.concat(dfs, axis=0, ignore_index=True)

    # 3. 导出为Excel
    merged_df.to_excel("./all_data.xlsx", index=False)
    print(f"合并完成！，共 {len(merged_df)} 行数据")


def pdf_to_text(content:bytes) -> str:
    """ pdf转文本 """

    # 1. 打开 PDF（with 语句自动关闭文件，避免内存泄漏）
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


