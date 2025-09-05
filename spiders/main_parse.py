import os
from bs4 import BeautifulSoup
from typing import Tuple, List, Union

import html
import pandas as pd

import re
import fitz  # PyMuPDF
import io
from PIL import Image
from cnocr import CnOcr
import html2text


# 初始化OCR
ocr = CnOcr()

def ocr_content(pdf_res):
    # 将PDF转换为图片
    pdf_doc = fitz.open(
        stream=pdf_res,
        # filename='test.pdf',
        filetype="pdf"
    )
    pdf_res_list = []
    for page in pdf_doc:

        # 转换为高分辨率图片
        pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
        img_data = pix.tobytes("png")
        img = Image.open(io.BytesIO(img_data))

        # OCR识别
        ocr_res = ocr.ocr(img)

        pdf_res_list.append('\n'.join([s['text'] for s in ocr_res]))

    pdf_doc.close()
    return '\n'.join(pdf_res_list)



def get_sub_parts(pattern: Union[str, re.Pattern],
                  repl: str,
                  string: str,
                  count: int = 0,
                  flags: int = 0) -> Tuple[str, List[str]]:  # , List[Tuple[int, int]]
    """
    获取re.sub中被删除的部分和剩余部分

    Args:
        pattern: 正则表达式模式
        repl: 替换字符串
        string: 原始字符串
        count: 最大替换次数，0表示替换所有
        flags: 正则表达式标志

    Returns:
        tuple: (剩余部分, 被删除的部分列表, 匹配位置列表)
    """
    # 编译正则表达式
    if isinstance(pattern, str):
        regex = re.compile(pattern, flags)
    else:
        regex = pattern

    # 找到所有匹配项
    matches = list(regex.finditer(string))

    # 如果指定了count，只取前count个匹配项
    if count > 0:
        matches = matches[:count]

    # 获取被删除的部分和位置信息
    deleted_parts = []
    match_positions = []

    for match in matches:
        deleted_parts.append(match.group())
        match_positions.append((match.start(), match.end()))

    # 执行替换得到剩余部分
    remaining_part = regex.sub(repl, string, count=count)

    return remaining_part, deleted_parts  # , match_positions
    if not excel_path:
        excel_file = fr'{computer_user_path}\Desktop\{excel_name}.xlsx'
    else:
        excel_file = os.path.join(excel_path, f'{excel_name}.xlsx')
    if not sheet_name:
        sheet_name = 'Sheet1'

    for find1 in one_list:
        for key, value in find1.items():
            if type(value) == list:
                find1[key] = join_str.join(value)

    # 无Excel文件则新建，有则添加sheet
    if not os.path.exists(excel_file):
        with pd.ExcelWriter(excel_file) as writer:
            data = pd.DataFrame(one_list)
            data.fillna('', inplace=True)
            data.to_excel(writer, sheet_name=sheet_name, index=False)
    else:
        with pd.ExcelWriter(excel_file, mode='a') as writer:
            data = pd.DataFrame(one_list)
            data.fillna('', inplace=True)
            data.to_excel(writer, sheet_name=sheet_name, index=False)


def deep_clean_text(text: str, replace_all_space=False) -> str:
    """深度清洗文本，去除HTML特殊字符"""
    if not text:
        return ""

    # 1. HTML实体解码
    text = html.unescape(text)

    # 2. 去除HTML空格符和特殊空白符
    html_whitespace_patterns = [
        r'	',
        r' ',
        r'&nbsp;',  # 不间断空格
        r'&ensp;',  # 半角空格
        r'&emsp;',  # 全角空格
        r'&thinsp;',  # 窄空格
        r'&zwsp;',  # 零宽空格
        r'&zwnj;',  # 零宽不连字符
        r'&zwj;',  # 零宽连字符
        r'&#8203;',  # 零宽空格（数字实体）
        r'&#160;',  # 不间断空格（数字实体）
        r'\u00A0',  # Unicode不间断空格
        r'\u2000',  # Unicode n-quad
        r'[\u2000-\u200F]',  # Unicode空格字符范围
        r'[\u2028-\u2029]',  # 行分隔符和段分隔符
        r'\u3000',  # 全角空格
    ]

    for pattern in html_whitespace_patterns:
        text = re.sub(pattern, ' ', text)

    # # 3. 规范化空白字符
    # text = re.sub(r'\s+', ' ', text)  # 多个空白字符合并为一个空格
    # text = re.sub(r'\n\s*\n', '\n', text)  # 多个空行合并为一个
    #
    # # 4. 去除行首行尾空白
    # text = '\n'.join(line.strip() for line in text.split('\n'))
    #
    # # 5. 去除多余的空行
    # text = re.sub(r'\n{3,}', '\n\n', text)
    if replace_all_space:
        return ''.join(text.strip().split())

    return text.strip()


