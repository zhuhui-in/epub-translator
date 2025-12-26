import xml.etree.ElementTree as ET
import re
from typing import List

def annotation_matcher(xml_str, annotation_text, xml_replace=False):
    """
    将注解文本匹配到对应的XML片段

    参数:
        xml_str: XML字符串
        annotation_text: 注解文本内容

    返回:
        list[str]: 匹配后的注解列表，每个元素对应一个fragment
    """
    # 解析XML文件，获取所有fragment元素
    root = ET.fromstring(xml_str)

    # 提取所有fragment并按id排序
    fragments = []
    for frag in root.findall('fragment'):
        frag_id = int(frag.get('id'))
        content = frag.text.strip() if frag.text else ''
        fragments.append((frag_id, content))

    # 按id排序
    fragments.sort(key=lambda x: x[0])
    total_fragments = len(fragments)

    # 处理注解文本：提取所有注解行（忽略空行）
    annotation_lines = [line.strip() for line in annotation_text.split('\n') if line.strip()]

    # 提取每行注解的关键词和完整行内容
    line_info = []
    first_appearance = 0
    for line in annotation_lines:
        try:
            if line.find(":") > 0:
                keyword_part, explanation = line.split(':', 1)
            else:
                keyword_part, explanation = line.split('：', 1)
        except ValueError:
            continue
        keyword = keyword_part.strip()
        pos = xml_str.find(keyword, first_appearance)
        if pos >= 0:
            first_appearance = pos
            # print(keyword, pos)
        elif xml_str.find(keyword) >= 0:
            error_str = f"Keyword '{keyword}' appears out of order in XML."
            raise ValueError(error_str)
        line_info.append((keyword, line))

    # 为每个fragment匹配注解行（按顺序贪婪匹配）
    result = [''] * total_fragments
    used_line_indices = set()  # 记录已使用的注解行索引

    # 遍历所有fragment
    for frag_index, (frag_id, frag_content) in enumerate(fragments):
        # 收集当前fragment的所有匹配注解行
        matched_lines = []

        # 遍历所有注解行，查找匹配当前fragment的未使用注解
        for line_idx, (keyword, line) in enumerate(line_info):
            if line_idx in used_line_indices:
                continue

            # 检查关键词是否存在于当前fragment内容中
            if frag_content:
                if keyword in frag_content:
                    matched_lines.append(line)
                    used_line_indices.add(line_idx)
                elif keyword not in xml_str:
                    used_line_indices.add(line_idx)
                    continue
                else:
                    break  # 关键词未匹配，停止检查后续行，因为注解行是按顺序的
        # 将匹配的注解行合并为一行
        if matched_lines:
            if xml_replace:
                result[frag_index] = construct_xml_content(frag_content, matched_lines)
            else:
                result[frag_index] = '||'.join(matched_lines)

    return result


def construct_xml_content(frag_content: str, matched_lines: List[str]) -> str:
    """
    Constructs XML content with popup annotations for epub.

    Args:
        frag_content: Plain text content
        matched_lines: List of "keyword:explanation" strings

    Returns:
        XML string with highlighted keywords and footnotes
    """
    # Parse matched_lines to extract keywords and explanations
    keyword_map = {}  # keyword -> (explanation, footnote_id)
    footnote_id = 1

    for line in matched_lines:
        # Split by colon (English or Chinese)
        if ':' in line:
            parts = line.split(':', 1)
        elif '：' in line:
            parts = line.split('：', 1)
        else:
            continue

        keyword = parts[0].strip()
        explanation = parts[1].strip()
        if keyword and explanation:
            keyword_map[keyword] = (explanation, footnote_id)
            footnote_id += 1

    # Find all keyword positions in the text (using word boundaries)
    replacements = []  # List of (position, keyword, explanation, footnote_id)
    for keyword, (explanation, fn_id) in keyword_map.items():
        # Use regex with word boundaries to match whole words only
        # Escape special regex characters in the keyword
        escaped_keyword = re.escape(keyword)
        pattern = r'\b' + escaped_keyword + r'\b'

        for match in re.finditer(pattern, frag_content):
            pos = match.start()
            replacements.append((pos, keyword, explanation, fn_id))

    # Sort by position
    replacements.sort(key=lambda x: x[0])

    # Build the XML string by replacing keywords
    result_parts = []
    last_pos = 0

    for pos, keyword, explanation, fn_id in replacements:
        # Add text before the keyword
        if pos > last_pos:
            result_parts.append(frag_content[last_pos:pos])

        # Add the highlighted keyword with link
        result_parts.append(f'<a href="#fn{fn_id}" epub:type="noteref"><span style="color: red;">{keyword}</span></a>')

        last_pos = pos + len(keyword)

    # Add remaining text
    if last_pos < len(frag_content):
        result_parts.append(frag_content[last_pos:])

    # Build footnotes
    footnotes = []
    for keyword, (explanation, fn_id) in sorted(keyword_map.items(), key=lambda x: x[1][1]):
        footnotes.append(f'<aside id="fn{fn_id}" epub:type="footnote">{explanation}</aside>')

    # Combine everything in <p> tag
    main_content = ''.join(result_parts)
    footnotes_content = ''.join(footnotes)
    xml_str = f'<p>{main_content}{footnotes_content}</p>'

    return xml_str

# 主程序：读取文件并执行匹配
if __name__ == "__main__":
    # 假设input1.xml和input2.txt与脚本在同一目录
    xml_path = "input1.xml"
    annotation_path = "input2.txt"

    # 读取注解文本
    with open(annotation_path, 'r', encoding='utf-8') as f:
        annotation_text = f.read()

    # 执行匹配
    matched_annotations = annotation_matcher(open(xml_path, 'r', encoding='utf-8').read(), annotation_text, True)
    open('output.html', 'w', encoding='utf-8').write('<body>' + '\n'.join(matched_annotations) + '</body>')