class HTMLTableCleaner:
    """HTML表格清洗器：转换为格式化纯文本"""

    def __init__(self,
                 min_col_width: int = 8,
                 max_col_width: int = 30,
                 padding: int = 2,
                 border_style: str = "simple"):
        """
        初始化清洗器

        Args:
            min_col_width: 列的最小宽度
            max_col_width: 列的最大宽度
            padding: 列之间的间距
            border_style: 边框样式 ("simple", "grid", "none")
        """
        self.min_col_width = min_col_width
        self.max_col_width = max_col_width
        self.padding = padding
        self.border_style = border_style

    def clean_html_content(self, html_str: str) -> str:
        """
        清洗整个HTML内容，重点处理表格

        Args:
            html_str: 原始HTML字符串

        Returns:
            清洗后的纯文本
        """
        if not html_str:
            return ""

        # 解析HTML
        soup = BeautifulSoup(html_str, 'html.parser')

        # 找到所有表格并替换为格式化文本
        tables = soup.find_all('table')
        for table in tables:
            formatted_table = self._format_table_to_text(table)
            # 创建一个新的文本节点替换表格
            table.replace_with(formatted_table)

        # 获取处理后的文本
        text = soup.get_text()

        # 深度清洗文本
        cleaned_text = deep_clean_text(text)

        return cleaned_text

    def extract_table_data(self, table_element) -> List[List[str]]:
        """
        提取表格数据为二维列表

        Args:
            table_element: BeautifulSoup表格元素

        Returns:
            二维列表，每个子列表代表一行
        """
        rows_data = []

        # 处理所有行（包括thead, tbody, tfoot中的行）
        rows = table_element.find_all(['tr'])

        for row in rows:
            row_data = []
            cells = row.find_all(['td', 'th'])

            for cell in cells:
                # 清洗单元格内容
                cell_text = self._clean_cell_content(cell)
                row_data.append(cell_text)

            if row_data:  # 只添加非空行
                rows_data.append(row_data)

        return rows_data

    def _clean_cell_content(self, cell) -> str:
        """清洗单元格内容"""
        if not cell:
            return ""

        # 处理嵌套的HTML元素
        for br in cell.find_all('br'):
            br.replace_with(' ')  # 将<br>替换为空格

        # 获取文本内容
        text = cell.get_text(separator=' ', strip=True)

        # 深度清洗
        cleaned = deep_clean_text(text)

        return cleaned

    def _format_table_to_text(self, table_element) -> str:
        """将表格转换为格式化的纯文本"""
        # 提取表格数据
        table_data = self.extract_table_data(table_element)

        if not table_data:
            return ""

        # 计算列宽
        col_widths = self._calculate_column_widths(table_data)

        # 生成格式化文本
        formatted_text = self._generate_formatted_table(table_data, col_widths)

        return formatted_text

    def _calculate_column_widths(self, table_data: List[List[str]]) -> List[int]:
        """计算每列的最佳宽度"""
        if not table_data:
            return []

        max_cols = max(len(row) for row in table_data)
        col_widths = []

        for col_idx in range(max_cols):
            max_width = 0

            # 找到这一列中最长的内容
            for row in table_data:
                if col_idx < len(row):
                    cell_content = str(row[col_idx])
                    # 考虑中文字符宽度（中文字符通常占2个字符位置）
                    display_width = self._calculate_display_width(cell_content)
                    max_width = max(max_width, display_width)

            # 应用最小和最大宽度限制
            width = max(self.min_col_width, min(max_width + self.padding, self.max_col_width))
            col_widths.append(width)

        return col_widths

    def _calculate_display_width(self, text: str) -> int:
        """计算文本的显示宽度（考虑中文字符）"""
        width = 0
        for char in text:
            # 中文字符、全角字符占2个位置
            if ord(char) > 127 or char in '：；！？（）【】《》""''':
                width += 2
            else:
                width += 1
        return width

    def _generate_formatted_table(self, table_data: List[List[str]], col_widths: List[int]) -> str:
        """生成格式化的表格文本"""
        lines = []

        if self.border_style == "grid":
            # 添加顶部边框
            lines.append(self._create_border_line(col_widths, "top"))

        for row_idx, row in enumerate(table_data):
            # 格式化行内容
            formatted_row = self._format_table_row(row, col_widths)
            if row_idx == 0 and  self.border_style == "simple":
                lines.append(self._create_separator_line(col_widths))
            lines.append(formatted_row)

            # # 在表头后添加分隔线
            # if row_idx == 0 and len(table_data) > 1:
            #     if self.border_style == "simple":
            #         lines.append(self._create_separator_line(col_widths))
            #     elif self.border_style == "grid":
            #         lines.append(self._create_border_line(col_widths, "middle"))
            # elif self.border_style == "grid" and row_idx < len(table_data) - 1:
            #     lines.append(self._create_border_line(col_widths, "middle"))
        lines.append(self._create_separator_line(col_widths))

        if self.border_style == "grid":
            # 添加底部边框
            lines.append(self._create_border_line(col_widths, "bottom"))

        return '\n'.join(lines)

    def _format_table_row(self, row: List[str], col_widths: List[int]) -> str:
        """格式化表格行"""
        formatted_cells = []

        for col_idx, width in enumerate(col_widths):
            cell_content = row[col_idx] if col_idx < len(row) else ""

            # # 截断过长的内容
            # if self._calculate_display_width(cell_content) > width - self.padding:
            #     cell_content = self._truncate_text(cell_content, width - self.padding - 2) + "..."

            # 左对齐格式化
            padded_cell = self._pad_text(cell_content, width)
            formatted_cells.append(padded_cell)

        if self.border_style == "grid":
            return "│ " + " │ ".join(formatted_cells) + " │"
        else:
            return " ".join(formatted_cells)

    def _pad_text(self, text: str, width: int) -> str:
        """文本填充到指定宽度（考虑中文字符）"""
        display_width = self._calculate_display_width(text)
        padding_needed = width - display_width
        return text + " " * max(0, padding_needed)

    def _truncate_text(self, text: str, max_width: int) -> str:
        """截断文本到指定宽度"""
        current_width = 0
        result = ""

        for char in text:
            char_width = 2 if ord(char) > 127 or char in '：；！？（）【】《》""''' else 1
            if current_width + char_width > max_width:
                break
            result += char
            current_width += char_width

        return result

    def _create_separator_line(self, col_widths: List[int]) -> str:
        """创建简单分隔线"""
        return "-" * (sum(col_widths) + len(col_widths) - 1)

    def _create_border_line(self, col_widths: List[int], position: str) -> str:
        """创建网格边框线"""
        if position == "top":
            left, mid, right, fill = "┌", "┬", "┐", "─"
        elif position == "middle":
            left, mid, right, fill = "├", "┼", "┤", "─"
        else:  # bottom
            left, mid, right, fill = "└", "┴", "┘", "─"

        segments = []
        for width in col_widths:
            segments.append(fill * (width + 2))  # +2 for padding

        return left + mid.join(segments) + right


def html2markdown(html_str):
    text_maker = html2text.HTML2Text()
    text_maker.bypass_tables = False
    text_maker.body_width = 0  # 这是关键设
    text = text_maker.handle(html_str)

    return text


class ContentParser:
    @staticmethod
    def normalize_html_str(one_str) -> str:
        """
        html符号抓换为正常的符号
        """
        return html.unescape(one_str)

    def normalize_xpath(self, selector, query, replace_space=True, text_join='\n', unescape_html=True) -> str:
        """
        提取parsel.Selector()对象的文本内容

        若需保留换行符、制表符等，则：replace_space=False
        """
        if replace_space:
            value = selector.xpath(f'normalize-space({query})').get(default='')
            # value = ' '.join(value.split()).strip()
            value = ''.join(deep_clean_text(value).strip().split())
        else:
            value = text_join.join(selector.xpath(f'{query}//text()').getall()).strip()
        if unescape_html:
            value = self.normalize_html_str(value).strip()
        return value

    @staticmethod
    def replace_p_tag(html_content, **kwargs) -> str:
        extra_remove_targets = kwargs.get('extra_remove_targets', {})
        # extra_unwrap_targets = kwargs.get('extra_unwrap_targets', {})

        soup = BeautifulSoup(html_content, 'html.parser')

        # 遍历删除不需要的文档树
        remove_targets = {
            # "id": ["idBodyTop"],  # 按 ID 删除
            'style': ['display: none', 'display:none'],
            "tag": ['strike', 'embed', 'object'],  # 按标签名删除
            "class": ["remove-me", 'hide', 'hidden'],  # 如果未来需要按 class 删除，可以加在这里
        }
        remove_targets.update(extra_remove_targets)
        for method, targets in remove_targets.items():
            for target in targets:
                if method == "id":
                    elements = soup.find_all(id=target)
                elif method == "style":
                    elements = [s for s in soup.find_all(attrs={'style': True}) if target in s.get('style', '')]
                elif method == "tag":
                    elements = soup.find_all(target)
                elif method == "class":
                    elements = soup.find_all(class_=target)
                else:
                    continue  # 其他情况暂不处理

                # 批量删除
                for elem in elements:
                    elem.extract()  # .decompose()  # 完全删除标签

        # 遍历删除标签，只保留文本
        unwrap_targets = {
            "tag": ['u', 'b', 'strong', 'span', 'sub', 'sup']
        }
        for method, targets in unwrap_targets.items():
            for target in targets:
                if method == 'tag':
                    elements = soup.find_all(target)
                else:
                    continue

                # 批量删除
                for elem in elements:
                    if target == 'span':
                        elem.replace_with(deep_clean_text(elem.get_text(strip=True)))
                    else:
                        elem.unwrap()

        # 对于 a、img、table标签特殊处理
        unique_targets = {
            "tag": ['a', 'img', 'table']
        }
        for method, targets in unique_targets.items():
            for target in targets:
                elements = soup.find_all(target)

                if target == 'a':
                    for elem in elements:
                        href = elem['href'] if elem.has_attr('href') else ''
                        if href and href.startswith('http'):
                            elem.replace_with(elem.get_text() + f'（链接：{href}）')
                        else:
                            elem.unwrap()
                elif target == 'img':
                    for elem in elements:
                        img_src = elem['src'] if elem.has_attr('src') else ''
                        if img_src and img_src.startswith('http'):
                            elem.replace_with(elem.get_text() + f'（图片链接：{img_src}）')
                        else:
                            elem.extract()
                elif target == 'table':
                    for elem in elements:
                        elem.replace_with(
                            # HTMLTableCleaner(border_style="simple").clean_html_content(str(elem))
                            html2markdown(str(elem))
                        )

        for p_tag in soup.find_all('p'):
            p_tag.replace_with('《【*${}$*】》'.format('\n\t' + re.sub(r'\s', '', p_tag.get_text(strip=True), flags=re.S)))

        # 注：改变过文档树的soup需要经过str()后，get_text()才能获取到正确的文本
        content = BeautifulSoup(str(soup), 'html.parser').get_text(separator='\n', strip=True)
        content = content.replace('《【*$', '').replace('$*】》', '')
        content = re.sub('\n+', '\n', content, flags=re.S)
        content = re.sub('\t+', '\t', content, flags=re.S)

        return content.strip()


class ProcurementAnnouncement:
    def __init__(self, json_res):
        """
        初始化采购公告生成器
        :param json_res: 包含公告详情的JSON数据字典
        """
        self.json_res = json_res
        # 采购方式映射字典
        self.CGFS_MAP = {
            1: "公开招标",
            4: "竞争性谈判"
            # 可根据实际情况补充其他采购方式
        }

    def generate_content_dict(self):
        """生成内容字典，包含各个字段的标题和内容"""
        content_field = {}

        # 处理联合体投标信息
        is_union = "是" if self.json_res.get('Is_Union', False) else "否"

        # 处理公告期限
        cgfs = self.json_res.get('CGFS', [])
        zs_type = self.json_res.get('ZSType', 0)
        announcement_period = 5 if (cgfs in [1] or zs_type == 2) else 3

        # 项目概况
        content_field['项目概况：'] = self.json_res.get('XiangMu_GaiKuang', '').replace('\n', '\n\t')

        # 项目基本情况
        project_basic = []
        project_basic.append(
            f"项目编号：{self.json_res.get('XiangMu_No', '')}\t项目名称：{self.json_res.get('XiangMu_Name', '')}")

        # 处理采购方式
        cgfs_code = self.json_res.get('CGFS')
        cgfs_text = self.CGFS_MAP.get(cgfs_code, self.json_res.get('GongGao_LeiXing', '').replace('采购公告', ''))

        # 处理预算金额
        budget = self.json_res.get('YuSuan_JinE', '')
        budget_unit = "%" if self.json_res.get('YuSuan_JinE_DanWei') == 3 else "万元"

        # 处理最高限价
        max_price = self.json_res.get('ZuiGao_XianJia', '')
        max_price_unit = "%" if self.json_res.get('ZuiGao_XianJia_DanWei') == 3 else "万元"

        project_basic.append(f"采购方式：{cgfs_text}\t预算金额：{budget}{budget_unit}")
        project_basic.append(f"最高限价：{max_price}{max_price_unit}\t采购需求：{self.json_res.get('CaiGou_XuQiu', '')}")
        project_basic.append(f"合同履行期限：{self.json_res.get('GongQi', '')}\t本项目是否接受联合体投标：{is_union}")

        content_field['一、项目基本情况'] = '\n\t'.join(project_basic)

        # 申请人资格要求
        if cgfs not in [4]:  # 非竞争性谈判
            资格要求 = []
            资格要求.append("1. 满足《中华人民共和国政府采购法》第二十二条规定；")
            资格要求.append(f"2. 落实政府采购政策需满足的资格要求：{self.json_res.get('GongYingShang_ZiGe', '')}")
            资格要求.append(f"3. 本项目的特定资格要求：{self.json_res.get('TeDing_ZiGe_YaoQiu', '')}")
            content_field['二、申请人资格要求'] = '\n\t'.join(资格要求)

        else:  # 竞争性谈判
            content_field['供应商资格：'] = self.json_res.get('GongYingShang_ZiGe', '').replace('\n', '\n\t')


        # 获取采购文件
        获取采购文件 = []
        获取采购文件.append(
            f"获取时间：{self.json_res.get('BMKSSJ', '')}至{self.json_res.get('BMJSSJ', '')}，采购文件获取时间，以{self.json_res.get('HuoQu_PingTai', '')}记录的时间为准（下同）")
        获取采购文件.append(f"获取方式及地点：{self.json_res.get('HuoQu_FangShi', '')}采购文件只在网上发布，不再提供其他发布方式")

        # 非竞争性谈判显示售价
        if cgfs not in [4]:
            获取采购文件.append("售价：0元")

        content_field['三、获取采购文件'] = '\n\t'.join(获取采购文件)

        # 响应文件提交
        响应文件提交 = []
        响应文件提交.append(
            f"（一）.递交投标文件（响应文件）截止时间和开标时间：{self.json_res.get('TouBiao_EndTime', '')}，开标地址：{self.json_res.get('KaiBiao_DiDian', '')}")
        响应文件提交.append("（二）.递交方式:以该项目采购文件要求为准")
        响应文件提交.append("（三）.本次政府采购不接受邮寄的投标文件（响应文件）")
        content_field['四、响应文件提交'] = '\n\t'.join(响应文件提交)

        # 开启（非CGFS=1和4的情况）
        if (cgfs not in [1]) and (cgfs not in [4]):
            content_field[
                '五、开启'] = f"时间：{self.json_res.get('TouBiao_EndTime', '')}\t地点：{self.json_res.get('KaiBiao_DiDian', '')}"

        # 公告期限（非CGFS=4的情况）
        if cgfs not in [4]:
            content_field['六、公告期限'] = f"自本公告发布之日起至少 {announcement_period} 个工作日"

        # 其他补充事宜（非CGFS=4的情况）
        if cgfs not in [4]:
            content_field['七、其他补充事宜'] = self.json_res.get('XinXi_NeiRong', '').replace('\n', '\n\t')

        # 联系方式（非CGFS=4的情况）
        if cgfs not in [4]:
            # 确定标题
            if zs_type == 2:
                contact_title = "十、对本次招标提出询问，请按以下方式联系"
            elif cgfs in [1]:
                contact_title = "七、对本次招标提出询问，请按以下方式联系"
            else:
                contact_title = "八、对本次招标提出询问，请按以下方式联系"

            # 联系方式内容
            contact_info = []
            contact_info.append(f"1.采购人信息")
            contact_info.append(f"\t\t名称：{self.json_res.get('CaiGouRen', '')}\t地址：{self.json_res.get('CaiGou_DiZhi', '')}")
            contact_info.append(
                f"\t\t联系人：{self.json_res.get('CaiGou_LianXiRen', '')}\t联系方式：{self.json_res.get('CaiGou_LianXi_FangShi', '')}")
            contact_info.append(f"\t2. 采购代理机构信息")
            contact_info.append(
                f"\t\t名称：{self.json_res.get('CaiGou_DaiLi', '')}\t地址：{self.json_res.get('CaiGou_DaiLi_DiZhi', '')}")
            contact_info.append(
                f"\t\t联系人：{self.json_res.get('CaiGou_DaiLi_LianXiRen', '')}\t联系方式：{self.json_res.get('CaiGou_DaiLi_LianXi_FangShi', '')}")

            content_field[contact_title] = '\n'.join(contact_info)

        # 处理省平台公告的情况
        if self.json_res.get('xinXi_LaiYuan') == '9' and self.json_res.get('shengPingTai_GongGao'):
            content_field['省平台公告'] = self.json_res.get('shengPingTai_GongGao', '').replace('\n', '\n\t')

        return content_field


if __name__ == '__main__':
    test_dict = {
            "CaiGou_GongGao_GUID": "a41d8cca-4bbb-4a58-ae1a-cd244f459407",
            "XiangMu_No": "N5115022025000188翠政工采【2025】21号",
            "XiangMu_Name": "宜宾市一曼中学校初中部2025年提升改造项目",
            "GongGao_LeiXing": "竞争性谈判采购公告",
            "XiangMu_FuZeRen": "肖勇",
            "ZSType": 1,
            "BaoJianShu": 1,
            "GongYingShang_ZiGe": "详见采购文件。",
            "TouBiao_EndTime": "2025-08-12 09:30:00",
            "XinXi_NeiRong": "信息发布：四川政府采购网、全国公共资源交易平台（四川省）、宜宾市公共资源交易信息网。",
            "CaiGouRen": "宜宾市一曼中学校",
            "CaiGou_LianXiRen": "肖老师",
            "CaiGou_LianXi_FangShi": "13778905367",
            "CaiGou_DaiLi": "宜宾市政府采购中心翠屏区分中心",
            "CaiGou_DaiLi_LianXiRen": "交易受理股",
            "CaiGou_DaiLi_LianXi_FangShi": "08318202636",
            "Publish_StartTime": "2025-08-06 00:00:00",
            "Publish_EndTime": "2025-08-10 23:59:00",
            "Is_Publish": True,
            "XinXi_LaiYuan": 3,
            "Last_UpdateTime": "2025-08-06 16:25:47",
            "Area": "3",
            "CGFS": 2,
            "YuSuan_JinE": 183.254,
            "YuSuan_JinE_DanWei": 2,
            "ZuiGao_XianJia": 178.987759,
            "ZuiGao_XianJia_DanWei": 2,
            "CaiGou_XuQiu": "详见采购文件。",
            "GongQi": "90日历天",
            "Is_Union": False,
            "TeDing_ZiGe_YaoQiu": "详见采购文件。",
            "BMKSSJ": "2025-08-06 00:00:00",
            "BMJSSJ": "2025-08-10 23:59:00",
            "HuoQu_FangShi": "四川政府采购网-项目电子化交易系统-投标（响应）管理-未获取采购文件中选择本项目获取采购文件。",
            "KaiBiao_DiDian": "四川省政府采购一体化平台项目电子化交易系统-开标/开启大厅参与开启",
            "CaiGou_DiZhi": "宜宾市一曼中学校",
            "CaiGou_DaiLi_DiZhi": "宜宾市翠屏区岷江新区东山路25号市民中心4楼",
            "HuoQu_PingTai": "四川省政府采购一体化平台",
            "HeGe_GongYingShang_RenShu": 0,
            "NewVersion": 3,
            "IsDeleted": False,
            "TouBiao_EndTime_ZGYS": "1900-01-01 00:00:00",
            "GongGao_Title": "竞争性谈判公告",
            "XiangMu_GaiKuang": "宜宾市一曼中学校初中部2025年提升改造项目的潜在投标人应登录四川省政府采购一体化平台获取招标文件，并于2025年08月12日09时30分00秒（北京时间）前递交投标文件"
        }

    # content_dict = ProcurementAnnouncement(test_dict).generate_content_dict()
    # content = '\n'.join([f"{key}\n\t{value}" for key, value in content_dict.items()])
    # print(content)
